"""
EKOS Vision Agent
Analyzes images using OCR and LLM-based description.
"""

import json
from app.agents.base_agent import BaseAgent
from app.agents.prompts import VISION_PROMPT
from app.llm.groq_client import get_chat_model
from app.ingestion.parsers.image_parser import ImageParser
from app.utils.logger import logger


class VisionAgent(BaseAgent):
    """Analyzes images for visual information and OCR text."""

    def __init__(self):
        super().__init__(
            name="vision_agent",
            description="Analyzes images for visual content and extracted text",
        )
        self.image_parser = ImageParser()

    async def execute(self, state: dict) -> dict:
        """Analyze images related to the query."""
        query = state.get("query", "")
        image_paths = state.get("image_paths", [])

        if not image_paths:
            state["vision_results"] = {
                "status": "skipped",
                "reason": "No images to analyze",
            }
            return state

        vision_results = []

        for image_path in image_paths:
            try:
                # Parse image for OCR text
                parsed = self.image_parser.parse(image_path)
                if not parsed:
                    continue

                image_data = parsed[0]
                ocr_text = image_data.get("content", "")
                metadata = image_data.get("metadata", {})

                # Use LLM to analyze the image context
                llm = get_chat_model(json_mode=True)
                chain = VISION_PROMPT | llm
                response = await chain.ainvoke({
                    "task": f"Analyze image for: {query}",
                    "image_description": f"Image file: {metadata.get('source', 'unknown')}",
                    "ocr_text": ocr_text or "No text extracted",
                })
                response_text = response.content

                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError:
                    result = {"analysis": response_text}

                result["source"] = metadata.get("source", "unknown")
                result["ocr_text"] = ocr_text
                vision_results.append(result)

            except Exception as e:
                logger.warning(f"Vision analysis failed for {image_path}: {e}")
                vision_results.append({
                    "source": image_path,
                    "status": "error",
                    "error": str(e),
                })

        state["vision_results"] = vision_results
        logger.info(f"Vision Agent analyzed {len(vision_results)} images")
        return state
