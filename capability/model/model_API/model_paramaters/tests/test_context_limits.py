# -*- coding: utf-8 -*-
"""plugin-unit: load context_limits by file, never through Host."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


def _load():
    path = Path(__file__).resolve().parents[1] / "context_limits" / "context_limits.py"
    spec = importlib.util.spec_from_file_location("context_limits_leaf", path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ContextLimitsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.limits = _load()

    def test_prefers_the_longest_matching_model_name(self) -> None:
        self.assertEqual(
            self.limits.resolve_default_context_length("vendor/minimax-m3-latest"),
            1_000_000,
        )
        self.assertEqual(
            self.limits.resolve_default_context_length("MINIMAX-legacy"),
            204_800,
        )
        self.assertEqual(
            self.limits.resolve_default_context_length("claude-opus-5"),
            1_000_000,
        )

    def test_unknown_model_uses_fallback(self) -> None:
        self.assertEqual(
            self.limits.resolve_default_context_length("unknown-provider/model"),
            self.limits.DEFAULT_FALLBACK_CONTEXT,
        )

    def test_missing_context_length_is_filled_in_place(self) -> None:
        request = {"model": "gpt-4"}
        self.assertIsNone(self.limits.recover_missing_context_length(None, request))
        self.assertEqual(request["context_length"], 128_000)

    def test_probe_tier_returns_next_strictly_lower(self) -> None:
        cases = (
            (300_000, 256_000),
            (256_000, 128_000),
            (129_000, 128_000),
            (128_000, 64_000),
            (8_001, 8_000),
        )
        for current, expected in cases:
            with self.subTest(current=current):
                self.assertEqual(
                    self.limits.get_next_context_probe_tier(current),
                    expected,
                )
        self.assertIsNone(self.limits.get_next_context_probe_tier(8_000))

    def test_parses_supported_provider_error_formats(self) -> None:
        cases = (
            ("max_model_len is 65536", 65_536),
            ("Maximum model length is 131072", 131_072),
            ("context window: 262144", 262_144),
            ("Request exceeds 128000 token context", 128_000),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    self.limits.parse_context_limit_from_error(message),
                    expected,
                )

    def test_rejects_missing_or_unreasonable_limits(self) -> None:
        self.assertIsNone(self.limits.parse_context_limit_from_error("request failed"))
        self.assertIsNone(self.limits.parse_context_limit_from_error("context window: 512"))
        self.assertIsNone(
            self.limits.parse_context_limit_from_error("context window: 10000001")
        )

    def test_only_resolves_a_lower_limit(self) -> None:
        error = "maximum context length is 131072"
        self.assertEqual(
            self.limits.resolve_lower_context_limit_from_error(error, 256_000),
            131_072,
        )
        self.assertIsNone(
            self.limits.resolve_lower_context_limit_from_error(error, 128_000)
        )

    def test_parses_supported_output_limit_errors(self) -> None:
        cases = (
            ("range of max_tokens should be [1, 4096]", 4_096),
            ("max_tokens exceeds available_tokens: 2048", 2_048),
            ("max_tokens exceeds available tokens 1024", 1_024),
            (
                "maximum context length is 10000 "
                "(6000 of text input, 1000 of tool input, 4000 in the output)",
                3_000,
            ),
        )
        for message, expected in cases:
            with self.subTest(message=message):
                self.assertEqual(
                    self.limits.parse_available_output_tokens_from_error(message),
                    expected,
                )

    def test_identifies_output_cap_without_input_overflow(self) -> None:
        self.assertTrue(
            self.limits.is_output_cap_error(
                "max_tokens should be less than or equal to 4096"
            )
        )
        self.assertFalse(
            self.limits.is_output_cap_error(
                "max_tokens is invalid because the prompt is too long"
            )
        )
        self.assertIsNone(
            self.limits.parse_available_output_tokens_from_error("prompt is too long")
        )


if __name__ == "__main__":
    unittest.main()
