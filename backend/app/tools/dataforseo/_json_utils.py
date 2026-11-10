"""Small defensive helpers for parsing DataForSEO SERP item nesting that the
docs describe inconsistently across item types (ai_overview/people_also_ask
sub-objects vary by surface). These walk whatever shape comes back instead
of assuming one exact nesting, so an unexpected shape degrades to an empty
list rather than raising."""

from __future__ import annotations

from typing import Any


def find_items_by_type_substring(items: list[dict[str, Any]], substring: str) -> list[dict[str, Any]]:
    return [item for item in items if substring in str(item.get("type", ""))]


def collect_strings_by_key(obj: Any, key: str, _depth: int = 0) -> list[str]:
    """Recursively collects every string value found under `key` anywhere
    inside `obj` (dicts/lists), e.g. every "url" in a nested AI Overview
    reference tree. Bounded depth to stay cheap and loop-safe."""
    if _depth > 8:
        return []
    found: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                found.append(v)
            else:
                found.extend(collect_strings_by_key(v, key, _depth + 1))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(collect_strings_by_key(v, key, _depth + 1))
    return found
