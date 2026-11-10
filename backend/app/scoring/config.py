"""Opportunity score weights, in one place so they're unit-tested and
explained in README rather than scattered through the scorer. CLAUDE.md
section 4 fixes the formula shape; the specific constants below are our
documented, defensible choices for the parts the brief left open.
"""

from __future__ import annotations

# demand = min(1, log10(1+search_volume) / log10(1+VOLUME_CAP))
VOLUME_CAP = 50_000

# visibility = mean of per-channel brand presence (organic uses position
# bands below; AI Overview / LLM channels are binary cited-or-not).
ORGANIC_TOP3_SCORE = 1.0
ORGANIC_4_TO_10_SCORE = 0.6
ORGANIC_11_TO_20_SCORE = 0.2
ORGANIC_BEYOND_SCORE = 0.0

# difficulty = keyword_difficulty/100, falling back to the competition index
# (already 0-1) when DataForSEO didn't return a difficulty for this keyword.
# When neither is available, 0.5 (neutral) rather than 0 (easy) or 1 (hard) —
# an unscored keyword should not look artificially better or worse than one
# DataForSEO actually scored.
DEFAULT_DIFFICULTY_WHEN_UNKNOWN = 0.5

# score = 100 * demand * gap * (CONTESTED_BASE + CONTESTED_VARIABLE*contested)
#       * (1 - DIFFICULTY_PENALTY*difficulty)
CONTESTED_BASE_WEIGHT = 0.6
CONTESTED_VARIABLE_WEIGHT = 0.4
DIFFICULTY_PENALTY_WEIGHT = 0.5
