from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from types import SimpleNamespace

from app.db.base import get_session, remove_session
from app.db.models import (
    Brand,
    Opportunity,
    Query,
    QuerySource,
    Run,
    RunStatus,
    VisibilityChannel,
    VisibilityObservation,
)
from app.services.run_service import RunAlreadyActiveError, create_run
from app.worker.callbacks import work_horse_killed


def test_simultaneous_run_requests_create_only_one_job(app, resilient_settings):
    session = get_session()
    brand = Brand(name="Concurrent brand", domain="example.com")
    session.add(brand)
    session.commit()
    brand_id = brand.id
    session.rollback()
    gate = Barrier(2)

    def request_run():
        own_session = get_session()
        try:
            own_brand = own_session.get(Brand, brand_id)
            gate.wait(timeout=10)
            run, _ = create_run(own_session, app.extensions["redis"], resilient_settings, own_brand)
            return "created", run.id
        except RunAlreadyActiveError as exc:
            return "active", exc.run_id
        finally:
            remove_session()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: request_run(), range(2)))
    assert sorted(status for status, _ in results) == ["active", "created"]
    assert results[0][1] == results[1][1]


def test_redis_enqueue_failure_does_not_leave_queued_run(client, monkeypatch):
    brand = client.post("/api/v1/brands", json={"name": "Queue check", "domain": "example.com"}).get_json()

    def unavailable(*_args, **_kwargs):
        raise ConnectionError("Redis unavailable")

    monkeypatch.setattr("rq.Queue.enqueue", unavailable)
    response = client.post(f"/api/v1/brands/{brand['id']}/runs")
    assert response.status_code == 500
    history = client.get(f"/api/v1/brands/{brand['id']}/runs").get_json()
    assert history["items"][0]["status"] == "failed"
    assert "enqueue" in history["items"][0]["error_summary"]


def test_channel_filter_is_applied_before_limit(client):
    session = get_session()
    brand = Brand(name="Channel check", domain="example.com")
    session.add(brand)
    session.flush()
    run = Run(brand_id=brand.id, status=RunStatus.SUCCEEDED)
    session.add(run)
    session.flush()
    for score, channel in [(90, VisibilityChannel.GOOGLE_ORGANIC), (20, VisibilityChannel.LLM_CHATGPT)]:
        query = Query(run_id=run.id, text=channel.value, source=QuerySource.LLM_PLANNER)
        session.add(query)
        session.flush()
        session.add(
            VisibilityObservation(
                query_id=query.id, channel=channel, brand_visible=False, competitors_visible=[], cited_urls=[]
            )
        )
        session.add(Opportunity(run_id=run.id, query_id=query.id, score=score, rank=1, components={}))
    session.commit()
    run_id = str(run.id)
    response = client.get(f"/api/v1/runs/{run_id}/opportunities?channel=llm_chatgpt&limit=1")
    assert response.status_code == 200
    assert [item["query_text"] for item in response.get_json()["items"]] == ["llm_chatgpt"]


def test_killed_worker_marks_an_active_run_failed(app):
    session = get_session()
    brand = Brand(name="Worker check", domain="example.com")
    session.add(brand)
    session.flush()
    run = Run(brand_id=brand.id, status=RunStatus.RUNNING)
    session.add(run)
    session.commit()
    run_id = run.id
    work_horse_killed(SimpleNamespace(args=[str(run_id)]), 1, 9, None)
    run = get_session().get(Run, run_id)
    assert run.status == RunStatus.FAILED
    assert "exited unexpectedly" in run.error_summary
