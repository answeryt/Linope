# Semantic compression atomic functions

This directory contains small deterministic compression functions extracted from
the root `context_compression.py` design. The root script and `model/token`
modules are intentionally untouched.

These files are not compose-discovered capability plugins yet. The Host imports
and wires the needed functions explicitly.

## Contracts

- Message transformations accept and return `list[dict]`.
- No function imports another project module or another function in this directory.
- No function imports `sliding_window` or `summary_compression`.
- Token counting is not implemented here. The Host injects
  `estimate_messages(list[dict]) -> int`.
- Summaries, markers, selection rules and policy decisions can be injected.
- A no-op normally returns the original list object, allowing the Host to
  detect committed rewrites by identity.
- Functions shallow-copy only rewritten messages/calls and do not mutate input.

## Atomic functions

- `tool_result_dedup.py`: keeps the newest full copy of identical string tool
  results and replaces older copies with a back-reference.
- `tool_result_summary.py`: safe one-line summaries for common tools plus a
  never-raise fallback; also exposes callback-driven result replacement.
- `json_args_truncation.py`: recursively truncates string leaves after parsing
  JSON, preserving valid JSON and leaving malformed arguments unchanged.
- `old_tool_result_demotion.py`: demotes Host-selected old results using
  injected summary, image and protection callbacks.
- `protected_tail_pressure.py`: demotes protected-tail results until an
  injected estimator reports that the tail is below its soft limit.
- `proactive_prune_gate.py`: applies trigger, eligibility and measured reclaim
  gates before committing a prompt-cache-breaking proactive prune.
- `tool_pair_sanitizer.py`: removes orphan tool results and strips tool calls
  that have no matching result.
- `media_stripping.py`: replaces image parts and strips images older than the
  newest image-bearing user message.
- `skill_view_guard.py`: recognizes `skill_view` calls, computes protected skill
  names, creates a demotion-protection callback and collects ghost markers.
- `deterministic_pipeline.py`: optional callback-only multi-pass runner. It
  imports no plugin and contains no policy.

## Host composition

The future Host owns configuration and imports the desired functions. It
should create closures for boundaries and policies, then pass them to the
callback-only pipeline in this typical order:

1. Deduplicate tool results.
2. Compute the protected-tail boundary.
3. Build `skill_view` protection from the original/current messages.
4. Demote old tool results outside the boundary.
5. Truncate old JSON tool arguments.
6. Run protected-tail pressure demotion with the Host estimator.
7. Sanitize tool call/result pairs.
8. Strip historical media.
9. Collect ghost-skill markers before semantic summarization and inject any
   missing markers into the Host-produced summary.

The proactive path should build steps 1, 4 and 5 as a candidate inside
`commit_proactive_prune`. That plugin estimates the actual before/after lists
and returns the original object unless the reclaim threshold is met.

Example Host wiring (illustrative only):

```python
passes = [
    deduplicate_tool_results,
    lambda rows: demote_old_tool_results(
        rows,
        should_demote=lambda index, _row: index < protected_start,
        summary_callback=default_tool_result_summary,
        protect_callback=skill_protection,
    ),
    lambda rows: truncate_tool_call_arguments(
        rows,
        should_truncate=lambda index, _row: index < protected_start,
    ),
    lambda rows: demote_protected_tail_under_pressure(
        rows,
        protected_start=protected_start,
        soft_token_limit=tail_limit,
        estimate_messages=host_estimator,
        summary_callback=default_tool_result_summary,
    ),
    sanitize_tool_pairs,
    strip_historical_media,
]
compressed = run_deterministic_pipeline(messages, passes=passes)
```

The names in this example are deliberately not re-exported through an
`__init__`, facade or host module. The Host imports each atomic plugin directly.
