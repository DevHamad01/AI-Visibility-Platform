"""Opportunity scoring: deterministic components and ranking (CLAUDE.md
section 4). Pure functions — no DB, no mocks."""

from __future__ import annotations

from app.scoring.opportunity import (
    ObservationInput,
    ScoringInput,
    compute_contested,
    compute_demand,
    compute_difficulty,
    compute_visibility,
    rank_scores,
    score_opportunity,
)


def test_demand_scales_with_log_volume_and_caps_at_one() -> None:
    assert compute_demand(None) == 0.0
    assert compute_demand(0) == 0.0
    assert 0.0 < compute_demand(100) < compute_demand(10_000) < 1.0
    assert compute_demand(50_000) == 1.0
    assert compute_demand(1_000_000) == 1.0  # capped, never exceeds 1


def test_visibility_averages_per_channel_presence() -> None:
    observations = [
        ObservationInput(channel="google_organic", brand_visible=True, brand_position=2),  # 1.0
        ObservationInput(channel="google_ai_overview", brand_visible=False),  # 0.0
    ]
    assert compute_visibility(observations) == 0.5


def test_organic_position_bands() -> None:
    top3 = ObservationInput(channel="google_organic", brand_visible=True, brand_position=1)
    mid = ObservationInput(channel="google_organic", brand_visible=True, brand_position=7)
    low = ObservationInput(channel="google_organic", brand_visible=True, brand_position=15)
    beyond = ObservationInput(channel="google_organic", brand_visible=False, brand_position=None)
    assert compute_visibility([top3]) == 1.0
    assert compute_visibility([mid]) == 0.6
    assert compute_visibility([low]) == 0.2
    assert compute_visibility([beyond]) == 0.0


def test_contested_is_share_of_tracked_competitors_visible() -> None:
    assert compute_contested(0, 0) == 0.0
    assert compute_contested(2, 4) == 0.5
    assert compute_contested(4, 4) == 1.0
    assert compute_contested(10, 4) == 1.0  # clamped


def test_difficulty_prefers_keyword_difficulty_then_competition_then_default() -> None:
    assert compute_difficulty(60, 0.2) == 0.6  # keyword_difficulty wins
    assert compute_difficulty(None, 0.3) == 0.3  # falls back to competition
    assert compute_difficulty(None, None) == 0.5  # neutral default


def test_score_is_zero_when_fully_visible_no_gap() -> None:
    fully_visible = ScoringInput(
        search_volume=10_000,
        keyword_difficulty=50,
        competition=None,
        observations=[ObservationInput(channel="google_organic", brand_visible=True, brand_position=1)],
        competitors_visible_count=1,
        tracked_competitor_count=2,
    )
    components = score_opportunity(fully_visible)
    assert components.gap == 0.0
    assert components.score == 0.0  # no opportunity if we're already fully visible


def test_score_is_zero_with_no_search_volume() -> None:
    no_demand = ScoringInput(
        search_volume=0,
        keyword_difficulty=50,
        competition=None,
        observations=[],
        competitors_visible_count=0,
        tracked_competitor_count=2,
    )
    assert score_opportunity(no_demand).score == 0.0


def test_score_is_higher_for_contested_queries_than_uncontested() -> None:
    base = {
        "search_volume": 5_000,
        "keyword_difficulty": 40,
        "competition": None,
        "observations": [],
        "tracked_competitor_count": 4,
    }
    uncontested = score_opportunity(ScoringInput(**base, competitors_visible_count=0))
    contested = score_opportunity(ScoringInput(**base, competitors_visible_count=4))
    assert contested.score > uncontested.score


def test_score_is_lower_for_harder_keywords() -> None:
    base = {
        "search_volume": 5_000,
        "competition": None,
        "observations": [],
        "competitors_visible_count": 2,
        "tracked_competitor_count": 4,
    }
    easy = score_opportunity(ScoringInput(**base, keyword_difficulty=10))
    hard = score_opportunity(ScoringInput(**base, keyword_difficulty=90))
    assert easy.score > hard.score


def test_rank_scores_is_deterministic_and_stable_on_ties() -> None:
    scores = [10.0, 50.0, 50.0, 0.0, 30.0]
    ranks = rank_scores(scores)
    # highest score (index 1, first of the tied pair) ranks 1, its tie (index 2) ranks 2
    assert ranks == [4, 1, 2, 5, 3]
    # same input always produces the same ranking
    assert rank_scores(scores) == ranks
