"""Ollama local VLM adapter — HTTP via httpx."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.implementations.llm._base import coerce_json, encode_image_b64, resolve_config
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProvider, VLMProviderError

logger = get_logger(__name__)


_RETRYABLE = (httpx.HTTPError, httpx.TransportError)


class OllamaProvider(VLMProvider):
    """Adapter for a local Ollama daemon (default http://localhost:11434)."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: float = 300.0):
        self._base_url = base_url or resolve_config("ollama", "base_url", default="http://localhost:11434")
        self._model = model or resolve_config("ollama", "model", default="qwen2.5vl:7b")
        self._timeout = timeout

    def name(self) -> str:
        return "ollama"

    @retry(
        reraise=True,
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    )
    def _post_generate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url.rstrip('/')}/api/generate"
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"Ollama HTTP {exc.response.status_code}", self._model, exc)

    def _call(self, image_path: str, prompt: str, system: Optional[str] = None) -> str:
        b64 = encode_image_b64(image_path)
        payload: Dict[str, Any] = {
            "model": self._model,
            "prompt": prompt,
            "images": [b64],
            "stream": False,
        }
        if system:
            payload["system"] = system
        try:
            data = self._post_generate(payload)
            return str(data.get("response", ""))
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Ollama unreachable: {exc}", self._model, exc)

    def caption_image(self, image_path: str, prompt: str, context: Optional[str] = None) -> str:
        full_prompt = f"{prompt}\n\nContext:\n{context}" if context else prompt
        return self._call(image_path, full_prompt)

    def describe_layout(self, image_path: str, prompt: str) -> Dict[str, Any]:
        system = "Respond in compact JSON describing detected layout regions (header, table, image, footer)."
        return coerce_json(self._call(image_path, prompt, system=system))

    def extract_structured(self, image_path: str, prompt: str, schema_hint: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            "Respond ONLY with JSON matching the provided schema hint. "
            f"Schema hint: {schema_hint}"
        )
        return coerce_json(self._call(image_path, prompt, system=system))
