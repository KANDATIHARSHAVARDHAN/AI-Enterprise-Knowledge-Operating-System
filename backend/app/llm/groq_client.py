"""
EKOS Groq LLM Client
Provides async Groq API access with retry logic, rate limiting, and streaming support.
"""

import time
from typing import AsyncGenerator, Optional
from groq import AsyncGroq, Groq
from langchain_groq import ChatGroq
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import get_settings
from app.utils.logger import logger
from app.utils.exceptions import LLMError, RateLimitError


class GroqClient:
    """Async Groq LLM client with retry and rate limiting."""

    def __init__(self):
        self.settings = get_settings()
        self.async_client = AsyncGroq(api_key=self.settings.groq_api_key)
        self.sync_client = Groq(api_key=self.settings.groq_api_key)
        self._request_count = 0
        self._window_start = time.time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        Send a chat completion request to Groq.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model name (defaults to large model)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            json_mode: If True, request JSON response format

        Returns:
            The assistant's response content as a string
        """
        model = model or self.settings.groq_model_large
        start_time = time.time()

        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = await self.async_client.chat.completions.create(**kwargs)

            latency_ms = int((time.time() - start_time) * 1000)
            content = response.choices[0].message.content or ""

            logger.info(
                "Groq API call completed",
                extra={
                    "extra_data": {
                        "model": model,
                        "latency_ms": latency_ms,
                        "input_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "output_tokens": response.usage.completion_tokens if response.usage else 0,
                    }
                },
            )

            return content

        except Exception as e:
            error_msg = str(e)
            if "rate_limit" in error_msg.lower() or "429" in error_msg:
                logger.warning(f"Groq rate limit hit, will retry: {error_msg}")
                raise RateLimitError(f"Groq rate limit exceeded: {error_msg}")
            logger.error(f"Groq API error: {error_msg}")
            raise LLMError(f"Groq API call failed: {error_msg}")

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat completion response from Groq.

        Yields:
            Individual content chunks as they arrive
        """
        model = model or self.settings.groq_model_large

        try:
            stream = await self.async_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Groq streaming error: {e}")
            raise LLMError(f"Groq streaming failed: {e}")

    async def chat_with_fast_model(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        """Use the fast/small model for less complex tasks (classification, extraction)."""
        return await self.chat(
            messages=messages,
            model=self.settings.groq_model_small,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

    def chat_sync(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Synchronous chat completion (for use in non-async contexts)."""
        model = model or self.settings.groq_model_large
        try:
            response = self.sync_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""
        except Exception as e:
            raise LLMError(f"Groq sync API call failed: {e}")


# Singleton instance
_groq_client: Optional[GroqClient] = None


def get_groq_client() -> GroqClient:
    """Get or create the singleton Groq client."""
    global _groq_client
    if _groq_client is None:
        _groq_client = GroqClient()
    return _groq_client


def get_chat_model(
    model_name: Optional[str] = None,
    json_mode: bool = False,
    temperature: float = 0.1,
    max_tokens: int = 6000,
) -> ChatGroq:
    """
    Get a LangChain ChatGroq model instance.

    Args:
        model_name: Name of the Groq model to use (defaults to groq_model_large)
        json_mode: Whether to enable JSON output format
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        ChatGroq instance
    """
    settings = get_settings()
    model = model_name or settings.groq_model_large

    kwargs = {
        "groq_api_key": settings.groq_api_key,
        "model_name": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

    primary_llm = ChatGroq(**kwargs)

    # Automatically fall back to the smaller model if the primary model hits a rate limit
    fallback_kwargs = kwargs.copy()
    fallback_kwargs["model_name"] = settings.groq_model_small
    fallback_llm = ChatGroq(**fallback_kwargs)

    return primary_llm.with_fallbacks([fallback_llm])
