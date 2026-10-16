"""Live model fragments reach the terminal before the final reply."""

from kernel.command.live_stream import (
    StreamTail,
    bind_stream_keys,
    publish_text,
    reset_emitter,
    reset_stream_keys,
    use_emitter,
)
from capability.model.model_runtime.model_main import _forward_display


def test_a_bound_request_receives_text_as_it_is_produced(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "kernel.command.live_stream.stream_path",
        lambda key: tmp_path / f"{key}.jsonl",
    )
    seen: list[str] = []
    token = bind_stream_keys(("task-1",))
    tail = StreamTail("task-1", lambda event: seen.append(str(event.get("text") or "")))
    tail.start()
    try:
        _forward_display({"type": "text-delta", "text": "一致"})
        _forward_display({"type": "tool-call-delta", "text": "ignored"})
        _forward_display({"type": "text-delta", "text": "性"})
        assert tail.finish() == "一致性"
    finally:
        reset_stream_keys(token)
    assert seen == ["一致", "性"]


def test_the_follower_uses_the_caller_emitter_on_its_own_thread(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "kernel.command.live_stream.stream_path",
        lambda key: tmp_path / f"{key}.jsonl",
    )
    seen: list[dict] = []
    token = use_emitter(seen.append)
    keys = bind_stream_keys(("task-2",))
    tail = StreamTail("task-2")
    tail.start()
    try:
        publish_text("流式")
        assert tail.finish() == "流式"
    finally:
        reset_stream_keys(keys)
        reset_emitter(token)
    assert seen == [{"type": "text-delta", "text": "流式"}]


def test_publish_without_a_key_is_silent(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(
        "kernel.command.live_stream.stream_path",
        lambda key: tmp_path / f"{key}.jsonl",
    )
    publish_text("不会落下")
    assert list(tmp_path.iterdir()) == []
