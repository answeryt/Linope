"""A configurable set of independent model compute cores."""

from __future__ import annotations

import threading
from typing import Any

from kernel.scheduler.model_scheduler.model import Model, ModelCard, _load_card


class Cores:
    """Own one model resource per configured core.

    The scheduler's ``Book`` decides which task gets a free core.  This
    object only owns the model instances and their common card.
    """

    def __init__(self, count: int = 1) -> None:
        self._lock = threading.RLock()
        self._models: list[Model] = []
        self.set_count(count)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._models)

    @property
    def models(self) -> tuple[Model, ...]:
        with self._lock:
            return tuple(self._models)

    @property
    def model(self) -> Model:
        """Compatibility access to the first model core."""

        with self._lock:
            if not self._models:
                raise RuntimeError("model_cores_empty")
            return self._models[0]

    @property
    def busy(self) -> bool:
        return any(model.busy for model in self.models)

    def model_for(self, core: int) -> Model:
        with self._lock:
            try:
                return self._models[int(core)]
            except (IndexError, ValueError) as exc:
                raise ValueError(f"Unknown model core: {core}") from exc

    def free_ids(self, book: Any) -> tuple[int, ...]:
        """Return free core ids in deterministic order."""

        used = set(book.using_cores())
        with self._lock:
            return tuple(
                index
                for index, model in enumerate(self._models)
                if index not in used and not model.busy
            )

    def set_count(self, count: int) -> dict[str, Any]:
        """Resize the pool while no model request is executing."""

        try:
            target = int(count)
        except (TypeError, ValueError) as exc:
            raise ValueError("Model core count must be an integer") from exc
        if target < 1:
            raise ValueError("Model core count must be at least 1")

        with self._lock:
            if any(model.busy for model in self._models):
                raise RuntimeError("model_busy")
            current = len(self._models)
            if target > current:
                card = self._models[0].card if self._models else None
                self._models.extend(
                    _new_model(card) for _ in range(target - current)
                )
            elif target < current:
                self._models = self._models[:target]
            return self.info()

    def use(
        self,
        capability: str,
        changes: tuple[tuple[str, str], ...] = (),
        *,
        env_file: str = "",
    ) -> dict[str, Any]:
        """Install one effective card on every model core."""

        with self._lock:
            if any(model.busy for model in self._models):
                raise RuntimeError("model_busy")
            card = _load_card(capability, changes, env_file=env_file)
            for model in self._models:
                model.install_card(card)
            return self.info()

    def run(self, body: Any, *, on_notice: Any = None) -> Any:
        """Run directly on the first currently free model core."""

        for model in self.models:
            if model.busy:
                continue
            try:
                return model.run(body, on_notice=on_notice)
            except RuntimeError as exc:
                if str(exc) != "model_busy":
                    raise
        raise RuntimeError("model_busy")

    def info(self) -> dict[str, Any]:
        with self._lock:
            if not self._models:
                return {"configured": False, "cores": 0}
            result = self._models[0].info()
            result["cores"] = len(self._models)
            return result


def _new_model(card: ModelCard | None) -> Model:
    model = Model()
    if card is not None:
        model.install_card(card)
    return model


_DEFAULT_CORES: Cores | None = None


def get_cores() -> Cores:
    """Return the process-wide model core pool."""

    global _DEFAULT_CORES
    if _DEFAULT_CORES is None:
        _DEFAULT_CORES = Cores()
    return _DEFAULT_CORES


__all__ = ["Cores", "get_cores"]
