"""Trace ids relate steps. A failed exporter does not change the task."""

import pytest

from kernel.trace import FailingExporter, MemoryExporter, Span, parse_traceparent, root_context, set_exporter


def test_a_child_span_keeps_the_trace_and_names_its_parent() -> None:
    root = root_context()
    child = root.child()
    assert child.trace_id == root.trace_id
    assert child.parent_span_id == root.span_id
    assert child.span_id != root.span_id
    parsed = parse_traceparent(child.traceparent())
    assert parsed.trace_id == child.trace_id
    assert parsed.span_id == child.span_id


def test_a_bad_traceparent_is_rejected() -> None:
    with pytest.raises(ValueError):
        parse_traceparent("00-" + "0" * 32 + "-" + "ab" * 8 + "-01")


def test_exporter_failure_is_recorded_on_the_span() -> None:
    set_exporter(FailingExporter())
    try:
        record = Span("start_model", root_context()).finish()
    finally:
        set_exporter(MemoryExporter())
    assert record["exported"] is False
    assert record["status"] == "ok"
