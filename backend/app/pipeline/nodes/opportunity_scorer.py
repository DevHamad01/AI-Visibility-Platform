"""OpportunityScorer: pure code, deterministic, explainable components
(CLAUDE.md section 4). Reads the queries + observations Normalizer just
persisted, scores each with app.scoring.opportunity, and persists one
`Opportunity` row per query with every component stored for the UI.
"""

from __future__ import annotations

import uuid

from app.db.models import Opportunity, Query
from app.pipeline.context import PipelineContext
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState
from app.scoring.opportunity import ObservationInput, ScoringInput, rank_scores, score_opportunity


def opportunity_scorer(ctx: PipelineContext, state: RunState) -> NodeResult:
    query_ids = [uuid.UUID(q) for q in state.get("query_ids") or []]
    if not query_ids:
        return NodeResult(state_update={"opportunity_ids": []}, output_summary={"opportunities_created": 0})

    tracked_competitor_count = len(ctx.brand_snapshot.get("competitors") or [])

    queries = (
        ctx.session.query(Query)
        .filter(Query.id.in_(query_ids))
        .order_by(Query.id)
        .all()
    )

    components_by_query: dict[uuid.UUID, tuple] = {}
    scores: list[float] = []
    for query in queries:
        observations = [
            ObservationInput(
                channel=obs.channel.value, brand_visible=obs.brand_visible, brand_position=obs.brand_position
            )
            for obs in query.observations
        ]
        competitors_visible: set[str] = set()
        for obs in query.observations:
            competitors_visible.update(obs.competitors_visible or [])

        components = score_opportunity(
            ScoringInput(
                search_volume=query.search_volume,
                keyword_difficulty=query.keyword_difficulty,
                competition=query.competition,
                observations=observations,
                competitors_visible_count=len(competitors_visible),
                tracked_competitor_count=tracked_competitor_count,
            )
        )
        components_by_query[query.id] = (query, components)
        scores.append(components.score)

    ranks = rank_scores(scores)
    opportunity_ids: list[str] = []
    for rank, (query_id, (_query, components)) in zip(ranks, components_by_query.items(), strict=True):
        opportunity = Opportunity(
            run_id=ctx.run_id,
            query_id=query_id,
            score=components.score,
            rank=rank,
            components=components.as_dict(),
        )
        ctx.session.add(opportunity)
        ctx.session.flush()
        opportunity_ids.append(str(opportunity.id))
    ctx.session.commit()

    return NodeResult(
        state_update={"opportunity_ids": opportunity_ids},
        output_summary={"opportunities_created": len(opportunity_ids)},
    )
