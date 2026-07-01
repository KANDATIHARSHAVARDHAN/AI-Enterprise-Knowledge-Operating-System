import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from app.rag.hybrid_retriever import HybridRetriever

async def test():
    query = 'What critical inspection step is mentioned in the L-200 incident report (as a corrective action) that is completely missing from the original maintenance manual?'
    hr = HybridRetriever()
    results = hr.retrieve(query, top_k=5)
    for r in results:
        print(f'SCORE: {r.get("rrf_score")}')
        print(f'SOURCE: {r.get("metadata", {}).get("source")}')
        print(f'CONTENT: {r.get("content")}')
        print('---')

asyncio.run(test())
