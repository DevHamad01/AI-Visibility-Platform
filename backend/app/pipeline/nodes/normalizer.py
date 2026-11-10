"""Normalizer: pure code, turns the three retrieval nodes' raw JSON into
typed `Query` / `VisibilityObservation` rows (CLAUDE.md section 4). No
external calls, no LLM — just deterministic parsing and domain/name
matching against the brand's tracked competitors.

Query sources (CLAUDE.md section 2 `queries.source` enum):
  - "llm_planner": a query the planner explicitly chose to check directly,
    either via a `serp_google_organic` call or as the question behind an
    `llm_mentions_search` result item.
  - "people_also_ask": a sub-question Google surfaced inside a SERP result.
  - "keyword_ideas": a suggested keyword from the Labs endpoint that was
    never itself checked via SERP/LLM Mentions this run.

When the same query text appears from more than one source (e.g. the
planner's own SERP pick also showed up as a `keyword_ideas` suggestion),
the richer source wins but borrows any volume/competition/CPC/difficulty
numbers the other source has — the two are the same real-world query.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.db.models import Query, QuerySource, VisibilityChannel, VisibilityObservation
from app.pipeline.context import PipelineContext
from app.pipeline.domain_match import domain_matches, name_matches
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState


@dataclass
class _ObservationDraft:
    channel: str
    brand_visible: bool
    brand_position: int | None
    competitors_visible: list[str]
    cited_urls: list[str]


@dataclass
class _QueryDraft:
    text: str
    source: str
    search_volume: int | None = None
    competition: float | None = None
    cpc: float | None = None
    keyword_difficulty: float | None = None
    observations: list[_ObservationDraft] = field(default_factory=list)


def _norm(text: str) -> str:
    return " ".join(text.strip().lower().split())


def _get_or_create(drafts: dict[str, _QueryDraft], text: str, source: str) -> _QueryDraft:
    key = _norm(text)
    draft = drafts.get(key)
    if draft is None:
        draft = _QueryDraft(text=text.strip(), source=source)
        drafts[key] = draft
    return draft


def normalizer(ctx: PipelineContext, state: RunState) -> NodeResult:
    competitors: list[dict[str, Any]] = ctx.brand_snapshot.get("competitors") or []
    brand_domain = ctx.brand_snapshot["domain"]

    drafts: dict[str, _QueryDraft] = {}

    # 1. SERP entries — the planner's own direct picks, source="llm_planner".
    for entry in state.get("serp_entries") or []:
        query_text = entry["query_text"]
        result = entry["result"]
        draft = _get_or_create(drafts, query_text, QuerySource.LLM_PLANNER.value)

        organic = result.get("organic_results") or []
        if organic:
            brand_row = next(
                (r for r in organic if domain_matches(r.get("domain") or "", brand_domain)), None
            )
            competitors_visible = [
                c["name"]
                for c in competitors
                if any(domain_matches(r.get("domain") or "", c["domain"]) for r in organic)
            ]
            draft.observations.append(
                _ObservationDraft(
                    channel=VisibilityChannel.GOOGLE_ORGANIC.value,
                    brand_visible=brand_row is not None,
                    brand_position=brand_row.get("rank_absolute") if brand_row else None,
                    competitors_visible=competitors_visible,
                    cited_urls=[],
                )
            )

        ai_refs = result.get("ai_overview_references") or []
        if ai_refs:
            competitors_visible = [
                c["name"] for c in competitors if any(domain_matches(ref, c["domain"]) for ref in ai_refs)
            ]
            draft.observations.append(
                _ObservationDraft(
                    channel=VisibilityChannel.GOOGLE_AI_OVERVIEW.value,
                    brand_visible=any(domain_matches(ref, brand_domain) for ref in ai_refs),
                    brand_position=None,
                    competitors_visible=competitors_visible,
                    cited_urls=ai_refs,
                )
            )

        for question in result.get("people_also_ask") or []:
            _get_or_create(drafts, question, QuerySource.PEOPLE_ALSO_ASK.value)

    # 2. LLM Mentions items — one query per distinct question, source="llm_planner".
    for item in state.get("llm_mention_items") or []:
        question = item.get("question")
        if not question:
            continue
        draft = _get_or_create(drafts, question, QuerySource.LLM_PLANNER.value)

        brand_entities = item.get("brand_entities") or []
        brand_entry = next(
            (be for be in brand_entities if name_matches(be.get("title"), ctx.brand_snapshot["name"])), None
        )
        competitors_visible = [
            c["name"]
            for c in competitors
            if any(name_matches(be.get("title"), c["name"]) for be in brand_entities)
        ]
        channel = (
            VisibilityChannel.LLM_CHATGPT.value
            if item.get("platform") == "chat_gpt"
            else VisibilityChannel.LLM_GOOGLE_AI.value
        )
        draft.observations.append(
            _ObservationDraft(
                channel=channel,
                brand_visible=brand_entry is not None,
                brand_position=brand_entry.get("position") if brand_entry else None,
                competitors_visible=competitors_visible,
                cited_urls=[u for u in (item.get("source_urls") or []) if u],
            )
        )

    # 3. keyword_ideas suggestions — lowest priority; also enrich any
    #    existing draft that happens to be the same query text.
    for item in state.get("keyword_idea_items") or []:
        text = item.get("keyword") or ""
        if not text:
            continue
        key = _norm(text)
        if key in drafts:
            draft = drafts[key]
        else:
            draft = _get_or_create(drafts, text, QuerySource.KEYWORD_IDEAS.value)
        if draft.search_volume is None:
            draft.search_volume = item.get("search_volume")
        if draft.competition is None:
            draft.competition = item.get("competition")
        if draft.cpc is None:
            draft.cpc = item.get("cpc")
        if draft.keyword_difficulty is None:
            draft.keyword_difficulty = item.get("keyword_difficulty")

    # Priority: llm_planner (direct checks) > people_also_ask > keyword_ideas,
    # capped at the run's query budget.
    priority = {
        QuerySource.LLM_PLANNER.value: 0,
        QuerySource.PEOPLE_ALSO_ASK.value: 1,
        QuerySource.KEYWORD_IDEAS.value: 2,
    }
    ordered = sorted(drafts.values(), key=lambda d: priority.get(d.source, 3))
    kept = ordered[: ctx.settings.max_queries_per_run]

    query_ids: list[str] = []
    for draft in kept:
        query = Query(
            run_id=ctx.run_id,
            text=draft.text,
            source=QuerySource(draft.source),
            search_volume=draft.search_volume,
            competition=draft.competition,
            cpc=draft.cpc,
            keyword_difficulty=draft.keyword_difficulty,
        )
        ctx.session.add(query)
        ctx.session.flush()  # assign query.id before creating observations
        for obs in draft.observations:
            ctx.session.add(
                VisibilityObservation(
                    query_id=query.id,
                    channel=VisibilityChannel(obs.channel),
                    brand_visible=obs.brand_visible,
                    brand_position=obs.brand_position,
                    competitors_visible=obs.competitors_visible,
                    cited_urls=obs.cited_urls,
                )
            )
        query_ids.append(str(query.id))
    ctx.session.commit()

    return NodeResult(
        state_update={"query_ids": query_ids, "sufficient_data": len(query_ids) > 0},
        output_summary={
            "queries_created": len(query_ids),
            "queries_discovered": len(drafts),
            "queries_dropped_over_budget": max(0, len(drafts) - len(kept)),
        },
    )
