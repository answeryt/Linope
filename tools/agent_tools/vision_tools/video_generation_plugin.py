# -*- coding: utf-8 -*-
"""Text-to-video / image-to-video surface. Host injects the provider."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from typing import Any, Dict, List, Optional


PLUGIN_NAME = "video_generation"
PLUGIN_VERSION = "1.0"

COMMON_ASPECT_RATIOS = ("16:9", "9:16", "1:1", "4:3", "3:4")
COMMON_RESOLUTIONS = ("480p", "540p", "720p", "1080p")
DEFAULT_ASPECT_RATIO = "16:9"
DEFAULT_RESOLUTION = "720p"

GenerateFn = Callable[..., Any]


def error_response(error: str, error_type: str, **details: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "success": False,
        "error": error,
        "error_type": error_type,
    }
    payload.update(details)
    return payload


def tool_error(message: str, **details: Any) -> str:
    payload: Dict[str, Any] = {"success": False, "error": message}
    payload.update(details)
    return json.dumps(payload, ensure_ascii=False)


def _read_local_config() -> Dict[str, Any]:
    from pathlib import Path

    raw = os.getenv("OPEN_LINUX_CONFIG") or os.getenv("AGENT_CONFIG")
    candidates = []
    if raw:
        candidates.append(Path(raw))
    home = Path(os.getenv("OPEN_LINUX_HOME", Path.home() / ".open-linux")).expanduser()
    candidates.extend((home / "config.json", home / "config.yaml"))
    for candidate in candidates:
        try:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8")
            if candidate.suffix == ".json":
                data = json.loads(text)
                return data if isinstance(data, dict) else {}
            try:
                import yaml
            except ImportError:
                continue
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}


def _read_video_gen_section() -> Dict[str, Any]:
    cfg = _read_local_config()
    section = cfg.get("video_gen") if isinstance(cfg, dict) else None
    return section if isinstance(section, dict) else {}


def _read_configured_video_provider() -> Optional[str]:
    value = _read_video_gen_section().get("provider")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def check_video_generation_requirements(generate: GenerateFn | None = None) -> bool:
    return generate is not None or bool(_read_configured_video_provider())


def _coerce_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes", "on"}:
            return True
        if text in {"false", "0", "no", "off"}:
            return False
    return None


def _normalize_reference_images(value: Any) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return None
    out = [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return out or None


def video_generate(
    prompt: str,
    image_url: Optional[str] = None,
    reference_image_urls: Optional[List[str]] = None,
    duration: Optional[int] = None,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str = DEFAULT_RESOLUTION,
    negative_prompt: Optional[str] = None,
    audio: Optional[bool] = None,
    seed: Optional[int] = None,
    model: Optional[str] = None,
    generate: GenerateFn | None = None,
) -> str:
    text = (prompt or "").strip()
    if not text:
        return tool_error("prompt is required")
    if generate is None:
        configured = _read_configured_video_provider()
        if configured:
            return json.dumps(
                error_response(
                    error=(
                        f"video_gen.provider={configured!r} is set but the Host "
                        "has not injected a generator for that backend."
                    ),
                    error_type="provider_not_registered",
                    provider=configured,
                )
            )
        return json.dumps(
            error_response(
                error="No video generation backend is configured.",
                error_type="no_provider_configured",
            )
        )
    result = generate(
        prompt=text,
        image_url=image_url,
        reference_image_urls=reference_image_urls,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        negative_prompt=negative_prompt,
        audio=audio,
        seed=seed,
        model=model,
    )
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def _handle_video_generate(args: Dict[str, Any], **kwargs: Any) -> str:
    return video_generate(
        prompt=str(args.get("prompt") or ""),
        image_url=(str(args.get("image_url") or "").strip() or None),
        reference_image_urls=_normalize_reference_images(args.get("reference_image_urls")),
        duration=_coerce_int(args.get("duration")),
        aspect_ratio=(str(args.get("aspect_ratio") or DEFAULT_ASPECT_RATIO).strip() or DEFAULT_ASPECT_RATIO),
        resolution=(str(args.get("resolution") or DEFAULT_RESOLUTION).strip() or DEFAULT_RESOLUTION),
        negative_prompt=(str(args.get("negative_prompt") or "").strip() or None),
        audio=_coerce_bool(args.get("audio")),
        seed=_coerce_int(args.get("seed")),
        model=(str(args.get("model") or "").strip() or None),
        generate=kwargs.get("generate"),
    )


VIDEO_GENERATE_SCHEMA: Dict[str, Any] = {
    "name": "video_generate",
    "description": (
        "Generate a video from a text prompt, optionally driven by a still "
        "image or reference images. A Host-injected backend must be available."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Text instruction describing the desired video.",
            },
            "image_url": {
                "type": "string",
                "description": "Optional public HTTPS URL of a still image (image-to-video).",
            },
            "reference_image_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional public HTTPS reference image URLs.",
            },
            "duration": {"type": "integer", "description": "Requested duration in seconds."},
            "aspect_ratio": {
                "type": "string",
                "enum": list(COMMON_ASPECT_RATIOS),
                "description": "Aspect ratio.",
            },
            "resolution": {
                "type": "string",
                "enum": list(COMMON_RESOLUTIONS),
                "description": "Output resolution.",
            },
            "negative_prompt": {"type": "string"},
            "audio": {"type": "boolean"},
            "seed": {"type": "integer"},
            "model": {"type": "string"},
        },
        "required": ["prompt"],
    },
}
