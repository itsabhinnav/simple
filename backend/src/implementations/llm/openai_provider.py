"""OpenAI Chat Completions VLM adapter."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Optional

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

    def _text_model(self) -> str:
        return resolve_config("openai", "text_model", default=None) or self._model

    def chat_text(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> str:
        msgs: list[Dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages or [])
        payload = {
            "model": self._text_model(),
            "messages": msgs,
            "temperature": float(kwargs.get("temperature", 0.2)),
        }
        try:
            data = self._post_chat(payload)
            choices = data.get("choices") or []
            if not choices:
                return ""
            return str(choices[0].get("message", {}).get("content", ""))
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"OpenAI unreachable: {exc}", self._text_model(), exc)

    def _embedding_model(self) -> str:
        return resolve_config("openai", "embedding_model", default="text-embedding-3-small")

    def embed_text(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self._base_url.rstrip('/')}/embeddings"
        headers = {"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}
        payload = {"model": self._embedding_model(), "input": list(texts)}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"OpenAI HTTP {exc.response.status_code}", self._embedding_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"OpenAI unreachable: {exc}", self._embedding_model(), exc)
        items = data.get("data") or []
        return [[float(x) for x in (item.get("embedding") or [])] for item in items]

    def embedding_dimension(self) -> Optional[int]:
        dim = resolve_config("openai", "embedding_dimension", default=None)
        try:
            return int(dim) if dim is not None else None
        except (TypeError, ValueError):
            return None

    def chat_text_stream(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> Iterator[str]:
        msgs: list[Dict[str, Any]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.extend(messages or [])
        payload = {
            "model": self._text_model(),
            "messages": msgs,
            "temperature": float(kwargs.get("temperature", 0.2)),
            "stream": True,
        }
        url = f"{self._base_url.rstrip('/')}/chat/completions"
        headers = {"Authorization": f"Bearer {self._api_key()}", "Content-Type": "application/json"}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream("POST", url, headers=headers, json=payload) as response:
                    response.raise_for_status()
                    for raw in response.iter_lines():
                        line = raw.strip() if isinstance(raw, str) else raw.decode("utf-8", "ignore").strip()
                        if not line or not line.startswith("data:"):
                            continue
                        body = line[5:].strip()
                        if body == "[DONE]":
                            break
                        try:
                            obj = json.loads(body)
                        except json.JSONDecodeError:
                            continue
                        delta = ((obj.get("choices") or [{}])[0].get("delta") or {}).get("content")
                        if delta:
                            yield str(delta)
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"OpenAI HTTP {exc.response.status_code}", self._text_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"OpenAI unreachable: {exc}", self._text_model(), exc)
