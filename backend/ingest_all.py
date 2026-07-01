import asyncio
import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from app.ingestion.pipeline import IngestionPipeline

async def run():
    pipeline = IngestionPipeline()
    uploads_dir = Path('uploads')
    for file in uploads_dir.glob('*.txt'):
        print(f'Ingesting {file}')
        try:
            res = await pipeline.ingest_document(1, file)
            print(res)
        except Exception as e:
            print(e)

asyncio.run(run())
