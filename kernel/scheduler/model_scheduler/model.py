"""The model as a CPU-like kernel resource.

This module deliberately does not create a process.  A ``Model`` owns the
currently selected provider card and executes one request supplied by a task
that has been granted the model scheduler's run queue.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

Notice = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ModelCard:
    """One installed provider card and its effective call parameters."""

    capability: str
    card_id: str
    provider: str
    model: str
    context_limit: int
    call_params: dict[str, Any] = field(default_factory=dict)
    api_key_env: str = ""
    env_file: str = ""

    def params(self) -> dict[str, Any]:
        return dict(self.call_params)


class Model:
    """One independent model compute core."""

    def __init__(self) -> None:
        self._card: ModelCard | None = None
        self._running = False
        self._lock = threading.RLock()

    @property
    def card(self) -> ModelCard | None:
        with self._lock:
            return self._card

    @property
    def context_limit(self) -> int:
        card = self.card
        return 0 if card is None else card.context_limit

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._running

    def use(
        self,
        capability: str,
        changes: tuple[tuple[str, str], ...] = (),
        *,
        env_file: str = "",
    ) -> dict[str, Any]:
        """Install a card while no model request is executing."""

        with self._lock:
            if self._running:
                raise RuntimeError("model_busy")
            card = _load_card(capability, changes, env_file=env_file)
            self.install_card(card)
            return self.info()

    def install_card(self, card: ModelCard) -> None:
        """Install an already resolved card on this idle core."""

        with self._lock:
            if self._running:
                raise RuntimeError("model_busy")
            self._card = ModelCard(
                capability=card.capability,
                card_id=card.card_id,
                provider=card.provider,
                model=card.model,
                context_limit=card.context_limit,
                call_params=card.params(),
                api_key_env=card.api_key_env,
                env_file=card.env_file,
            )

    def info(self) -> dict[str, Any]:
        card = self.card
        if card is None:
            return {"configured": False}
        return {
            "configured": True,
            "capability": card.capability,
            "card": card.card_id,
            "provider": card.provider,
            "model": card.model,
            "context_limit": card.context_limit,
        }

    def run(self, body: Any, *, on_notice: Notice | None = None) -> Any:
        """Execute one message on the installed card."""

        with self._lock:
            card = self._card
            if card is None:
                raise RuntimeError("model_not_configured")
            if self._running:
                raise RuntimeError("model_busy")
            self._running = True
        try:
            params = card.params()
            if card.env_file and card.api_key_env:
                params["api_key"] = _read_secret(card.env_file, card.api_key_env)
            from capability.model.model_runtime.model_main import load_named_card_async

            return asyncio.run(
                load_named_card_async(
                    card.card_id,
                    "message",
                    body,
                    params,
                    on_notice=on_notice,
                )
            )
        finally:
            with self._lock:
                self._running = False


def get_model() -> Model:
    """Return the first model core for compatibility callers."""

    from kernel.scheduler.model_scheduler.cores import get_cores

    return get_cores().model


def _load_card(
    capability: str,
    changes: tuple[tuple[str, str], ...],
    *,
    env_file: str,
) -> ModelCard:
    name = str(capability or "").strip()
    if not name.startswith("model.") or not name.split(".", 1)[1]:
        raise ValueError(f"Unknown model card: {capability}")
    plugin_name = name.split(".", 1)[1]
    module = importlib.import_module(
        f"capability.model.model_provider.{plugin_name}.{plugin_name}_plugin"
    )
    raw = getattr(module, "CARD_CONFIG", None)
    if not isinstance(raw, dict):
        raise ValueError(f"Model card is unavailable: {capability}")
    from capability.model.model_provider.card_profile import declaration_from_card

    configured = declaration_from_card(capability, raw, changes)
    return ModelCard(
        capability=configured.capability,
        card_id=configured.card_id,
        provider=configured.provider,
        model=configured.model,
        context_limit=configured.context_limit,
        call_params=configured.call_params,
        api_key_env=configured.api_key_env,
        env_file=str(env_file or ""),
    )


def _read_secret(path: str, name: str) -> str:
    if not path:
        value = os.environ.get(name, "")
    else:
        value = ""
        try:
            lines = Path(path).read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise RuntimeError(f"Environment has no such secret: {name}") from exc
        for raw in lines:
            key, separator, candidate = raw.partition("=")
            if separator and key.strip() == name:
                value = candidate.strip().strip("'").strip('"')
                break
    if not value:
        raise RuntimeError(f"Environment has no such secret: {name}")
    return value


__all__ = ["Model", "ModelCard", "get_model"]
