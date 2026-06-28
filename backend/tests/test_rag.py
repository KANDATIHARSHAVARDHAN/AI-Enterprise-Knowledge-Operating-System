"""
EKOS RAG Unit Tests
Tests retrieval logic, sparse retrievers, and Reciprocal Rank Fusion.
"""

import pytest
from app.rag.sparse_retriever import SparseRetriever
from app.rag.hybrid_retriever import HybridRetriever


def test_sparse_retriever_bm25():
    """Test that BM25 retrieves matching documents."""
    retriever = SparseRetriever()

    docs = [
        {"content": "Machine X failed due to spindle bearing overheating.", "metadata": {"id": 1}},
        {"content": "Coolant pressure dropped on CNC Milling Station Y.", "metadata": {"id": 2}},
        {"content": "Preventive maintenance scheduled for conveyor belts.", "metadata": {"id": 3}},
    ]

    retriever.build_index(docs)

    # Search for "spindle bearing"
    results = retriever.retrieve("spindle bearing", top_k=2)

    assert len(results) > 0
    assert results[0]["metadata"]["id"] == 1


def test_rrf_merging():
    """Test Reciprocal Rank Fusion (RRF) logic."""
    retriever = HybridRetriever()

    # RRF combines and ranks results
    dense_res = [
        {"metadata": {"embedding_id": "doc1"}, "score": 0.9},
        {"metadata": {"embedding_id": "doc2"}, "score": 0.8},
    ]
    sparse_res = [
        {"metadata": {"embedding_id": "doc2"}, "score": 12.5},
        {"metadata": {"embedding_id": "doc3"}, "score": 5.2},
    ]

    fused = retriever._reciprocal_rank_fusion(dense_res, sparse_res, k=60)

    # doc2 was in both, so it should rank highly or be combined
    doc_ids = [item["metadata"]["embedding_id"] for item in fused]
    assert "doc1" in doc_ids
    assert "doc2" in doc_ids
    assert "doc3" in doc_ids
