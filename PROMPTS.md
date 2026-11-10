# Claude Code prompts — run ONE phase at a time

How to use: open Git Bash in `D:\Assesment\AI-Visibility-Platform`, run `claude`, paste the phase prompt.
After each phase: check the "Done when" list yourself, then ask Claude Code:
"Explain what you built in this phase in simple terms, and the 3 decisions an interviewer is most likely to ask about."
Write those answers down — you will need them in the interview.

Target timeline (PKT): P1 07:30–08:45 · P2 08:45–10:15 · P3 10:15–12:30 · P4 12:30–16:00 · P5 16:00–18:00 · buffer → submit 19:00

---

## Phase 1 — Foundation: Docker, backend skeleton, DB, API, observability

```
Read CLAUDE.md fully first. It is the source of truth for this project; follow every rule in it.

Phase 1 goal: a running foundation that the rest of the project plugs into. Build:

1. Repo scaffolding: .gitignore (Python, Node, Angular, .env), .gitattributes (eol=lf), Makefile
   (up, down, logs, test, migrate, fmt), root .env.example documenting EVERY setting with comments
   (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD, LLM_CHAIN=groq:openai/gpt-oss-120b,gemini:<model>,
   GROQ_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, timeouts, retry limits, circuit breaker thresholds,
   cache TTL, MAX_QUERIES_PER_RUN, LOG_LEVEL, SENTRY_DSN, DATABASE_URL, REDIS_URL).
2. docker-compose.yml with services: postgres (16, healthcheck, named volume, NO published port),
   redis (NO published port), api (Flask, port 8000), worker (RQ, same image), frontend placeholder
   (just leave a TODO service comment for now). api/worker wait for healthy db/redis. Migrations run
   automatically on api start (alembic upgrade head).
3. backend/: pyproject.toml (pinned deps), Dockerfile (python:3.12-slim, non-root user), app factory,
   config from env via pydantic-settings (fail fast with a clear message if required keys are missing),
   structlog JSON logging with request_id/trace_id contextvars, X-Request-ID middleware,
   RFC7807 problem+json error handlers (404, 409, 422 validation, 500 without leaking internals),
   Prometheus /metrics, /healthz, /readyz (checks DB + Redis).
4. SQLAlchemy 2 models + first Alembic migration for ALL tables in CLAUDE.md section 2.
5. flask-openapi3 REST endpoints for brands + competitors (full CRUD with Pydantic validation,
   correct status codes, Location headers, cursor pagination). Swagger UI at /api/docs.
   Runs endpoints can return 501 problem+json for now — they are built in Phase 3.
6. pytest setup (tests run inside the api container against a throwaway test DB or SQLite fallback —
   your choice, explain it) with tests for: brand create 201 + Location, validation 422 problem shape,
   404 problem shape.

Do NOT build the pipeline, DataForSEO or the frontend yet.

Done when: `docker compose up --build` starts cleanly, http://localhost:8000/api/docs shows the API,
/healthz and /readyz return 200, `make test` passes. Then commit in logical commits
(no Co-Authored-By trailers) and push to origin main. Finish with a short summary of what exists now.
```

---

## Phase 2 — DataForSEO tools + LLM layer + resilience

```
Read CLAUDE.md again (sections 1, 4, 5, 6). Phase 2 goal: reliable building blocks for the pipeline.

1. backend/app/tools/dataforseo/: an httpx client (Basic auth, timeouts from env) and ONE tool per
   logical call: keyword_ideas, search_volume, serp_google_organic, llm_mentions_search.
   Before writing each tool, check the real request/response shape in the official docs
   (https://docs.dataforseo.com/v3/) — do not guess field names. Each tool has a Pydantic args model
   (types, descriptions, required fields, sensible bounds) whose JSON schema is exported for LLM
   tool-calling, and a typed parsed result. Validate args BEFORE any HTTP call; invalid/partial args
   return a typed ToolArgumentError, never an exception into the graph.
2. Resilience module used by every external call: tenacity exponential backoff + full jitter,
   error classification (retryable: timeouts, connection errors, 429 with Retry-After, 5xx, DataForSEO
   inner "retry later" codes; non-retryable: 400/401/402/403/404, auth/balance/plan errors — remember
   DataForSEO wraps errors in HTTP 200 with an inner status_code), per-dependency circuit breaker
   (closed/open/half-open, thresholds from env), attempt counts surfaced to the caller.
3. Postgres-backed response cache (api_cache table): key = sha256(endpoint + canonical JSON payload),
   TTL from env. Cache hits are logged and counted; DataForSEO `cost` from responses is recorded.
4. backend/app/llm/: LLMClient interface with complete_structured(prompt, schema) and
   call_tools(prompt, tools). Providers: groq and openai (both via the openai SDK with base_url),
   gemini (openai SDK with Gemini OpenAI-compatible base_url), anthropic (anthropic SDK), plus the
   ordered fallback chain from CLAUDE.md. Do NOT use provider-native response_format/strict structured outputs.
   Parse JSON, validate with Pydantic, one repair retry with the validation error, then a typed
   LLMOutputError. Same retry/backoff/circuit-breaker module. Providers + order chosen by env (LLM_CHAIN) only.
5. Metrics + structured logs for every external call (dependency, endpoint, status, attempt,
   duration_ms, cache_hit), secrets redacted.
6. Tests (mock HTTP with respx, no real network): tool arg validation (missing required field,
   wrong type, out-of-range), retry then success on 503, 429 honours Retry-After, no retry on 401,
   circuit opens after N failures and fails fast, cache hit avoids second HTTP call, LLM junk JSON →
   repair retry → success, LLM junk twice → LLMOutputError (no crash), primary provider 503 x N →
   falls back to secondary and records which provider served the call.
7. Add a tiny CLI `python -m app.tools.dataforseo.smoke "best project management software"` that
   calls serp_google_organic + keyword_ideas LIVE and prints a short summary, so we can verify the
   real credentials and response parsing.

Done when: `make test` passes and the smoke CLI (run inside the api container) prints real data.
Commit in logical commits and push.
```

---

## Phase 3 — LangGraph pipeline, scoring, runs API, background jobs, live progress

```
Read CLAUDE.md sections 2–6 again. Phase 3 goal: an end-to-end analysis run on live data.

1. backend/app/pipeline/: RunState (typed), and one node per agent exactly as in the CLAUDE.md DAG:
   QueryPlanner (LLM tool-calling → validated ToolCall list; invalid calls dropped and logged),
   KeywordRetrieval / SerpRetrieval / LlmMentionsRetrieval (parallel fan-out; they only execute
   validated tool calls), Normalizer (pure code), conditional route on data sufficiency,
   OpportunityScorer (pure code, formula + weights from CLAUDE.md in one config module),
   GapAnalyst (LLM, validated), Recommender (LLM, validated, top-N only), Report (assembles final
   JSON + summary and decides succeeded | partial | failed). Each node is wrapped by a common
   decorator that: logs start/end JSON with run_id/node/duration/attempts/status, updates run_stages,
   emits metrics, catches failures into a typed stage error so other branches' work is kept.
2. Prompts: specific, short, with the brand snapshot and competitors, explicit output JSON shape,
   and instructions about what NOT to invent (no numbers). Keep prompts in their own module.
3. Runs API: POST /brands/{id}/runs (202 + Location, Idempotency-Key, 409 if one already active),
   GET /runs/{id} (stages, progress, metrics, partial flags), GET /brands/{id}/runs (history),
   GET /runs/{id}/events (SSE progress), /visibility, /opportunities (filters + sort),
   /recommendations, PATCH /recommendations/{id}, GET /brands/{id}/compare, GET /overview,
   GET /runs/{id}/export, POST /client-errors. Store brand_snapshot on each run.
4. RQ worker executes the graph; a timeout guard marks stuck runs failed with a reason.
5. Tests: scoring determinism + ordering; full pipeline happy path with mocked tools/LLM; SERP
   dependency failing after retries → run ends `partial`, keyword + scoring work is kept, stage error
   recorded; malformed planner tool call is rejected and not executed; API 202/409/404.

Done when: via Swagger I can create a brand with 2 competitors, start a run, watch /events, and get
real opportunities + recommendations from live DataForSEO data. Paste a real run's JSON log excerpt
into docs/sample-trace.log for the README. Commit and push.
```

---

## Phase 4 — Angular frontend (20 design points + 10 Angular points)

```
Read CLAUDE.md section 7 and the backend OpenAPI at http://localhost:8000/api/docs. Phase 4 goal:
a product-quality UI that uses ONLY our API.

1. Create frontend/ with the latest stable Angular CLI: standalone, strict TS, SCSS, routing,
   lazy-loaded feature routes. Typed models for every API response (mirror the OpenAPI schemas).
   All HTTP in services; interceptor adds X-Request-ID; global ErrorHandler + HTTP error reporting to
   POST /api/v1/client-errors. Shared state with signals in small stores; RxJS for HTTP and SSE.
2. Design system first: tokens (CSS custom properties) for colour, typography scale, spacing, radius,
   elevation; light + dark theme with a toggle; one confident accent colour; a small set of shared UI
   components (button, card, badge, skeleton, empty-state, error-state, partial-banner, stat tile).
   Use the frontend-design skill if available. It must NOT look like default Angular Material.
3. Screens: Portfolio overview · Brand setup (Reactive Form + competitors FormArray + domain
   validators + server error mapping) · Brand detail with run history/trend · Run live view (SSE stage
   timeline, current activity, elapsed time, partial-failure explanation) · Results: visibility heatmap
   (queries × channels, brand vs competitors, ngx-echarts), opportunities table with filters/sort and a
   score-breakdown drawer showing each formula component, recommendations board with status actions,
   CSV/JSON export · Compare two runs.
4. Every state designed: skeleton loading, empty with next action, friendly error with trace id and
   retry, partial banner. Responsive at >=1280px and >=768px.
5. Dockerfile (multi-stage Node build → nginx), nginx.conf proxying /api to the api service (SSE
   friendly: proxy_buffering off for /events), add the frontend service to docker-compose on port
   4200. Add frontend/src/environments/environment.example.ts.

Done when: `docker compose up --build` → http://localhost:4200 → create brand → run analysis → watch
live progress → see real results, filter opportunities, act on recommendations, re-run and compare.
Check at 1280px and 768px and in dark mode. Commit in logical commits and push.
```

---

## Phase 5 — Hardening, CI, README, final check

```
Read CLAUDE.md sections 8 and 10. Phase 5 goal: submission quality.

1. Fill test gaps listed in CLAUDE.md section 8; make `make test` green.
2. .github/workflows/ci.yml: backend lint + tests, frontend lint + production build.
3. README.md exactly covering CLAUDE.md section 10, with a Mermaid DAG diagram, the opportunity formula
   and why, a real simulated-failure log excerpt (run with SERP forced to fail via an env flag used
   only for this demonstration, documented), the "how to debug 'my run failed yesterday'" walkthrough
   using real log lines, trade-offs, known limitations, next steps, setup in under 5 minutes, and the
   AI tools section (Claude Code for scaffolding, implementation and tests under the author's direction).
   State the assumption about the missing "Section 4" of the brief.
4. Clean-checkout test: clone the repo into a temp folder, copy .env, run `docker compose up --build`,
   and verify the full flow works. Fix anything that breaks.
5. Remove dead code, TODOs that are not in README, and debug prints.

Commit and push. Then give me a 1-page "interview cheat sheet": architecture in 5 lines, each agent's
job, the opportunity formula, how retries/circuit breaker/cache work, how to trace a failed run,
and the top 5 trade-offs with their justification.
```
