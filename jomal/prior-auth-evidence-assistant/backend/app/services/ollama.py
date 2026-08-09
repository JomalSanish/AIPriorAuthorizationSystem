"""
Ollama LLM Client.
Provides access to native Ollama models (llama3.2:3b).
Respects GPU Contention Guard.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx

from app.config import get_settings
from app.core.gpu_guard import gpu_guard, GpuPriority

logger = logging.getLogger("pa.services.ollama")

class LLMUnavailableError(Exception):
    """Raised when Ollama is unreachable."""
    pass

class OllamaClient:
    def __init__(self):
        self._settings = get_settings()
        self.base_url = self._settings.OLLAMA_URL
        self.model = "llama3.2:3b"

    async def generate(
        self, prompt: str, system_prompt: str = "", format_schema: Dict[str, Any] | str | None = None
    ) -> str:
        """Calls Ollama /api/generate with structured JSON support."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
        }
        if format_schema:
            payload["format"] = format_schema

        timeout = 60.0 # Configurable per-call timeout
        
        async with gpu_guard.acquire_or_fallback(GpuPriority.LLM, timeout=120.0) as acquired:
            if not acquired:
                # LLM can't fallback to CPU dynamically in this setup, so we raise if lock fails
                raise LLMUnavailableError("Failed to acquire GPU for LLM inference.")
                
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{self.base_url}/api/generate", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("response", "")
            except httpx.RequestError as e:
                logger.error(f"Ollama connection error: {e}")
                raise LLMUnavailableError(f"Ollama unreachable: {e}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error {e.response.status_code}: {e.response.text}")
                raise LLMUnavailableError(f"Ollama API error: {e.response.status_code}")

    async def chat(self, messages: list[Dict[str, str]], format_schema: Dict[str, Any] | str | None = None) -> str:
        """Calls Ollama /api/chat for multi-turn conversations."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
        }
        if format_schema:
            payload["format"] = format_schema

        timeout = 60.0
        
        async with gpu_guard.acquire_or_fallback(GpuPriority.LLM, timeout=120.0) as acquired:
            if not acquired:
                raise LLMUnavailableError("Failed to acquire GPU for LLM inference.")
                
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(f"{self.base_url}/api/chat", json=payload)
                    response.raise_for_status()
                    data = response.json()
                    return data.get("message", {}).get("content", "")
            except httpx.RequestError as e:
                logger.error(f"Ollama connection error: {e}")
                raise LLMUnavailableError(f"Ollama unreachable: {e}")
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error {e.response.status_code}: {e.response.text}")
                raise LLMUnavailableError(f"Ollama API error: {e.response.status_code}")

ollama_client = OllamaClient()
