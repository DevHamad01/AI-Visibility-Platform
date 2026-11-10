"""Streaming must release connections and close on a persisted terminal state."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from app.api.sse import run_events_stream


def test_sse_releases_each_poll_and_finishes_after_terminal_event(monkeypatch):
    session = Mock()
    session.get.side_effect = [
        SimpleNamespace(status=SimpleNamespace(value="running"), progress={}),
        SimpleNamespace(status=SimpleNamespace(value="failed"), progress={}),
    ]
    session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
    release = Mock()
    monkeypatch.setattr("app.api.sse.get_session", lambda: session)
    monkeypatch.setattr("app.api.sse.remove_session", release)
    monkeypatch.setattr("app.api.sse.time.sleep", lambda _: None)
    stream = run_events_stream(uuid4())
    first = next(stream)
    assert release.call_count == 1  # Before the caller consumes the event.
    assert json.loads(first.removeprefix("data: "))["status"] == "running"
    rest = list(stream)
    assert release.call_count == 2
    assert json.loads(rest[0].removeprefix("data: "))["status"] == "failed"
