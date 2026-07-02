import asyncio
from pathlib import Path
from dotenv import load_dotenv
from app.ingestion.pipeline import IngestionPipeline

load_dotenv()

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
