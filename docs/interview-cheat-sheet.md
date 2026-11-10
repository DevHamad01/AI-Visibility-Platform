# Interview cheat sheet — AI Visibility Platform

## Architecture in five lines

1. Angular uses typed HTTP services, signals/reactive forms and lazy routes; nginx proxies the API.
2. Flask validates with Pydantic, documents OpenAPI and persists profiles/history in PostgreSQL.
3. POST run returns 202; Redis/RQ executes a LangGraph DAG outside the HTTP request.
4. DataForSEO supplies numbers; interchangeable LLMs plan, classify, explain and recommend.
5. Stage records and structured trace IDs explain failures; successful branches retain their work.

## Each agent's job

QueryPlanner → validated, capped tool calls. KeywordRetrieval → demand/difficulty.
SerpRetrieval → organic ranks, AI citations and PAA. LlmMentionsRetrieval → one aggregated
brand/competitor call. Normalizer → typed persisted evidence. OpportunityScorer → deterministic
ranking. GapAnalyst → intent and evidence-based explanation. Recommender → content actions.
Report → terminal status, stage outcomes, counts and cost.

## Opportunity formula

`100 × demand × (1 − visibility) × (0.6 + 0.4 × contested) × (1 − 0.5 × difficulty)`

Demand is log-scaled volume capped at 50,000. Visibility averages observed channels; organic
uses position bands, AI/LLM presence is binary. Contested is the visible competitor share.
Difficulty uses KD, then competition, then neutral 0.5. Higher score means a larger remaining
gap. The LLM never supplies these numbers. Missing coverage reduces confidence.

## Resilience and spend

Retry transient transport/429/5xx with jitter; honor Retry-After. Do not retry auth, billing or
verification errors. Each dependency has a circuit breaker and one half-open recovery probe.
JSON is Pydantic-validated, repaired once, then falls back to the next configured provider.
The 24-hour Postgres cache includes base URL so sandbox/live never mix. Atomic reservations
cover simultaneous estimated charges; actual billed attempts accumulate. One aggregated LLM
Mentions request and idempotency keys avoid duplicate spend. Paid PAA expansion is disabled.

## Trace a failed run

History → run → trace ID → failed stage → duration/attempts/error/provider. Correlate JSON
worker/API logs with the same ID, check readiness, provider/account state, budget and worker.
Fix the cause and create a new run; preserve the old evidence. The live example failed with
DataForSEO 40104 (unverified account), while Groq planning succeeded, at $0 DataForSEO cost.

## Five trade-offs to defend

1. RQ + Postgres: simple, durable history; a transactional outbox is future work.
2. Thin LLM adapter: provider-independent JSON validation; weaker models can produce poorer text.
3. Explainable formula: auditable prioritization; not a causal traffic/ROI prediction.
4. Partial results: keep useful evidence; unavailable data must remain visibly distinguished.
5. Real Postgres tests + Docker: faithful JSONB/UUID behavior and one-command setup; slower startup.

Be candid: live successful results await DataForSEO verification; worker metrics are not aggregated
into the API registry. Never present these as completed production capabilities.
