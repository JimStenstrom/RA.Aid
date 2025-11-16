"""Async client for vLLM backend."""

import httpx
from typing import Dict, Any, AsyncIterator
import json

from .config import settings


class VLLMClient:
    """
    Async HTTP client for vLLM inference server.

    Handles communication with vLLM's OpenAI-compatible API.
    """

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url or settings.vllm_url
        self.api_key = api_key or settings.vllm_api_key
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=300.0,  # 5 minutes for long generations
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()

    async def chat_completion(
        self,
        messages: list[Dict[str, str]],
        model: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any] | AsyncIterator[Dict[str, Any]]:
        """
        Request chat completion from vLLM.

        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model identifier
            stream: Whether to stream the response
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Response dict or async iterator of response chunks
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async with statement.")

        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **kwargs
        }

        if stream:
            return self._stream_chat_completion(payload)
        else:
            response = await self._client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_chat_completion(
        self,
        payload: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream chat completion responses."""
        if not self._client:
            raise RuntimeError("Client not initialized.")

        async with self._client.stream("POST", "/v1/chat/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    async def completion(
        self,
        prompt: str,
        model: str,
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any] | AsyncIterator[Dict[str, Any]]:
        """
        Request text completion from vLLM.

        Args:
            prompt: Input prompt text
            model: Model identifier
            stream: Whether to stream the response
            **kwargs: Additional parameters

        Returns:
            Response dict or async iterator of response chunks
        """
        if not self._client:
            raise RuntimeError("Client not initialized.")

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            **kwargs
        }

        if stream:
            return self._stream_completion(payload)
        else:
            response = await self._client.post("/v1/completions", json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_completion(
        self,
        payload: Dict[str, Any]
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream completion responses."""
        if not self._client:
            raise RuntimeError("Client not initialized.")

        async with self._client.stream("POST", "/v1/completions", json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    async def health_check(self) -> bool:
        """Check if vLLM server is healthy."""
        if not self._client:
            raise RuntimeError("Client not initialized.")

        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False
