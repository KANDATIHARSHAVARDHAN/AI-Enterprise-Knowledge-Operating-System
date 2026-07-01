"""
EKOS Firestore Database Adapter
Provides async Firestore database operations mapping to dynamic models.
"""

import os
import time
import random
from typing import Optional, List, Dict, Any
from google.cloud import firestore
from google.oauth2 import service_account
from app.config import get_settings
from app.utils.logger import logger

settings = get_settings()

# Initialize Firestore AsyncClient
db: Optional[firestore.AsyncClient] = None

def get_firestore_client() -> Optional[firestore.AsyncClient]:
    """Initialize and return the Firestore async client. Returns None if credentials cannot be resolved."""
    global db
    if db is None:
        credentials_path = settings.firebase_credentials_path
        project_id = settings.firebase_project_id or None
        
        # Check if credential file exists
        if credentials_path and os.path.exists(credentials_path):
            try:
                credentials = service_account.Credentials.from_service_account_file(credentials_path)
                db = firestore.AsyncClient(project=project_id, credentials=credentials)
                logger.info("Initialized Firestore client with service account credentials.")
            except Exception as e:
                logger.error(f"Failed to load credentials from {credentials_path}: {e}")
                try:
                    db = firestore.AsyncClient(project=project_id)
                except Exception as ex:
                    logger.error(f"Failed to initialize Firestore with default credentials after fallback: {ex}")
                    db = None
        else:
            # Fallback to default credentials
            logger.info("Credentials file not found. Initializing Firestore with default credentials.")
            try:
                db = firestore.AsyncClient(project=project_id)
            except Exception as e:
                logger.error(f"Failed to initialize Firestore with default credentials: {e}")
                db = None
            
    return db


def generate_int_id() -> int:
    """Generate a unique 64-bit integer ID."""
    return int(time.time() * 1000) * 1000 + random.randint(0, 999)


class FirestoreModel:
    """Dynamic class wrapping dictionary items to allow attribute access (like SQLAlchemy ORM)."""
    
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            self.__dict__[k] = v
            
    def __getattr__(self, name):
        return self.__dict__.get(name, None)
        
    def __setattr__(self, name, value):
        self.__dict__[name] = value
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert attributes to a dictionary, filtering private properties."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}


# Define models for route types compatibility
class User(FirestoreModel):
    pass

class Document(FirestoreModel):
    pass

class DocumentChunk(FirestoreModel):
    pass

class Conversation(FirestoreModel):
    pass

class Message(FirestoreModel):
    pass

class QueryLog(FirestoreModel):
    pass

class EvaluationResult(FirestoreModel):
    pass

class AuditLog(FirestoreModel):
    pass

class MemoryStore(FirestoreModel):
    pass


class FirestoreDB:
    """Helper service class for executing async queries on Firestore."""

    def __init__(self):
        self.client = get_firestore_client()

    # === User operations ===
    async def get_user(self, user_id: int) -> Optional[User]:
        doc_ref = self.client.collection("users").document(str(user_id))
        doc = await doc_ref.get()
        if doc.exists:
            return User(**doc.to_dict())
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        users_ref = self.client.collection("users")
        query = users_ref.where("email", "==", email).limit(1)
        docs = await query.get()
        for doc in docs:
            return User(**doc.to_dict())
        return None

    async def get_user_by_username(self, username: str) -> Optional[User]:
        users_ref = self.client.collection("users")
        query = users_ref.where("username", "==", username).limit(1)
        docs = await query.get()
        for doc in docs:
            return User(**doc.to_dict())
        return None

    async def create_user(self, data: Dict[str, Any]) -> User:
        user_id = generate_int_id()
        data["id"] = user_id
        data["created_at"] = time.time()
        data["updated_at"] = time.time()
        data["is_active"] = True
        
        await self.client.collection("users").document(str(user_id)).set(data)
        return User(**data)

    # === Document operations ===
    async def get_document(self, doc_id: int) -> Optional[Document]:
        doc_ref = self.client.collection("documents").document(str(doc_id))
        doc = await doc_ref.get()
        if doc.exists:
            return Document(**doc.to_dict())
        return None

    async def get_documents(self, uploaded_by: Optional[int] = None) -> List[Document]:
        col_ref = self.client.collection("documents")
        if uploaded_by is not None:
            query = col_ref.where("uploaded_by", "==", uploaded_by)
        else:
            query = col_ref
            
        docs = await query.get()
        return [Document(**doc.to_dict()) for doc in docs]

    async def create_document(self, data: Dict[str, Any]) -> Document:
        doc_id = generate_int_id()
        data["id"] = doc_id
        data["created_at"] = time.time()
        data["updated_at"] = time.time()
        data["chunk_count"] = 0
        
        await self.client.collection("documents").document(str(doc_id)).set(data)
        return Document(**data)

    async def update_document(self, doc_id: int, updates: Dict[str, Any]) -> Optional[Document]:
        updates["updated_at"] = time.time()
        doc_ref = self.client.collection("documents").document(str(doc_id))
        await doc_ref.update(updates)
        
        updated_doc = await doc_ref.get()
        if updated_doc.exists:
            return Document(**updated_doc.to_dict())
        return None

    async def delete_document(self, doc_id: int) -> bool:
        # Delete document metadata
        await self.client.collection("documents").document(str(doc_id)).delete()
        
        # Batch delete chunks related to this document
        chunks_col = self.client.collection("document_chunks")
        query = chunks_col.where("document_id", "==", doc_id)
        docs = await query.get()
        
        # Firestore batch delete
        batch = self.client.batch()
        for doc in docs:
            batch.delete(doc.reference)
        await batch.commit()
        return True

    # === Document Chunk operations ===
    async def get_chunks(self, doc_id: int) -> List[DocumentChunk]:
        col_ref = self.client.collection("document_chunks")
        query = col_ref.where("document_id", "==", doc_id).order_by("chunk_index")
        docs = await query.get()
        return [DocumentChunk(**doc.to_dict()) for doc in docs]

    async def get_chunk(self, chunk_id: int) -> Optional[DocumentChunk]:
        doc_ref = self.client.collection("document_chunks").document(str(chunk_id))
        doc = await doc_ref.get()
        if doc.exists:
            return DocumentChunk(**doc.to_dict())
        return None

    async def create_chunk(self, data: Dict[str, Any]) -> DocumentChunk:
        chunk_id = generate_int_id()
        data["id"] = chunk_id
        data["created_at"] = time.time()
        
        await self.client.collection("document_chunks").document(str(chunk_id)).set(data)
        return DocumentChunk(**data)

    # === Conversation operations ===
    async def get_conversation(self, conv_id: int) -> Optional[Conversation]:
        doc_ref = self.client.collection("conversations").document(str(conv_id))
        doc = await doc_ref.get()
        if doc.exists:
            return Conversation(**doc.to_dict())
        return None

    async def get_conversations(self, user_id: int) -> List[Conversation]:
        col_ref = self.client.collection("conversations")
        query = col_ref.where("user_id", "==", user_id).where("is_active", "==", True).order_by("created_at", direction=firestore.Query.DESCENDING)
        docs = await query.get()
        return [Conversation(**doc.to_dict()) for doc in docs]

    async def create_conversation(self, data: Dict[str, Any]) -> Conversation:
        conv_id = generate_int_id()
        data["id"] = conv_id
        data["created_at"] = time.time()
        data["updated_at"] = time.time()
        data["is_active"] = True
        
        await self.client.collection("conversations").document(str(conv_id)).set(data)
        return Conversation(**data)

    async def update_conversation(self, conv_id: int, updates: Dict[str, Any]) -> Optional[Conversation]:
        updates["updated_at"] = time.time()
        doc_ref = self.client.collection("conversations").document(str(conv_id))
        await doc_ref.update(updates)
        
        updated_doc = await doc_ref.get()
        if updated_doc.exists:
            return Conversation(**updated_doc.to_dict())
        return None

    async def delete_conversation(self, conv_id: int) -> bool:
        # Delete messages first
        messages_col = self.client.collection("messages")
        query = messages_col.where("conversation_id", "==", conv_id)
        docs = await query.get()
        
        batch = self.client.batch()
        for doc in docs:
            batch.delete(doc.reference)
            
        # Delete conversation
        batch.delete(self.client.collection("conversations").document(str(conv_id)))
        await batch.commit()
        return True

    # === Message operations ===
    async def get_messages(self, conv_id: int) -> List[Message]:
        col_ref = self.client.collection("messages")
        query = col_ref.where("conversation_id", "==", conv_id).order_by("created_at")
        docs = await query.get()
        return [Message(**doc.to_dict()) for doc in docs]

    async def create_message(self, data: Dict[str, Any]) -> Message:
        msg_id = generate_int_id()
        data["id"] = msg_id
        data["created_at"] = time.time()
        
        await self.client.collection("messages").document(str(msg_id)).set(data)
        return Message(**data)

    # === Memory Store operations ===
    async def get_memories(self, user_id: int) -> List[MemoryStore]:
        col_ref = self.client.collection("memory_store")
        query = col_ref.where("user_id", "==", user_id).order_by("created_at", direction=firestore.Query.DESCENDING)
        docs = await query.get()
        return [MemoryStore(**doc.to_dict()) for doc in docs]

    async def create_memory(self, data: Dict[str, Any]) -> MemoryStore:
        mem_id = generate_int_id()
        data["id"] = mem_id
        data["created_at"] = time.time()
        data["last_accessed_at"] = time.time()
        data["access_count"] = 0
        
        await self.client.collection("memory_store").document(str(mem_id)).set(data)
        return MemoryStore(**data)

    # === Audit Log operations ===
    async def create_audit_log(self, data: Dict[str, Any]) -> AuditLog:
        log_id = generate_int_id()
        data["id"] = log_id
        data["created_at"] = time.time()
        
        await self.client.collection("audit_logs").document(str(log_id)).set(data)
        return AuditLog(**data)

    # === Query Log operations ===
    async def get_query_log(self, log_id: int) -> Optional[QueryLog]:
        doc_ref = self.client.collection("query_logs").document(str(log_id))
        doc = await doc_ref.get()
        if doc.exists:
            return QueryLog(**doc.to_dict())
        return None

    async def get_query_logs(self) -> List[QueryLog]:
        col_ref = self.client.collection("query_logs")
        query = col_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        docs = await query.get()
        return [QueryLog(**doc.to_dict()) for doc in docs]

    async def create_query_log(self, data: Dict[str, Any]) -> QueryLog:
        log_id = generate_int_id()
        data["id"] = log_id
        data["created_at"] = time.time()
        
        await self.client.collection("query_logs").document(str(log_id)).set(data)
        return QueryLog(**data)

    # === Evaluation Result operations ===
    async def get_evaluation_results(self) -> List[EvaluationResult]:
        col_ref = self.client.collection("evaluation_results")
        query = col_ref.order_by("created_at", direction=firestore.Query.DESCENDING)
        docs = await query.get()
        return [EvaluationResult(**doc.to_dict()) for doc in docs]

    async def create_evaluation_result(self, data: Dict[str, Any]) -> EvaluationResult:
        eval_id = generate_int_id()
        data["id"] = eval_id
        data["created_at"] = time.time()
        
        await self.client.collection("evaluation_results").document(str(eval_id)).set(data)
        return EvaluationResult(**data)


# Session mock for FastAPI dependency injection if provider=firestore
class AsyncFirestoreSession:
    """Mock database session that routes requests to FirestoreDB helper functions."""
    
    def __init__(self):
        self.db = FirestoreDB()
        self._pending = []
        
    async def get(self, model_class, doc_id):
        # Maps db.get(Document, document_id) or db.get(Conversation, id)
        doc_id = int(doc_id)
        res = None
        if model_class.__name__ == "Document":
            res = await self.db.get_document(doc_id)
        elif model_class.__name__ == "Conversation":
            res = await self.db.get_conversation(doc_id)
        elif model_class.__name__ == "User":
            res = await self.db.get_user(doc_id)
        elif model_class.__name__ == "QueryLog":
            res = await self.db.get_query_log(doc_id)
            
        if res and res not in self._pending:
            self._pending.append(res)
        return res

    def add(self, model_instance):
        # We store instances temporarily and commit them later during flush/commit.
        if model_instance not in self._pending:
            self._pending.append(model_instance)

    async def flush(self):
        if not self._pending:
            return
        
        for item in list(self._pending):
            model_name = item.__class__.__name__
            data = item.to_dict()
            
            # Generate ID and save
            if not item.id:
                item.id = generate_int_id()
                data["id"] = item.id
                
            if model_name == "User":
                await self.db.client.collection("users").document(str(item.id)).set(data)
            elif model_name == "Document":
                await self.db.client.collection("documents").document(str(item.id)).set(data)
            elif model_name == "DocumentChunk":
                await self.db.client.collection("document_chunks").document(str(item.id)).set(data)
            elif model_name == "Conversation":
                await self.db.client.collection("conversations").document(str(item.id)).set(data)
            elif model_name == "Message":
                await self.db.client.collection("messages").document(str(item.id)).set(data)
            elif model_name == "QueryLog":
                await self.db.client.collection("query_logs").document(str(item.id)).set(data)
            elif model_name == "EvaluationResult":
                await self.db.client.collection("evaluation_results").document(str(item.id)).set(data)
            elif model_name == "AuditLog":
                await self.db.client.collection("audit_logs").document(str(item.id)).set(data)
            elif model_name == "MemoryStore":
                await self.db.client.collection("memory_store").document(str(item.id)).set(data)

    async def commit(self):
        await self.flush()
        
    async def rollback(self):
        self._pending.clear()
            
    async def close(self):
        self._pending.clear()

    async def execute(self, statement):
        # We need to parse select queries
        stmt_str = str(statement).lower()
        
        class ResultMock:
            def __init__(self, items):
                self.items = items
            def scalar_one_or_none(self):
                return self.items[0] if self.items else None
            def fetchall(self):
                return [(item,) for item in self.items]
            def keys(self):
                return ["item"]
                
        # Handle User queries
        if "from users" in stmt_str or "users.id" in stmt_str:
            bound_params = statement.compile().params
            email = bound_params.get("email_1")
            username = bound_params.get("username_1")
            user_id = bound_params.get("id_1")
                
            if email:
                user = await self.db.get_user_by_email(email)
                return ResultMock([user] if user else [])
            elif username:
                user = await self.db.get_user_by_username(username)
                return ResultMock([user] if user else [])
            elif user_id:
                user = await self.db.get_user(int(user_id))
                return ResultMock([user] if user else [])
                
        # Handle Documents queries
        elif "from documents" in stmt_str:
            bound_params = statement.compile().params
            uploaded_by = bound_params.get("uploaded_by_1")
            docs = await self.db.get_documents(uploaded_by)
            return ResultMock(docs)
            
        # Handle Conversations queries
        elif "from conversations" in stmt_str:
            bound_params = statement.compile().params
            user_id = bound_params.get("user_id_1")
            convs = await self.db.get_conversations(int(user_id))
            return ResultMock(convs)
            
        # Handle Messages queries
        elif "from messages" in stmt_str:
            bound_params = statement.compile().params
            conv_id = bound_params.get("conversation_id_1")
            msgs = await self.db.get_messages(int(conv_id))
            return ResultMock(msgs)
            
        # Handle Memory queries
        elif "from memory_store" in stmt_str:
            bound_params = statement.compile().params
            user_id = bound_params.get("user_id_1")
            mems = await self.db.get_memories(int(user_id))
            return ResultMock(mems)

        return ResultMock([])
