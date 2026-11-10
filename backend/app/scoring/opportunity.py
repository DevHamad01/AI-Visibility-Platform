"""Deterministic opportunity scoring (CLAUDE.md section 4). Pure functions
over plain data — no DB/ORM here — so the formula is trivial to unit test
and to explain: every component of the score is a named, visible number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.scoring.config import (
    CONTESTED_BASE_WEIGHT,
    CONTESTED_VARIABLE_WEIGHT,
    DEFAULT_DIFFICULTY_WHEN_UNKNOWN,
    DIFFICULTY_PENALTY_WEIGHT,
    ORGANIC_4_TO_10_SCORE,
    ORGANIC_11_TO_20_SCORE,
    ORGANIC_BEYOND_SCORE,
    ORGANIC_TOP3_SCORE,
    VOLUME_CAP,
)


@dataclass(frozen=True)
class ObservationInput:
    channel: str
    brand_visible: bool
    brand_position: int | None = None


@dataclass(frozen=True)
class ScoringInput:
    search_volume: int | None
    keyword_difficulty: float | None
    competition: float | None
    observations: list[ObservationInput]
    competitors_visible_count: int
    tracked_competitor_count: int


@dataclass(frozen=True)
class ScoreComponents:
    demand: float
    visibility: float
    gap: float
    contested: float
    difficulty: float
    score: float

    def as_dict(self) -> dict:
        return {
            "demand": self.demand,
            "visibility": self.visibility,
            "gap": self.gap,
            "contested": self.contested,
            "difficulty": self.difficulty,
            "score": self.score,
        }


def _organic_presence(position: int | None) -> float:
    if position is None:
        return ORGANIC_BEYOND_SCORE
    if position <= 3:
        return ORGANIC_TOP3_SCORE
    if position <= 10:
        return ORGANIC_4_TO_10_SCORE
    if position <= 20:
        return ORGANIC_11_TO_20_SCORE
    return ORGANIC_BEYOND_SCORE


def _channel_presence(obs: ObservationInput) -> float:
    if obs.channel == "google_organic":
        return _organic_presence(obs.brand_position)
    return 1.0 if obs.brand_visible else 0.0


def compute_demand(search_volume: int | None) -> float:
    if not search_volume or search_volume <= 0:
        return 0.0
    return min(1.0, math.log10(1 + search_volume) / math.log10(1 + VOLUME_CAP))


def compute_visibility(observations: list[ObservationInput]) -> float:
    if not observations:
        return 0.0
    return sum(_channel_presence(o) for o in observations) / len(observations)


def compute_contested(competitors_visible_count: int, tracked_competitor_count: int) -> float:
    if tracked_competitor_count <= 0:
        return 0.0
    return max(0.0, min(1.0, competitors_visible_count / tracked_competitor_count))


def compute_difficulty(keyword_difficulty: float | None, competition: float | None) -> float:
    if keyword_difficulty is not None:
        return max(0.0, min(1.0, keyword_difficulty / 100))
    if competition is not None:
        return max(0.0, min(1.0, competition))
    return DEFAULT_DIFFICULTY_WHEN_UNKNOWN


def score_opportunity(data: ScoringInput) -> ScoreComponents:
    demand = compute_demand(data.search_volume)
    visibility = compute_visibility(data.observations)
    gap = 1.0 - visibility
    contested = compute_contested(data.competitors_visible_count, data.tracked_competitor_count)
    difficulty = compute_difficulty(data.keyword_difficulty, data.competition)
    score = (
        100
        * demand
        * gap
        * (CONTESTED_BASE_WEIGHT + CONTESTED_VARIABLE_WEIGHT * contested)
        * (1 - DIFFICULTY_PENALTY_WEIGHT * difficulty)
    )
    return ScoreComponents(
        demand=round(demand, 4),
        visibility=round(visibility, 4),
        gap=round(gap, 4),
        contested=round(contested, 4),
        difficulty=round(difficulty, 4),
        score=round(score, 2),
    )


def rank_scores(scores: list[float]) -> list[int]:
    """1 = highest score. Ties keep the input order (stable) so ranking is
    deterministic given the same queries in the same order every time."""
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    ranks = [0] * len(scores)
    for rank, index in enumerate(order, start=1):
        ranks[index] = rank
    return ranks
