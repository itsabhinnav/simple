"""Anthropic Messages API VLM adapter."""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.implementations.llm._base import coerce_json, encode_image_b64, resolve_config
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProvider, VLMProviderError

logger = get_logger(__name__)


_RETRYABLE = (httpx.HTTPError, httpx.TransportError)


class AnthropicProvider(VLMProvider):
    """Adapter for Anthropic Claude vision-capable models."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
        api_version: str = "2023-06-01",
    ):
        self._base_url = base_url or resolve_config("anthropic", "base_url", default="https://api.anthropic.com")
        self._model = model or resolve_config("anthropic", "model", default="claude-3-5-sonnet-latest")
        self._timeout = timeout
        self._api_version = api_version

    def name(self) -> str:
        return "anthropic"

    def _api_key(self) -> str:
        key = resolve_config("anthropic", "api_key", env_var="ANTHROPIC_API_KEY", default=None)
        if not key:
            raise VLMProviderError(self.name(), "Missing ANTHROPIC_API_KEY", self._model)
        return str(key)

    @retry(
        reraise=True,
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    )
    def _post_messages(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self._api_key(),
            "anthropic-version": self._api_version,
            "content-type": "application/json",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"Anthropic HTTP {exc.response.status_code}", self._model, exc)

    def _call(self, image_path: str, prompt: str, system: Optional[str] = None) -> str:
        b64 = encode_image_b64(image_path)
        payload: Dict[str, Any] = {
            "model": self._model,
            "max_tokens": 1024,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        }
        if system:
            payload["system"] = system
        try:
            data = self._post_messages(payload)
            content = data.get("content") or []
            text_parts = [chunk.get("text", "") for chunk in content if chunk.get("type") == "text"]
            return "".join(text_parts)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Anthropic unreachable: {exc}", self._model, exc)

    def caption_image(self, image_path: str, prompt: str, context: Optional[str] = None) -> str:
        full_prompt = f"{prompt}\n\nContext:\n{context}" if context else prompt
        return self._call(image_path, full_prompt)

    def describe_layout(self, image_path: str, prompt: str) -> Dict[str, Any]:
        system = "Respond in JSON describing detected layout regions (header, table, image, footer)."
        return coerce_json(self._call(image_path, prompt, system=system))

    def extract_structured(self, image_path: str, prompt: str, schema_hint: Dict[str, Any]) -> Dict[str, Any]:
        system = (
            "Respond ONLY with JSON matching the provided schema hint. "
            f"Schema hint: {schema_hint}"
        )
        return coerce_json(self._call(image_path, prompt, system=system))

    def _text_model(self) -> str:
        return resolve_config("anthropic", "text_model", default=None) or self._model

    def chat_text(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> str:
        normalized = [
            {"role": m.get("role", "user"), "content": [{"type": "text", "text": str(m.get("content", ""))}]}
            for m in (messages or [])
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        payload: Dict[str, Any] = {
            "model": self._text_model(),
            "max_tokens": int(kwargs.get("max_tokens", 1024)),
            "messages": normalized,
            "temperature": float(kwargs.get("temperature", 0.2)),
        }
        if system:
            payload["system"] = system
        try:
            data = self._post_messages(payload)
            content = data.get("content") or []
            text_parts = [chunk.get("text", "") for chunk in content if chunk.get("type") == "text"]
            return "".join(text_parts)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Anthropic unreachable: {exc}", self._text_model(), exc)

    def chat_text_stream(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> Iterator[str]:
        yield self.chat_text(messages, system=system, **kwargs)
