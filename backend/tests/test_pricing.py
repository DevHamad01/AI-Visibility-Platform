import pytest

from app.tools.dataforseo.pricing import estimate_serp_google_organic_cost
from app.tools.dataforseo.serp_google_organic import SerpGoogleOrganicArgs


def test_serp_estimate_covers_depth_operators_and_ai_overview():
    assert estimate_serp_google_organic_cost() == 0.002
    assert estimate_serp_google_organic_cost(15) == 0.004
    assert estimate_serp_google_organic_cost(10, load_async_ai_overview=True) == 0.004
    assert estimate_serp_google_organic_cost(20, keyword="site:example.com intitle:tools") == 0.10


def test_unbounded_paid_paa_expansion_is_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SerpGoogleOrganicArgs(keyword="tools", location_code=2840, people_also_ask_click_depth=1)
