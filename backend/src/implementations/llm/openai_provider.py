"""OpenAI Chat Completions VLM adapter."""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.implementations.llm._base import coerce_json, encode_image_b64, resolve_config
from src.infrastructure.logging_config import get_logger
from src.interfaces.llm_provider import VLMProvider, VLMProviderError

logger = get_logger(__name__)


_RETRYABLE = (httpx.HTTPError, httpx.TransportError)


class OpenAIProvider(VLMProvider):
    """Adapter for OpenAI gpt-4o-mini and compatible vision-capable models."""

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, timeout: float = 60.0):
        self._base_url = base_url or resolve_config("openai", "base_url", default="https://api.openai.com/v1")
        self._model = model or resolve_config("openai", "model", default="gpt-4o-mini")
        self._timeout = timeout

    def name(self) -> str:
        return "openai"

    def _api_key(self) -> str:
        key = resolve_config("openai", "api_key", env_var="OPENAI_API_KEY", default=None)
        if not key:
            raise VLMProviderError(self.name(), "Missing OPENAI_API_KEY", self._model)
        return str(key)

    @retry(
        reraise=True,
        retry=retry_if_exception_type(_RETRYABLE),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4.0),
    )
    def _post_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key()}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"OpenAI HTTP {exc.response.status_code}", self._model, exc)

    def _build_messages(self, prompt: str, image_b64: str, system: Optional[str]) -> list[Dict[str, Any]]:
        messages: list[Dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        )
        return messages

    def _call(self, image_path: str, prompt: str, system: Optional[str] = None) -> str:
        b64 = encode_image_b64(image_path)
        payload = {
            "model": self._model,
            "messages": self._build_messages(prompt, b64, system),
            "temperature": 0.0,
        }
        try:
            data = self._post_chat(payload)
            choices = data.get("choices") or []
            if not choices:
                return ""
            return str(choices[0].get("message", {}).get("content", ""))
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"OpenAI unreachable: {exc}", self._model, exc)

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
