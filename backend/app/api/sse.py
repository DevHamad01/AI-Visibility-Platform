"""GET /runs/{id}/events: polls `run_stages` and streams changes as
Server-Sent Events until the run reaches a terminal status. Flask/gunicorn
sync workers hold the connection open for the duration — fine at this
project's scale; the frontend's nginx proxy disables buffering for this
route (Phase 4) so updates aren't held back in a buffer.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator

from app.db.base import get_session
from app.db.models import Run, RunStage

TERMINAL_STATUSES = {"succeeded", "partial", "failed"}


def _event(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def run_events_stream(
    run_id: uuid.UUID, *, poll_interval: float = 1.0, max_duration: float = 600.0
) -> Iterator[str]:
    session = get_session()
    start = time.monotonic()
    last_payload: dict | None = None

    while True:
        session.expire_all()
        run = session.get(Run, run_id)
        if run is None:
            yield _event({"error": "run not found"})
            return

        stages = session.query(RunStage).filter(RunStage.run_id == run_id).order_by(RunStage.id).all()
        payload = {
            "status": run.status.value,
            "progress": run.progress,
            "stages": [
                {
                    "stage": s.stage,
                    "status": s.status.value,
                    "attempts": s.attempts,
                    "duration_ms": s.duration_ms,
                    "error_type": s.error_type,
                }
                for s in stages
            ],
        }
        if payload != last_payload:
            yield _event(payload)
            last_payload = payload

        if run.status.value in TERMINAL_STATUSES:
            return
        if time.monotonic() - start > max_duration:
            yield _event({"warning": "stream timed out — the run may still be in progress"})
            return
        time.sleep(poll_interval)
