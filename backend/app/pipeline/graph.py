"""Builds and runs the LangGraph DAG (CLAUDE.md section 4):

             ┌──────────────┐
  start ───► │ QueryPlanner │
             └──────┬───────┘
        ┌───────────┼──────────────────────┐   (parallel fan-out)
        ▼           ▼                      ▼
 KeywordRetrieval  SerpRetrieval      LlmMentionsRetrieval
        └───────────┼──────────────────────┘
                    ▼
             Normalizer
                    │
          route: enough data? ──no──► Report
                    │ yes
                    ▼
             OpportunityScorer ─► GapAnalyst ─► Recommender ─► Report

Built fresh per run (cheap — a handful of node registrations) rather than
once globally, because nodes need run-scoped dependencies (DB session,
budget tracker, trace id) that LangGraph's own `config` threading would add
indirection without benefit for a graph this size.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from app.pipeline.context import PipelineContext
from app.pipeline.nodes.gap_analyst import gap_analyst
from app.pipeline.nodes.keyword_retrieval import keyword_retrieval
from app.pipeline.nodes.llm_mentions_retrieval import llm_mentions_retrieval
from app.pipeline.nodes.normalizer import normalizer
from app.pipeline.nodes.opportunity_scorer import opportunity_scorer
from app.pipeline.nodes.query_planner import query_planner
from app.pipeline.nodes.recommender import recommender
from app.pipeline.nodes.report import report
from app.pipeline.nodes.serp_retrieval import serp_retrieval
from app.pipeline.stages import run_node
from app.pipeline.state import RunState


def _route_on_sufficiency(state: RunState) -> str:
    return "sufficient" if state.get("sufficient_data") else "insufficient"


def build_graph(ctx: PipelineContext):
    graph = StateGraph(RunState)

    def node(name: str, fn):
        return run_node(ctx, name, lambda s: fn(ctx, s))

    graph.add_node("query_planner", node("query_planner", query_planner))
    graph.add_node("keyword_retrieval", node("keyword_retrieval", keyword_retrieval))
    graph.add_node("serp_retrieval", node("serp_retrieval", serp_retrieval))
    graph.add_node("llm_mentions_retrieval", node("llm_mentions_retrieval", llm_mentions_retrieval))
    graph.add_node("normalizer", node("normalizer", normalizer))
    graph.add_node("opportunity_scorer", node("opportunity_scorer", opportunity_scorer))
    graph.add_node("gap_analyst", node("gap_analyst", gap_analyst))
    graph.add_node("recommender", node("recommender", recommender))
    graph.add_node("report", node("report", report))

    graph.set_entry_point("query_planner")
    graph.add_edge("query_planner", "keyword_retrieval")
    graph.add_edge("query_planner", "serp_retrieval")
    graph.add_edge("query_planner", "llm_mentions_retrieval")
    graph.add_edge("keyword_retrieval", "normalizer")
    graph.add_edge("serp_retrieval", "normalizer")
    graph.add_edge("llm_mentions_retrieval", "normalizer")
    graph.add_conditional_edges(
        "normalizer", _route_on_sufficiency, {"sufficient": "opportunity_scorer", "insufficient": "report"}
    )
    graph.add_edge("opportunity_scorer", "gap_analyst")
    graph.add_edge("gap_analyst", "recommender")
    graph.add_edge("recommender", "report")
    graph.add_edge("report", END)

    return graph.compile()


def run_pipeline(ctx: PipelineContext) -> dict[str, Any]:
    compiled = build_graph(ctx)
    return compiled.invoke({})
