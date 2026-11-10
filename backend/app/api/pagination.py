"""Opaque cursor pagination: cursor = base64("<created_at.isoformat()>|<id>"),
ordered by (created_at, id) ascending. Shared by every list endpoint so the
response envelope ({items, next_cursor}) is consistent across resources.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol


class HasCreatedAtAndId(Protocol):
    id: uuid.UUID
    created_at: datetime


def encode_cursor(created_at: datetime, id_: uuid.UUID) -> str:
    raw = f"{created_at.isoformat()}|{id_}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        created_at_raw, id_raw = raw.split("|", 1)
        return datetime.fromisoformat(created_at_raw), uuid.UUID(id_raw)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Invalid cursor.") from exc


def paginate[ModelT: HasCreatedAtAndId](
    items: Sequence[ModelT], limit: int
) -> tuple[Sequence[ModelT], str | None]:
    """Expects `items` fetched with a query limited to `limit + 1` rows, ordered
    by (created_at, id). Returns the page (at most `limit`) and the next cursor."""
    if len(items) > limit:
        page = items[:limit]
        last = page[-1]
        return page, encode_cursor(last.created_at, last.id)
    return items, None
