# CLAUDE.md — AI Visibility Platform (Aegasis Labs Full-Stack Assessment)

You are building a take-home assessment that will be reviewed by two senior engineers and then
defended by the author (Hamad) in a technical interview. Every decision must be simple enough to
explain, deliberate, and documented. Prefer a smaller, solid system over a big fragile one.

**Hard deadline: today 19:00 PKT.** Work phase by phase (see PROMPTS.md). Finish and commit each
phase before starting the next. Never leave the repo in a non-running state at the end of a phase.

---

## 0. Non-negotiable rules

1. **Git identity is already configured locally (Hamad).** Never run `git config`, never change the
   remote, never force-push. Do **not** add `Co-Authored-By` or any AI attribution trailer to commits.
   Use Conventional Commit messages (`feat(backend): ...`, `fix(frontend): ...`, `docs: ...`, `test: ...`).
   Commit small and often — reviewers read the commit history.
2. **Never commit secrets.** `.env` is git-ignored. Only `.env.example` files are committed.
3. **Live data by default.** DataForSEO and the LLM are called for real in the running app.
   Mocks/fixtures are allowed **only in automated tests**. There is no "demo mode" default.
4. **Everything runs from a clean checkout with one command:** `docker compose up --build`
   (plus a `Makefile` with `make up`, `make test`, `make logs`, `make down`).
5. **Do not publish ports for Postgres or Redis.** This machine already runs other containers on
   5432 and 6379. DB and Redis live only on the internal compose network. Published ports:
   frontend `4200`, backend `8000` only.
6. Docker images use **Python 3.12** (`python:3.12-slim`) and **Node 22 LTS** for the Angular build.
   Do not depend on the host's Python version.
7. Windows host: keep shell scripts LF line endings (add `.gitattributes` with `* text=auto eol=lf`).
8. When something cannot be done well in time, stub it cleanly and record it in README "Known
   limitations / next steps". Never fake data on screen.

---

## 1. Stack (fixed by the brief + our choices)

| Layer | Choice | Why (be ready to defend) |
|---|---|---|
| API | Flask 3 + **flask-openapi3** (Pydantic v2 request/response models → OpenAPI + Swagger UI at `/api/docs`) | Flask is mandated; Pydantic gives one source of truth for validation + docs |
| Pipeline | **LangGraph** `StateGraph` (DAG with parallel fan-out + conditional routing) | Brief asks for a DAG of single-responsibility agents |
| LLM | Own thin `LLMClient` interface. Providers: `openai`, `anthropic`, `groq`, `gemini` (Groq and Gemini via their OpenAI-compatible base URLs). **Ordered fallback chain** from env, e.g. `LLM_CHAIN=groq:openai/gpt-oss-120b,gemini:gemini-2.5-flash` (verify current Gemini model ids). Default dev chain: Groq primary, Gemini fallback | Provider is config, not code; one provider down ≠ run down |
| Data | DataForSEO v3 REST via `httpx` | Reference provider |
| DB | PostgreSQL 16 + SQLAlchemy 2 + Alembic migrations | History, relational model |
| Jobs | Redis + **RQ** worker (separate container) | Long runs never block HTTP; survives API restarts |
| Logs | `structlog` JSON to stdout | Machine-parseable, one event per line |
| Metrics | `prometheus_client` at `/metrics` + per-run metrics summary persisted on the run | |
| Errors | Optional Sentry (`SENTRY_DSN`; no-op when empty) + errors persisted per stage | |
| Frontend | Angular (latest stable, ≥17), standalone components, strict TS, signals for state, RxJS for async, Reactive Forms, lazy routes, **ngx-echarts** for charts, own SCSS design system (no stock Material look), dark mode | Brief's quality bar |
| Serve FE | Multi-stage Docker: build with Node, serve with **nginx**, nginx proxies `/api` → backend | One origin, no CORS pain |

### LLM layer rules (important — provider must be swappable without changing results)
- All agents call `LLMClient.complete_structured(prompt, schema: type[BaseModel])` and
  `LLMClient.call_tools(prompt, tools)`. Agents never import a provider SDK.
- **Do NOT rely on provider-native "structured output / response_format / strict" features**
  (Groq's gpt-oss and LangChain's `with_structured_output` are unreliable together). Instead:
  request JSON in the prompt (or via a single tool call), parse it, **validate with Pydantic**,
  and on failure re-ask once with the validation error appended ("repair retry"). If still invalid,
  the stage returns a typed failure — it never raises into the graph and never reaches the UI unchecked.
- **Numbers never come from the LLM.** Volumes, competition, positions, mentions, and the
  opportunity score come from DataForSEO + deterministic Python. The LLM only plans, classifies,
  explains and writes recommendations. A better model gives better text, never different numbers.
- **Fallback chain:** each provider has its own retry policy and circuit breaker. If the current provider
  exhausts retries, its circuit is open, or it returns a non-retryable provider error (auth, quota, model
  not found), the call moves to the next provider in `LLM_CHAIN`. Output that fails Pydantic validation after
  the repair retry also falls through to the next provider. Only when every provider fails does the stage fail.
- Every run and every LLM stage records which `provider:model` actually served it (shown in the run trace UI),
  and fallbacks are logged and counted (`llm_fallbacks_total{from,to}`).
- README note: the brief asks for OpenAI or Anthropic; both are supported first-class and selectable via
  `LLM_CHAIN`. Development used free tiers (Groq serving OpenAI's open-weight gpt-oss-120b, Gemini as fallback).

---

## 2. Domain & data model (persistence with history — never overwrite a past run)

- `brands` (id UUID, name, domain, description, industry/market, location_code, language_code, created_at, updated_at)
- `competitors` (id, brand_id FK, name, domain)
- `runs` (id, brand_id, status: `queued|running|succeeded|partial|failed`, trigger, created_at, started_at,
  finished_at, llm_provider, llm_model, trace_id, progress JSON, metrics JSON, error_summary,
  dataforseo_cost_usd, idempotency_key, **brand_snapshot JSON** = brand+competitors as they were at run time)
- `run_stages` (run_id, stage name, status `pending|running|succeeded|failed|skipped`, attempts,
  started_at, finished_at, duration_ms, error_type, error_message, output_summary JSON)
- `queries` (id, run_id, text, source `keyword_ideas|people_also_ask|llm_planner`, intent, search_volume,
  competition, cpc, keyword_difficulty)
- `visibility_observations` (id, query_id, channel `google_organic|google_ai_overview|llm_chatgpt|llm_google_ai`,
  brand_visible bool, brand_position int|null, competitors_visible JSON, cited_urls JSON, raw_ref)
- `opportunities` (id, run_id, query_id, score 0–100, rank, components JSON, explanation)
- `recommendations` (id, run_id, opportunity_id, title, content_type, target_query, outline JSON,
  rationale, priority, effort, status `todo|in_progress|done|dismissed`)
- `api_cache` (key sha256 of endpoint+normalized payload, endpoint, response JSON, cost, created_at, expires_at)
  → **we never pay twice for the same DataForSEO call within TTL** (default 24h).

Re-measuring creates a **new run**. Comparison is computed between two runs of the same brand.

---

## 3. REST API (`/api/v1`, JSON, consistent, documented)

- Errors: RFC 7807 `application/problem+json` `{type,title,status,detail,instance,trace_id,errors[]}`.
- Every response carries `X-Request-ID` (accept incoming or generate). It is also the log correlation id.
- Pagination: `?limit=&cursor=`; list responses `{items, next_cursor}`.

Resources (adjust only with a written reason in README):
```
GET/POST           /brands                         201 + Location
GET/PATCH/DELETE   /brands/{id}                    404 problem if missing
GET/POST           /brands/{id}/competitors
DELETE             /brands/{id}/competitors/{cid}
POST               /brands/{id}/runs               202 Accepted + Location; Idempotency-Key header;
                                                   409 if a run for this brand is already queued/running
GET                /brands/{id}/runs               run history
GET                /runs/{id}                      status, stages, progress, metrics, partial flags
GET                /runs/{id}/events               Server-Sent Events: live stage progress
GET                /runs/{id}/visibility           query × channel matrix (brand vs competitors)
GET                /runs/{id}/opportunities        filters: min_score, channel, intent, q; sort
GET                /runs/{id}/recommendations
PATCH              /recommendations/{id}           status updates
GET                /brands/{id}/compare?base=&target=   deltas between two runs
GET                /overview                       portfolio across all brands
GET                /runs/{id}/export?format=csv|json
POST               /client-errors                  frontend error reports (rate-limited, size-limited)
GET                /healthz (liveness)  /readyz (DB + Redis + config)  /metrics (Prometheus)
```

---

## 4. Pipeline (LangGraph DAG) — one job per agent, explicit contracts

Each node: input = typed slice of `RunState`, output = typed Pydantic model, persisted to `run_stages`.
A node failing marks its stage `failed`, stores the error, and **never discards other nodes' work**.

```
             ┌──────────────┐
  start ───► │ QueryPlanner │  LLM + tool-calling: chooses which DataForSEO tools to call and with what args
             └──────┬───────┘
                    │ validated ToolCall[] (Pydantic; invalid/partial args → dropped + logged, never executed)
        ┌───────────┼──────────────────────┐   (parallel fan-out)
        ▼           ▼                      ▼
 KeywordRetrieval  SerpRetrieval      LlmMentionsRetrieval      ← only call APIs, no reasoning
        └───────────┼──────────────────────┘
                    ▼
             Normalizer           ← pure code: raw JSON → typed Query/VisibilityObservation
                    │
          route: enough data? ──no──► Report (status=failed/partial, explains what's missing)
                    │ yes
                    ▼
             OpportunityScorer    ← pure code, deterministic, explainable components
                    ▼
             GapAnalyst (LLM)     ← classifies intent + explains *why* each top gap exists (validated)
                    ▼
             Recommender (LLM)    ← content recommendations for top-N opportunities (validated)
                    ▼
             Report               ← assembles final JSON + human-readable summary; sets succeeded|partial|failed
```
- Retrieval tools: **one tool per logical DataForSEO call**, each with a Pydantic args schema
  exported as JSON schema for the LLM. Suggested tools (verify against https://docs.dataforseo.com/v3/):
  - `keyword_ideas` → `/v3/dataforseo_labs/google/keyword_ideas/live` (volume, competition, KD)
  - `search_volume` → `/v3/keywords_data/google_ads/search_volume/live`
  - `serp_google_organic` → `/v3/serp/google/organic/live/advanced` (organic ranks, `ai_overview`, `people_also_ask` items)
  - `llm_mentions_search` → `/v3/ai_optimization/llm_mentions/search/live` (platform `google` | `chat_gpt`)
  If an endpoint returns an auth/plan error (e.g. LLM Mentions not enabled on a trial account), that
  tool's stage is `failed` with a clear reason; the run continues and ends `partial`.
- Budget guards from env: `MAX_QUERIES_PER_RUN` (default 12), `MAX_SERP_CALLS_PER_RUN`, timeouts.
  Record DataForSEO `cost` from each response into run metrics.

### Opportunity score (deterministic, 0–100, every component stored and shown in the UI)
```
demand       = min(1, log10(1 + search_volume) / log10(1 + VOLUME_CAP))         # VOLUME_CAP default 50_000
visibility   = weighted mean over channels of brand presence
               (organic: 1 if top3, 0.6 if 4–10, 0.2 if 11–20, else 0; AI overview cited: 1/0; LLM mentioned: 1/0)
gap          = 1 − visibility
contested    = share of tracked competitors visible on this query (0–1)  → proves relevance & winnability
difficulty   = keyword_difficulty/100 (fallback: competition index)
score        = 100 × demand × gap × (0.6 + 0.4 × contested) × (1 − 0.5 × difficulty)
```
Weights live in one config module, are unit-tested, and are explained in README.

---

## 5. Resilience
- `httpx` timeouts on every external call (connect 5s, read from env, default 60s; LLM 60s).
- Retry with **exponential backoff + full jitter** (tenacity) only for retryable errors:
  timeouts, connection errors, 429 (respect `Retry-After`), 5xx, DataForSEO task status codes that mean
  "try later". **Non-retryable:** 400/401/402/403/404, validation errors, DataForSEO auth/balance errors.
  Note: DataForSEO returns HTTP 200 with an inner `status_code` — classify on the inner code too.
- **Circuit breaker** per dependency (dataforseo, llm): opens after N consecutive failures, half-open after cooldown;
  open circuit → stage fails fast with `circuit_open`.
- Cache + idempotency key prevent double spend. Retries recorded per stage (`attempts`).
- Worker crash/timeout: run marked `failed` with reason by a timeout guard; never stuck in `running` forever.

## 6. Observability (must answer "my run failed yesterday — why?")
- One JSON log line per event with: `ts, level, event, service, run_id, trace_id, request_id, node, attempt,
  duration_ms, status, error_type`. Inputs logged **redacted** (no API keys/passwords).
- `trace_id` = `run_id`-scoped; propagated API → RQ job → every node → every external call.
- `GET /runs/{id}` exposes per-stage timing, attempts and errors (the "trace" view in the UI).
- Prometheus metrics: `node_duration_seconds{node}`, `node_runs_total{node,status}`,
  `external_calls_total{dependency,endpoint,status}`, `external_retries_total`, `runs_total{status}`,
  `circuit_state{dependency}`, `dataforseo_cost_usd_total`.
- Frontend errors → `POST /api/v1/client-errors` with `request_id`/route/user-agent, logged server-side.

## 7. Frontend product (judged "as a product someone would pay for")
Screens (lazy routes): **Portfolio overview** (all brands, latest score/visibility trend) · **Brand setup**
(reactive form, competitors FormArray, domain validation) · **Brand detail** (run history + trend) ·
**Run live view** (SSE stage timeline, what's happening now, partial-failure explanation) ·
**Results**: visibility matrix heatmap (queries × channels, brand vs competitors), opportunity table with
filters/sort and a score-breakdown drawer, recommendations board with status actions, export ·
**Compare** two runs (what improved/declined).
- Design system: CSS custom properties for colour/type/spacing scale, light + dark theme, one accent colour.
- Every state designed: skeleton loading, empty (with next action), error (friendly + trace id + retry),
  partial (banner listing failed stages and what data is missing).
- Responsive at ≥1280px and ≥768px.
- Typed models for every API response, all HTTP in services, HTTP interceptor adds `X-Request-ID`,
  global `ErrorHandler` reports to backend. Nothing hardcoded — all data from our API.

## 8. Tests (few, aimed at the riskiest parts) — `make test`
- tool-call argument validation (missing/invalid/partial args never executed)
- retry/backoff + error classification + circuit breaker (mock transport, e.g. `respx`)
- LLM output validation + repair retry + graceful stage failure on junk output
- opportunity scoring determinism and ordering
- pipeline happy path (mocked providers) and one-dependency-fails → `partial` run with other work kept
- API: status codes (201/202/404/409/422) and problem+json shape
- CI: GitHub Actions running backend tests + frontend build/lint

## 9. Repo layout
```
backend/   app/{api,core(config,logging,metrics,errors),db(models,migrations),pipeline(graph,nodes,state),
           tools(dataforseo),llm(providers),scoring,services,worker}  tests/  Dockerfile  pyproject.toml
frontend/  src/app/{core(services,interceptors,models,state),shared(ui),features/*}  Dockerfile  nginx.conf
docker-compose.yml  Makefile  .env.example  frontend/src/environments/*.example  README.md  .github/workflows/ci.yml
```

## 10. README (part of the grade — write it as you go, finalize in the last phase)
Architecture + why · DAG diagram (Mermaid) · agent responsibilities & contracts · opportunity definition
& formula & why · failure handling with a **real simulated-failure log excerpt** · how to debug a production
incident step by step with a **sample trace/log excerpt** · trade-offs · known limitations & next steps ·
setup in <5 min · which DataForSEO endpoints/mode · which LLM/provider and how to switch ·
**AI tools used: Claude Code (Anthropic) for scaffolding, implementation and tests under the author's
direction and review** · assumptions (the brief references a "Section 4" that was not included; state our
assumption about persistence of profiles/runs/queries/recommendations).
