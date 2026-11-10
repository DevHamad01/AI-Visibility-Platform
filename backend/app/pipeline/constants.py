"""Small pipeline-wide constants that aren't per-run env config."""

from __future__ import annotations

# GapAnalyst and Recommender only process the highest-scoring opportunities —
# every opportunity is already persisted with its deterministic score by
# OpportunityScorer; these two LLM stages just add explanation/content for
# the ones worth acting on first, in one batched call each (not one call per
# opportunity) to keep LLM cost and latency down.
TOP_N_OPPORTUNITIES_FOR_LLM_STAGES = 5
