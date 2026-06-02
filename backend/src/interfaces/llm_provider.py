"""Pluggable VLM/LLM provider interface and registry."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional

from src.infrastructure.logging_config import get_logger
from src.services.parsing.models import VLMError, VLMRequest, VLMResponse, VLMUsage

logger = get_logger(__name__)


__all__ = [
    "VLMProvider",
    "VLMRegistry",
    "VLMProviderError",
    "VLMRequest",
    "VLMResponse",
    "VLMError",
    "VLMUsage",
    "get_vlm_registry",
]


class VLMProviderError(Exception):
    """Raised when a VLM provider fails or is unavailable."""

    def __init__(self, provider: str, message: str, model: Optional[str] = None, cause: Optional[Exception] = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.model = model
        self.message = message
        self.cause = cause

    def as_error(self) -> VLMError:
        return VLMError(
            provider=self.provider,
            model=self.model,
            message=self.message,
            cause=repr(self.cause) if self.cause else None,
        )


class VLMProvider(ABC):
    """Abstract base for pluggable Vision-Language Model providers."""

    @abstractmethod
    def name(self) -> str:
        """Return the lowercase provider name (e.g. "ollama")."""

    @abstractmethod
    def caption_image(self, image_path: str, prompt: str, context: Optional[str] = None) -> str:
        """Return a free-form caption / description string for the image."""

    @abstractmethod
    def describe_layout(self, image_path: str, prompt: str) -> Dict[str, Any]:
        """Return a structured description of layout regions."""

    @abstractmethod
    def extract_structured(self, image_path: str, prompt: str, schema_hint: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured data from the image guided by a schema hint."""

    def invoke(self, request: VLMRequest) -> VLMResponse:
        """Generic invocation that defaults to extract_structured."""
        schema_hint = request.schema_hint or {}
        try:
            parsed = self.extract_structured(request.image_path, request.prompt, schema_hint)
            return VLMResponse(
                provider=self.name(),
                model=request.model or "default",
                parsed=parsed if isinstance(parsed, dict) else {"value": parsed},
                raw_text=str(parsed),
            )
        except VLMProviderError as exc:
            return VLMResponse(
                provider=self.name(),
                model=request.model or "default",
                skipped=True,
                error=exc.message,
            )


ProviderFactory = Callable[[], VLMProvider]


class VLMRegistry:
    """Process-wide registry for VLM provider factories (singleton)."""

    _instance: Optional["VLMRegistry"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        self._factories: Dict[str, ProviderFactory] = {}
        self._cache: Dict[str, VLMProvider] = {}
        self._default: Optional[str] = None
        self._configured: bool = False

    @classmethod
    def instance(cls) -> "VLMRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, factory: ProviderFactory) -> None:
        key = name.lower()
        self._factories[key] = factory
        self._cache.pop(key, None)
        logger.info(f"Registered VLM provider: {key}")

    def list_providers(self) -> List[str]:
        return sorted(self._factories.keys())

    def has(self, name: str) -> bool:
        return name.lower() in self._factories

    def set_default(self, name: str) -> None:
        key = name.lower()
        if key not in self._factories:
            raise VLMProviderError(key, f"Unknown VLM provider '{name}'")
        self._default = key

    def get_default_name(self) -> Optional[str]:
        return self._default

    def get(self, name: Optional[str] = None) -> VLMProvider:
        key = (name or self._default or "").lower()
        if not key:
            raise VLMProviderError("registry", "No default VLM provider configured")
        if key not in self._factories:
            raise VLMProviderError(key, f"Unknown VLM provider '{name}'")
        if key not in self._cache:
            self._cache[key] = self._factories[key]()
        return self._cache[key]

    def configure_from_config(self, config_manager: Any) -> None:
        """Read parsing.vlm.* keys and set the default provider."""
        if self._configured:
            return
        default = config_manager.get_config("parsing.vlm.default_provider", "ollama")
        try:
            if default and default.lower() in self._factories:
                self.set_default(default)
            elif self._factories:
                self.set_default(next(iter(sorted(self._factories.keys()))))
        except VLMProviderError as exc:
            logger.warning(f"VLM registry default not applied: {exc.message}")
        self._configured = True

    def reset(self) -> None:
        self._factories.clear()
        self._cache.clear()
        self._default = None
        self._configured = False


def get_vlm_registry() -> VLMRegistry:
    """Convenience accessor for the singleton."""
    return VLMRegistry.instance()
