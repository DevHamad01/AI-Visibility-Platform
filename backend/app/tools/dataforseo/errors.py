"""Argument validation failures never reach the HTTP layer or raise into the
pipeline graph — they're a plain value a caller checks for, per CLAUDE.md
section 4: "invalid/partial args → dropped + logged, never executed"."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolArgumentError:
    tool: str
    errors: list[dict[str, Any]]
    raw_args: dict[str, Any]
