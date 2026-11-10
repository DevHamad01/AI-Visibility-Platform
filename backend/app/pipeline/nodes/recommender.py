"""Recommender: LLM proposes content recommendations for the top-N
opportunities (CLAUDE.md section 4), one batched call, not one per
opportunity. Runs after GapAnalyst so each opportunity already has an
intent/explanation to ground the recommendation in.
"""

from __future__ import annotations

import uuid

from app.db.models import Opportunity, Recommendation
from app.pipeline.constants import TOP_N_OPPORTUNITIES_FOR_LLM_STAGES
from app.pipeline.context import PipelineContext
from app.pipeline.prompts import recommender_system_prompt, recommender_user_prompt
from app.pipeline.schemas import RecommendationsBatch
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState


def recommender(ctx: PipelineContext, state: RunState) -> NodeResult:
    empty = NodeResult(state_update={"recommendation_ids": []}, output_summary={"recommendations_created": 0})

    opportunity_ids = [uuid.UUID(o) for o in state.get("opportunity_ids") or []]
    if not opportunity_ids:
        return empty

    top = (
        ctx.session.query(Opportunity)
        .filter(Opportunity.id.in_(opportunity_ids))
        .order_by(Opportunity.rank)
        .limit(TOP_N_OPPORTUNITIES_FOR_LLM_STAGES)
        .all()
    )
    if not top:
        return empty

    payload = [
        {
            "query_id": str(opp.query_id),
            "text": opp.query.text,
            "intent": opp.query.intent,
            "score": opp.score,
            "explanation": opp.explanation,
        }
        for opp in top
    ]
    prompt = recommender_user_prompt(ctx.brand_snapshot, payload)
    result = ctx.llm_client.complete_structured(
        prompt, RecommendationsBatch, system=recommender_system_prompt()
    )

    by_query_id = {str(opp.query_id): opp for opp in top}
    recommendation_ids: list[str] = []
    for item in result.value.items:
        opp = by_query_id.get(item.query_id)
        if opp is None:
            continue
        recommendation = Recommendation(
            run_id=ctx.run_id,
            opportunity_id=opp.id,
            title=item.title,
            content_type=item.content_type,
            target_query=opp.query.text,
            outline=item.outline,
            rationale=item.rationale,
            priority=item.priority,
            effort=item.effort,
        )
        ctx.session.add(recommendation)
        ctx.session.flush()
        recommendation_ids.append(str(recommendation.id))
    ctx.session.commit()

    return NodeResult(
        state_update={"recommendation_ids": recommendation_ids},
        output_summary={
            "recommendations_created": len(recommendation_ids),
            "provider": result.provider,
            "model": result.model,
            "attempts": result.attempts,
        },
    )

