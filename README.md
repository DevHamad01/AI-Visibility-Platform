# AI Visibility Platform

Take-home assessment for Aegasis Labs. Finds where a brand is losing visibility to
competitors in Google search, Google AI Overviews and LLM answers, scores the
opportunities, and recommends content to close the gap.

This README is written as the project is built, phase by phase (see `PROMPTS.md`),
and finalized in the last phase. `CLAUDE.md` is the full specification.

## Status

- [x] **Phase 1** — Docker foundation, backend skeleton, DB schema, brands/competitors
  API, observability basics.
- [x] **Phase 2** — DataForSEO tools + LLM layer + resilience.
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

## What's built in Phase 2

- **DataForSEO tools** (`backend/app/tools/dataforseo/`): one function per logical
  call — `keyword_ideas`, `search_volume`, `serp_google_organic`, `llm_mentions_search`
  (the live endpoint DataForSEO's own docs now recommend over the brief's suggested
  `.../llm_mentions/search/live`, which they mark deprecated-but-working). Each has a
  Pydantic args model validated *before* any HTTP call — invalid/partial args return
  a `ToolArgumentError` value, never an exception. A shared `DataForSEOClient` handles
  Basic auth, timeouts, retry/circuit-breaker, the Postgres `api_cache` table (key =
  sha256 of endpoint + canonical JSON payload), and cost metrics. DataForSEO returns
  HTTP 200 for most logical errors with the real outcome in `tasks[0].status_code` —
  classified here (e.g. `40202` rate-limited → retryable, `40100` auth failure → not).
  AI Overview/People-Also-Ask item shapes are parsed defensively (recursive, type-
  tolerant) since DataForSEO's own docs describe their nesting inconsistently.
- **Resilience module** (`app/core/resilience.py`): tenacity exponential backoff with
  full jitter, honouring a server's `Retry-After` when present; a per-dependency
  circuit breaker (closed → open after N consecutive failures → half-open after a
  cooldown); shared by every DataForSEO and LLM call.
- **LLM layer** (`app/llm/`): one `LLMClient` with `complete_structured(prompt, schema)`
  and `call_tools(prompt, tools)`. Providers (`groq`, `openai`, `anthropic`, `gemini`)
  and their order come entirely from `LLM_CHAIN` — agent code never imports a provider
  SDK. No provider-native structured-output mode is used: the client asks for JSON in
  the prompt, validates with Pydantic, and does exactly one repair retry (re-asking
  with the validation error attached) before falling through to the next provider in
  the chain. An empty `GEMINI_API_KEY` (or any other provider's) simply drops that
  entry from the active chain — the rest still works.
  LLM model ids were verified live against each provider's current docs on
  2026-11-10: `gemini-2.5-flash` turned out to be deprecated (Google auto-routes it to
  `gemini-3.5-flash-lite` from Dec 1, 2026), so the default chain uses
  `gemini-3.5-flash-lite` directly instead. `openai`/`anthropic` SDKs are pinned one
  major version below latest (`openai==2.54.0`, `anthropic==0.125.0`) because their
  newer releases moved to an internal `httpx2` client that `respx` — used by every
  test in this suite to mock HTTP with no real network — cannot intercept; the
  chat/tool-calling API surface is unchanged between these versions and current ones.
- **Tests**: tool argument validation (missing/invalid/out-of-range, never reaches
  HTTP), retry-then-success on 503, 429 honouring `Retry-After`, no retry on 401,
  circuit opening after N failures and failing fast, a cache hit skipping the second
  HTTP call, happy-path parsing for all four tools, LLM JSON repair retry, provider
  fallback after exhausted retries (and which provider served the call), and dropped
  invalid/unknown tool-call arguments.
- **Smoke CLI**: `python -m app.tools.dataforseo.smoke "<query>"` calls
  `serp_google_organic` + `keyword_ideas` live (depth=1, limit=1 — the smallest
  requests that still exercise AI Overview / People Also Ask parsing) and prints
  account balance before/after via the free `user_data` endpoint. Deliberately never
  calls `llm_mentions_search` here — at $0.10/request + $0.001/row it's far more
  expensive than the others and shouldn't be spent on a routine check.
- **Budget guard**: a `RunBudget` caps estimated + actual DataForSEO spend per run
  (`DATAFORSEO_MAX_COST_PER_RUN`, default $0.15). Cost is estimated from DataForSEO's
  published pricing *before* a call is made (`app/tools/dataforseo/pricing.py`); a
  call that would exceed the remaining budget is never sent. A cache hit is always
  free regardless of budget. `llm_mentions_search` takes up to 10 brand/competitor
  targets in **one** call by design, specifically so a run never pays its $0.10 floor
  cost once per competitor.
- **DataForSEO Sandbox**: `DATAFORSEO_BASE_URL=https://sandbox.dataforseo.com` gives
  free dummy-data responses in the same shape as production, for routine local
  development against a small trial balance. The app still defaults to the real,
  billed `api.dataforseo.com` (the brief's "live data by default" rule) — the sandbox
  is opt-in via env var, never automatic.

## Known limitations / next steps

- The LangGraph pipeline and the frontend are not built yet — see the phase checklist
  above. The DataForSEO tools and LLMClient exist as building blocks but aren't wired
  into a graph until Phase 3.
- `make test` recreates its own Postgres database (`<db>_test`) on the same `db`
  service; it does not touch the application database.
- DataForSEO's AI Overview / People Also Ask response shapes are parsed defensively
  rather than against a byte-exact confirmed schema (their own docs describe the
  nesting inconsistently across pages) — field names there should be revisited against
  a real response the first time a run actually surfaces one.
- **The DataForSEO trial account used for development is not yet verified.** A live
  call on 2026-11-10 returned HTTP 403 with inner `status_code` `40104`: "Please
  verify your account before using the API. You can complete verification in the user
  panel: https://app.dataforseo.com/." No cost was incurred (the response's `cost` is
  `0` and `tasks` is `null` — the request never reached a billable task) and the
  account balance was confirmed unchanged at $1.00 before and after via `user_data`.
  This blocks live verification of the DataForSEO tools' response parsing — it is not
  specific to any one endpoint (e.g. LLM Mentions needing a plan upgrade); it blocks
  all of them equally until the account is verified. The live LLM check is unaffected:
  both Groq (`openai/gpt-oss-120b`) and Gemini (`gemini-3.5-flash-lite`) answered a
  real structured-output request correctly on 2026-11-10.

## AI tools used

Claude Code (Anthropic) was used for scaffolding, implementation and tests, under
the author's direction and review.
