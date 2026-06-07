"""Ollama local VLM adapter — HTTP via httpx."""

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

    def _text_model(self) -> str:
        """Resolve the text-chat model, falling back to the VLM if no text-only
        model is configured. Ollama is happy serving a vision-capable model
        for pure text, just at higher cost."""
        return resolve_config("ollama", "text_model", default=None) or self._model

    def chat_text(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> str:
        url = f"{self._base_url.rstrip('/')}/api/chat"
        payload: Dict[str, Any] = {
            "model": self._text_model(),
            "stream": False,
            "messages": list(messages or []),
            "options": {"temperature": float(kwargs.get("temperature", 0.2))},
        }
        if system:
            payload["messages"] = [{"role": "system", "content": system}, *payload["messages"]]
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            msg = (data.get("message") or {}).get("content", "")
            return str(msg)
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"Ollama HTTP {exc.response.status_code}", self._text_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Ollama unreachable: {exc}", self._text_model(), exc)

    # ------------------------------------------------------------------
    # Embeddings (used by the RAG vector index)
    # ------------------------------------------------------------------
    def _embedding_model(self) -> str:
        return resolve_config("ollama", "embedding_model", default="nomic-embed-text")

    def embed_text(self, texts: List[str], **kwargs: Any) -> List[List[float]]:
        if not texts:
            return []
        url = f"{self._base_url.rstrip('/')}/api/embed"
        payload = {"model": self._embedding_model(), "input": list(texts)}
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
            embeddings = data.get("embeddings") or []
            if embeddings:
                return [list(map(float, vec)) for vec in embeddings]
            # /api/embed was added in newer Ollama releases; old daemons only
            # expose /api/embeddings (singular) which takes one prompt at a
            # time. Fall back if the new endpoint returned nothing usable.
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise VLMProviderError(self.name(), f"Ollama HTTP {exc.response.status_code}", self._embedding_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Ollama unreachable: {exc}", self._embedding_model(), exc)

        legacy_url = f"{self._base_url.rstrip('/')}/api/embeddings"
        out: List[List[float]] = []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                for text in texts:
                    resp = client.post(legacy_url, json={"model": self._embedding_model(), "prompt": text})
                    resp.raise_for_status()
                    body = resp.json()
                    vec = body.get("embedding") or []
                    out.append([float(x) for x in vec])
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"Ollama HTTP {exc.response.status_code}", self._embedding_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Ollama unreachable: {exc}", self._embedding_model(), exc)
        return out

    def embedding_dimension(self) -> Optional[int]:
        dim = resolve_config("ollama", "embedding_dimension", default=None)
        try:
            return int(dim) if dim is not None else None
        except (TypeError, ValueError):
            return None

    def chat_text_stream(self, messages: List[Dict[str, Any]], system: Optional[str] = None, **kwargs: Any) -> Iterator[str]:
        url = f"{self._base_url.rstrip('/')}/api/chat"
        payload: Dict[str, Any] = {
            "model": self._text_model(),
            "stream": True,
            "messages": list(messages or []),
            "options": {"temperature": float(kwargs.get("temperature", 0.2))},
        }
        if system:
            payload["messages"] = [{"role": "system", "content": system}, *payload["messages"]]
        try:
            with httpx.Client(timeout=self._timeout) as client:
                with client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        chunk = (obj.get("message") or {}).get("content", "")
                        if chunk:
                            yield chunk
                        if obj.get("done"):
                            break
        except httpx.HTTPStatusError as exc:
            raise VLMProviderError(self.name(), f"Ollama HTTP {exc.response.status_code}", self._text_model(), exc)
        except _RETRYABLE as exc:
            raise VLMProviderError(self.name(), f"Ollama unreachable: {exc}", self._text_model(), exc)
