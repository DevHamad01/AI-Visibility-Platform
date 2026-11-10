"""One-off, real-provider failure demonstration for an existing brand.

docker compose run --rm -e DEMO_FAIL_SERP=true api python -m app.pipeline.failure_demo BRAND_ID

Does not enqueue a competing job or change the normal worker's configuration.
Other providers remain live and budgeted. A verified account is required for
useful partial results; an unverified account still produces an honest failure.
"""

from __future__ import annotations

import sys
import uuid

from app.core.config import get_settings
from app.db.base import get_session, init_engine, remove_session
from app.db.models import Brand, Run
from app.pipeline.runner import execute_run
from app.services.run_service import brand_snapshot


def main():
    settings = get_settings()
    if not settings.demo_fail_serp:
        raise SystemExit("Use DEMO_FAIL_SERP=true for this one-off demonstration.")
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m app.pipeline.failure_demo BRAND_ID")
    init_engine(settings.database_url)
    session = get_session()
    try:
        brand = session.get(Brand, uuid.UUID(sys.argv[1]))
        if brand is None:
            raise SystemExit("Brand not found")
        run = Run(brand_id=brand.id, trigger="failure_demo", brand_snapshot=brand_snapshot(brand))
        session.add(run)
        session.flush()
        run.trace_id = str(run.id)
        run_id = str(run.id)
        session.commit()
    finally:
        remove_session()
    execute_run(run_id)
    print(f"Failure demonstration recorded. Run: {run_id}")


if __name__ == "__main__":
    main()
