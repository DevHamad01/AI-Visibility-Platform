"""Normalizing and comparing domains/URLs that come back from DataForSEO
against the brand's and competitors' tracked domains. Deliberately simple —
exact match after stripping scheme/www/port, plus subdomain matching — good
enough for matching real SERP/AI-Overview domains without over-engineering
public-suffix-list-grade parsing for a take-home project.
"""

from __future__ import annotations

from urllib.parse import urlparse


def normalize_domain(value: str) -> str:
    value = value.strip().lower()
    if "://" in value:
        value = urlparse(value).netloc or value
    if value.startswith("www."):
        value = value[4:]
    return value.split(":")[0].split("/")[0]


def domain_matches(candidate: str, target: str) -> bool:
    c, t = normalize_domain(candidate), normalize_domain(target)
    if not c or not t:
        return False
    return c == t or c.endswith(f".{t}") or t.endswith(f".{c}")


def name_matches(candidate: str | None, target: str) -> bool:
    """Case-insensitive equality or substring match, for matching a brand
    *name* (e.g. an LLM Mentions `brand_entities[].title`) against a tracked
    brand/competitor name — those come back as free text, not domains."""
    if not candidate:
        return False
    c, t = candidate.strip().lower(), target.strip().lower()
    if not c or not t:
        return False
    return c == t or c in t or t in c
