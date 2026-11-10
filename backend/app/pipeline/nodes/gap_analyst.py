"""GapAnalyst: LLM classifies each top opportunity's search intent and
explains *why* the gap exists, grounded only in the numbers OpportunityScorer
already computed (CLAUDE.md section 4). One batched call for all top-N
opportunities, not one call per opportunity.
"""

from __future__ import annotations

import uuid

from app.db.models import Opportunity
from app.pipeline.constants import TOP_N_OPPORTUNITIES_FOR_LLM_STAGES
from app.pipeline.context import PipelineContext
from app.pipeline.prompts import gap_analyst_system_prompt, gap_analyst_user_prompt
from app.pipeline.schemas import GapAnalysisBatch
from app.pipeline.stages import NodeResult
from app.pipeline.state import RunState


def gap_analyst(ctx: PipelineContext, state: RunState) -> NodeResult:
    opportunity_ids = [uuid.UUID(o) for o in state.get("opportunity_ids") or []]
    if not opportunity_ids:
        return NodeResult(state_update={}, output_summary={"opportunities_analyzed": 0})

    top = (
        ctx.session.query(Opportunity)
        .filter(Opportunity.id.in_(opportunity_ids))
        .order_by(Opportunity.rank)
        .limit(TOP_N_OPPORTUNITIES_FOR_LLM_STAGES)
        .all()
    )
    if not top:
        return NodeResult(state_update={}, output_summary={"opportunities_analyzed": 0})

    payload = [
        {
            "query_id": str(opp.query_id),
            "text": opp.query.text,
            "search_volume": opp.query.search_volume,
            "score": opp.score,
            **opp.components,
        }
        for opp in top
    ]
    prompt = gap_analyst_user_prompt(payload)
    result = ctx.llm_client.complete_structured(prompt, GapAnalysisBatch, system=gap_analyst_system_prompt())

    by_query_id = {str(opp.query_id): opp for opp in top}
    applied = 0
    for item in result.value.items:
        opp = by_query_id.get(item.query_id)
        if opp is None:
            continue
        opp.explanation = item.explanation
        opp.query.intent = item.intent
        applied += 1
    ctx.session.commit()

    return NodeResult(
        state_update={},
        output_summary={
            "opportunities_analyzed": applied,
            "provider": result.provider,
            "model": result.model,
            "attempts": result.attempts,
        },
    )
