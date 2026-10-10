"""Load and validate user-owned system-prompt compression parameter cards."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


PARAMETERS_DIRECTORY = (
    Path(__file__).resolve().parents[2]
    / "prompt_card"
    / "prompt_paramaters"
    / "system_prompt_paramaters"
)
PARAMETERS_BASENAME = "system_prompt_paramaters"
SUPPORTED_PARAMETER_FORMATS = ("json", "toml", "yaml")
PARAMETERS_PATH_ENV = "SYSTEM_PROMPT_PARAMETERS_PATH"
PARAMETERS_FORMAT_ENV = "SYSTEM_PROMPT_PARAMETERS_FORMAT"


class SystemPromptCompressionError(RuntimeError):
    """System-prompt parameter configuration or compression failed."""


@dataclass(frozen=True, slots=True)
class SystemPromptCompressionParameters:
    """Validated user-owned system-prompt compression parameters."""

    enabled: bool
    max_chars: int
    chars_per_token: int
    context_window_fraction: float
    max_dynamic_chars: int
    head_ratio: float
    tail_ratio: float

    def __post_init__(self) -> None:
        if not isinstance(self.enabled, bool):
            raise SystemPromptCompressionError("enabled must be a boolean")
        _require_positive_int("max_chars", self.max_chars)
        _require_positive_int("chars_per_token", self.chars_per_token)
        _require_positive_int("max_dynamic_chars", self.max_dynamic_chars)
        if self.max_dynamic_chars < self.max_chars:
            raise SystemPromptCompressionError(
                "max_dynamic_chars must not be below max_chars"
            )
        if (
            isinstance(self.context_window_fraction, bool)
            or not isinstance(self.context_window_fraction, (int, float))
            or not 0 < self.context_window_fraction <= 1
        ):
            raise SystemPromptCompressionError(
                "context_window_fraction must be a number in (0, 1]"
            )
        for name, value in (
            ("head_ratio", self.head_ratio),
            ("tail_ratio", self.tail_ratio),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or value < 0
            ):
                raise SystemPromptCompressionError(
                    f"{name} must be a non-negative number"
                )
        if self.head_ratio + self.tail_ratio <= 0:
            raise SystemPromptCompressionError(
                "at least one retention ratio must be positive"
            )

    def as_mapping(self) -> dict[str, Any]:
        """Return a dependency-neutral mapping for a compressor plugin."""

        return asdict(self)


def _require_positive_int(name: str, value: Any) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SystemPromptCompressionError(f"{name} must be a positive integer")


def parameters_from_mapping(
    values: Mapping[str, Any],
) -> SystemPromptCompressionParameters:
    """Validate a decoded parameter mapping and return its typed form."""

    expected = {
        "enabled",
        "max_chars",
        "chars_per_token",
        "context_window_fraction",
        "max_dynamic_chars",
        "head_ratio",
        "tail_ratio",
    }
    unknown = set(values) - expected
    missing = expected - set(values)
    if unknown:
        raise SystemPromptCompressionError(
            f"Unknown compression parameters: {', '.join(sorted(unknown))}"
        )
    if missing:
        raise SystemPromptCompressionError(
            f"Missing compression parameters: {', '.join(sorted(missing))}"
        )
    if any(values[name] == "UNSET" for name in expected):
        raise SystemPromptCompressionError(
            "Compression parameters cannot be UNSET; configure every field"
        )
    return SystemPromptCompressionParameters(
        enabled=values["enabled"],
        max_chars=values["max_chars"],
        chars_per_token=values["chars_per_token"],
        context_window_fraction=values["context_window_fraction"],
        max_dynamic_chars=values["max_dynamic_chars"],
        head_ratio=values["head_ratio"],
        tail_ratio=values["tail_ratio"],
    )


def resolve_parameters_path(
    context: Mapping[str, Any] | None = None,
) -> Path:
    """Resolve the user-selected JSON, TOML, or YAML parameter card."""

    values = context or {}
    explicit = values.get("system_prompt_parameters_path") or os.getenv(
        PARAMETERS_PATH_ENV
    )
    if explicit:
        return Path(str(explicit)).expanduser().resolve()

    selected_format = values.get("system_prompt_parameters_format") or os.getenv(
        PARAMETERS_FORMAT_ENV, "json"
    )
    normalized_format = str(selected_format).lower().lstrip(".")
    if normalized_format == "yml":
        normalized_format = "yaml"
    if normalized_format not in SUPPORTED_PARAMETER_FORMATS:
        raise SystemPromptCompressionError(
            "system prompt parameter format must be json, toml, or yaml"
        )
    return PARAMETERS_DIRECTORY / f"{PARAMETERS_BASENAME}.{normalized_format}"


def load_system_prompt_compression_parameters(
    path: str | Path,
) -> SystemPromptCompressionParameters:
    """Deserialize and validate one JSON, TOML, or YAML parameter card."""

    parameter_path = Path(path).expanduser().resolve()
    if not parameter_path.is_file():
        raise SystemPromptCompressionError(
            f"System prompt parameter card does not exist: {parameter_path}"
        )
    try:
        suffix = parameter_path.suffix.lower()
        if suffix == ".json":
            values = json.loads(parameter_path.read_text(encoding="utf-8-sig"))
        elif suffix == ".toml":
            import tomllib

            with parameter_path.open("rb") as stream:
                values = tomllib.load(stream)
        elif suffix in {".yaml", ".yml"}:
            try:
                import yaml
            except ImportError as exc:
                raise SystemPromptCompressionError(
                    "PyYAML is required to load YAML parameter cards"
                ) from exc
            values = yaml.safe_load(parameter_path.read_text(encoding="utf-8-sig"))
        else:
            raise SystemPromptCompressionError(
                f"Unsupported parameter card format: {parameter_path.suffix}"
            )
    except SystemPromptCompressionError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        raise SystemPromptCompressionError(
            f"Could not parse system prompt parameter card: {parameter_path}"
        ) from exc

    if not isinstance(values, Mapping):
        raise SystemPromptCompressionError(
            "System prompt parameter card must contain a mapping"
        )
    return parameters_from_mapping(values)


__all__ = [
    "PARAMETERS_BASENAME",
    "PARAMETERS_DIRECTORY",
    "PARAMETERS_FORMAT_ENV",
    "PARAMETERS_PATH_ENV",
    "SUPPORTED_PARAMETER_FORMATS",
    "SystemPromptCompressionError",
    "SystemPromptCompressionParameters",
    "load_system_prompt_compression_parameters",
    "parameters_from_mapping",
    "resolve_parameters_path",
]
