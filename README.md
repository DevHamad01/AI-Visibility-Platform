# AI Visibility Platform

Take-home assessment for Aegasis Labs. Finds where a brand is losing visibility to
competitors in Google search, Google AI Overviews and LLM answers, scores the
opportunities, and recommends content to close the gap.

This README is written as the project is built, phase by phase (see `PROMPTS.md`),
and finalized in the last phase. `CLAUDE.md` is the full specification.

## Status

- [x] **Phase 1** — Docker foundation, backend skeleton, DB schema, brands/competitors
  API, observability basics.
- [ ] Phase 2 — DataForSEO tools + LLM layer + resilience.
- [ ] Phase 3 — LangGraph pipeline, scoring, runs API, background jobs.
- [ ] Phase 4 — Angular frontend.
- [ ] Phase 5 — Hardening, CI, final README.

## Quick start

```bash
cp .env.example .env   # fill in DataForSEO/LLM keys when you reach Phase 2+
make up                # docker compose up --build
```

- API: http://localhost:8000
- Swagger UI: http://localhost:8000/api/docs (lands on a doc-UI picker; direct
  link is http://localhost:8000/api/docs/swagger)
- Liveness: http://localhost:8000/healthz · Readiness: http://localhost:8000/readyz
- Metrics: http://localhost:8000/metrics

```bash
make test     # run the backend test suite inside the api container
make migrate  # apply Alembic migrations manually (the api container does this on boot too)
make logs     # follow all service logs
make down     # stop everything
```

The frontend (`http://localhost:4200`) is added in Phase 4.

## What's built in Phase 1

- **Docker Compose**: `db` (Postgres 16) and `redis` (Redis 7), neither published on
  the host (this machine already runs Postgres/Redis for other projects); `api`
  (Flask) on `8000`; `worker` (RQ, same image as `api`, idle until Phase 3 enqueues
  pipeline jobs).
- **Backend**: Flask 3 + flask-openapi3 (Pydantic v2 request/response models,
  Swagger UI at `/api/docs`), SQLAlchemy 2 models + Alembic migration for every table
  in the domain model (brands, competitors, runs, run_stages, queries,
  visibility_observations, opportunities, recommendations, api_cache), structured
  JSON logs via `structlog` with request/trace id propagation, RFC 7807
  (`application/problem+json`) error responses everywhere, Prometheus `/metrics`,
  `/healthz` and `/readyz` (checks DB + Redis).
- **API**: full CRUD on `/api/v1/brands` and `/api/v1/brands/{id}/competitors` with
  cursor pagination (`{items, next_cursor}`), domain validation, `Location` headers
  on create. The run/pipeline endpoints from the full spec exist and are documented
  in Swagger, but return `501 application/problem+json` — they're built in Phase 3.
- **Tests**: run inside the `api` container against a real, throwaway Postgres
  database (`<db>_test`), not SQLite — the models use Postgres-native `JSONB`/`UUID`
  column types that SQLite doesn't support, so a real Postgres instance is the only
  thing that actually exercises the schema we ship. Covers brand create (`201` +
  `Location`), validation failure (`422` problem shape), and missing resource
  (`404` problem shape).

## Known limitations / next steps

- DataForSEO calls, the LLM layer, the LangGraph pipeline and the frontend are not
  built yet — see the phase checklist above.
- `make test` recreates its own Postgres database (`<db>_test`) on the same `db`
  service; it does not touch the application database.

## AI tools used

Claude Code (Anthropic) was used for scaffolding, implementation and tests, under
the author's direction and review.
