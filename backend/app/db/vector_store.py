"""
EKOS Pinecone Vector Store (LangChain Integrated)
Manages Pinecone index using LangChain abstractions for vector search and metadata mapping.
Persists metadata cache in Firestore to keep local BM25 sparse search fully synchronized.
"""

import json
import os
from pathlib import Path
from typing import Optional
from langchain_core.embeddings import Embeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from app.config import get_settings
from app.ingestion.embedder import get_embedder
from app.utils.logger import logger


class LangChainEmbeddingsWrapper(Embeddings):
    """LangChain compatibility wrapper for EKOS DocumentEmbedder."""

    def __init__(self):
        self.embedder = get_embedder()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.embedder.embed_batch(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.embedder.embed_query(text)


class VectorStore:
    """Pinecone-based vector store wrapped with LangChain abstractions."""

    def __init__(self):
        self.settings = get_settings()
        self.dimension = self.settings.embedding_dimension
        
        self.pc: Optional[Pinecone] = None
        self.vectorstore: Optional[PineconeVectorStore] = None
        self.embeddings_wrapper = LangChainEmbeddingsWrapper()

        # Local metadata cache (needed for BM25 Sparse Retriever)
        self.metadata: list[dict] = []
        self.id_map: dict[str, int] = {}
        self._metadata_path = Path(self.settings.faiss_metadata_path)

        self._initialize()

    def _initialize(self):
        """Initialize Pinecone, load metadata cache, and build the LangChain PineconeVectorStore."""
        api_key = self.settings.pinecone_api_key
        index_name = self.settings.pinecone_index_name

        # Load metadata cache
        self._load_metadata_cache()

        if not api_key or not index_name:
            logger.warning("Pinecone API key or index name not configured. Vector Store operations will fail.")
            return

        try:
            self.pc = Pinecone(api_key=api_key)
            
            # List existing indexes
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if index_name not in existing_indexes:
                logger.info(f"Pinecone index '{index_name}' not found. Creating serverless index...")
                self.pc.create_index(
                    name=index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region="us-east-1"
                    )
                )
                logger.info(f"Successfully created Pinecone index '{index_name}'.")

            # Initialize LangChain's PineconeVectorStore
            self.vectorstore = PineconeVectorStore(
                index_name=index_name,
                embedding=self.embeddings_wrapper,
                pinecone_api_key=api_key
            )
            logger.info(f"Connected to LangChain PineconeVectorStore '{index_name}'")
        except Exception as e:
            logger.error(f"Failed to initialize Pinecone Vector Store: {e}")

    def _load_metadata_cache(self):
        """Load vector metadata cache from local disk or Firestore backup."""
        if self._metadata_path.exists():
            try:
                with open(self._metadata_path, "r") as f:
                    data = json.load(f)
                self.metadata = data.get("metadata", [])
                self.id_map = data.get("id_map", {})
                logger.info(f"Loaded {len(self.metadata)} metadata cache items from local disk.")
                return
            except Exception as e:
                logger.warning(f"Failed to read local metadata cache: {e}")

        # Fallback: Download metadata cache from Firestore
        if self.settings.database_provider == "firestore":
            try:
                from google.cloud import firestore
                from google.oauth2 import service_account

                credentials_path = self.settings.firebase_credentials_path
                project_id = self.settings.firebase_project_id or None

                if credentials_path and os.path.exists(credentials_path):
                    credentials = service_account.Credentials.from_service_account_file(credentials_path)
                    client = firestore.Client(project=project_id, credentials=credentials)
                else:
                    client = firestore.Client(project=project_id)

                meta_doc = client.collection("vector_store").document("metadata_cache").get()
                if meta_doc.exists:
                    meta_data = meta_doc.to_dict()
                    self.metadata = json.loads(meta_data.get("metadata_json", "[]"))
                    self.id_map = json.loads(meta_data.get("id_map_json", "{}"))
                    logger.info(f"Restored {len(self.metadata)} metadata cache items from Firestore.")
                    
                    # Cache to local disk
                    self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self._metadata_path, "w") as f:
                        json.dump({"metadata": self.metadata, "id_map": self.id_map}, f)
            except Exception as e:
                logger.warning(f"Could not restore metadata cache from Firestore: {e}")

    def _save_metadata_cache(self):
        """Save vector metadata cache to local disk and backup to Firestore."""
        try:
            self._metadata_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._metadata_path, "w") as f:
                json.dump({
                    "metadata": self.metadata,
                    "id_map": self.id_map,
                }, f)
            logger.info("Saved vector metadata cache locally.")
        except Exception as e:
            logger.warning(f"Failed to save metadata cache locally: {e}")

        # Upload backup to Firestore
        if self.settings.database_provider == "firestore":
            try:
                from google.cloud import firestore
                from google.oauth2 import service_account

                credentials_path = self.settings.firebase_credentials_path
                project_id = self.settings.firebase_project_id or None

                if credentials_path and os.path.exists(credentials_path):
                    credentials = service_account.Credentials.from_service_account_file(credentials_path)
                    client = firestore.Client(project=project_id, credentials=credentials)
                else:
                    client = firestore.Client(project=project_id)

                client.collection("vector_store").document("metadata_cache").set({
                    "metadata_json": json.dumps(self.metadata),
                    "id_map_json": json.dumps(self.id_map)
                })
                logger.info("Uploaded vector metadata cache backup to Firestore.")
            except Exception as e:
                logger.warning(f"Failed to backup metadata cache to Firestore: {e}")

    def add_embeddings(
        self,
        embeddings: list[list[float]],
        metadata_list: list[dict],
        embedding_ids: list[str],
    ):
        """
        Add embeddings to the Pinecone index.
        Uses raw Pinecone index upserts for optimal throughput.
        """
        if not self.vectorstore:
            logger.warning("Pinecone vectorstore not initialized. Cannot add embeddings.")
            return

        if not embeddings:
            return

        try:
            # 1. Update in-memory metadata cache
            start_pos = len(self.metadata)
            for i, (meta, emb_id) in enumerate(zip(metadata_list, embedding_ids)):
                position = start_pos + i
                self.metadata.append(meta)
                self.id_map[emb_id] = position

            # 2. Get underlying Pinecone index client
            index = self.pc.Index(self.settings.pinecone_index_name)
            
            # Build vectors array
            vectors = []
            for i, (emb, meta, emb_id) in enumerate(zip(embeddings, metadata_list, embedding_ids)):
                cleaned_meta = {}
                for k, v in meta.items():
                    if isinstance(v, (str, int, float, bool)):
                        cleaned_meta[k] = v
                    elif v is None:
                        cleaned_meta[k] = ""
                    else:
                        cleaned_meta[k] = json.dumps(v)
                
                # Ensure 'text' key is present for LangChain Pinecone default behavior
                if "text" not in cleaned_meta and "content" in meta:
                    cleaned_meta["text"] = meta["content"]

                vectors.append((emb_id, emb, cleaned_meta))

            # Upsert in batches of 100
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i:i + batch_size]
                index.upsert(vectors=batch)

            logger.info(f"Uploaded {len(embeddings)} vectors to Pinecone using LangChain VectorStore.")
            
            # 3. Persist metadata cache changes
            self._save_metadata_cache()
        except Exception as e:
            logger.error(f"Failed to upload vectors to Pinecone: {e}")

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
    ) -> list[dict]:
        """
        Search for similar vectors using LangChain.
        """
        if not self.vectorstore:
            logger.warning("Pinecone vectorstore not initialized. Cannot perform search.")
            return []

        try:
            # Query using LangChain similarity search with score
            langchain_results = self.vectorstore.similarity_search_by_vector_with_score(
                embedding=query_embedding,
                k=top_k
            )

            results = []
            for doc, score in langchain_results:
                parsed_meta = {}
                for k, v in doc.metadata.items():
                    if isinstance(v, str) and (v.startswith("{") or v.startswith("[")):
                        try:
                            parsed_meta[k] = json.loads(v)
                        except json.JSONDecodeError:
                            parsed_meta[k] = v
                    else:
                        parsed_meta[k] = v

                results.append({
                    "score": float(score),
                    "metadata": parsed_meta,
                    "content": doc.page_content,
                    "content_preview": doc.page_content[:200] if doc.page_content else "",
                })

            return results
        except Exception as e:
            logger.error(f"Failed to query Pinecone VectorStore: {e}")
            return []

    def delete_by_document(self, document_id: int):
        """
        Remove all vectors for a specific document.
        """
        # 1. Filter in-memory metadata cache
        indices_to_keep = []
        new_metadata = []
        new_id_map = {}

        for i, meta in enumerate(self.metadata):
            if meta.get("document_id") != document_id:
                indices_to_keep.append(i)

        for new_idx, old_idx in enumerate(indices_to_keep):
            meta = self.metadata[old_idx]
            new_metadata.append(meta)
            emb_id = meta.get("embedding_id", f"vec_{new_idx}")
            new_id_map[emb_id] = new_idx

        self.metadata = new_metadata
        self.id_map = new_id_map
        self._save_metadata_cache()

        # 2. Delete vectors from Pinecone Cloud
        if not self.vectorstore:
            logger.warning("Pinecone vectorstore not initialized. Cannot delete vectors.")
            return

        try:
            # Delete using LangChain metadata filtering delete method
            self.vectorstore.delete(filter={"document_id": document_id})
            logger.info(f"Deleted all Pinecone vectors for document_id={document_id}")
        except Exception as e:
            logger.error(f"Failed to delete Pinecone vectors for document {document_id}: {e}")

    def save(self):
        """No-op for Pinecone as cloud updates are immediately persistent."""
        pass

    @property
    def total_vectors(self) -> int:
        """Get total number of vectors in the index."""
        if not self.pc:
            return 0
        try:
            index = self.pc.Index(self.settings.pinecone_index_name)
            stats = index.describe_index_stats()
            return stats.total_vector_count
        except Exception:
            return 0

    def get_stats(self) -> dict:
        """Get vector store statistics."""
        if not self.vectorstore:
            return {
                "total_vectors": 0,
                "dimension": self.dimension,
                "provider": "pinecone_langchain",
                "status": "uninitialized"
            }
        try:
            index = self.pc.Index(self.settings.pinecone_index_name)
            stats = index.describe_index_stats()
            return {
                "total_vectors": stats.total_vector_count,
                "dimension": stats.dimension,
                "provider": "pinecone_langchain",
                "status": "initialized",
                "index_name": self.settings.pinecone_index_name
            }
        except Exception as e:
            return {
                "total_vectors": 0,
                "dimension": self.dimension,
                "provider": "pinecone_langchain",
                "status": "error",
                "error": str(e)
            }


# Singleton
_vector_store: Optional[VectorStore] = None


def get_vector_store() -> VectorStore:
    """Get or create the singleton vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
