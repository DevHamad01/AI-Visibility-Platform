"""Pydantic request/response models for the brands + competitors API.
These are the single source of truth for both validation and the generated
OpenAPI schema (flask-openapi3 introspects the type hints on each route)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

DOMAIN_PATTERN = re.compile(
    r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)


def validate_domain(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/", 1)[0]
    if not DOMAIN_PATTERN.match(value):
        raise ValueError(
            "domain must be a bare hostname like 'example.com' (no scheme or path)"
        )
    return value


# --- Brands ---------------------------------------------------------------


class BrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    industry: str | None = Field(default=None, max_length=200)
    location_code: int | None = Field(default=None, ge=0)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)

    _validate_domain = field_validator("domain")(validate_domain)


class BrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    domain: str | None = Field(default=None, min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    industry: str | None = Field(default=None, max_length=200)
    location_code: int | None = Field(default=None, ge=0)
    language_code: str | None = Field(default=None, min_length=2, max_length=10)

    @field_validator("domain")
    @classmethod
    def _domain(cls, value: str | None) -> str | None:
        return validate_domain(value) if value is not None else value


class BrandResponse(BaseModel):
    id: uuid.UUID
    name: str
    domain: str
    description: str | None
    industry: str | None
    location_code: int | None
    language_code: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandListResponse(BaseModel):
    items: list[BrandResponse]
    next_cursor: str | None


# --- Competitors -----------------------------------------------------------


class CompetitorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    domain: str = Field(..., min_length=3, max_length=255)

    _validate_domain = field_validator("domain")(validate_domain)


class CompetitorResponse(BaseModel):
    id: uuid.UUID
    brand_id: uuid.UUID
    name: str
    domain: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CompetitorListResponse(BaseModel):
    items: list[CompetitorResponse]
    next_cursor: str | None


# --- Path / query params ----------------------------------------------------


class BrandPath(BaseModel):
    brand_id: uuid.UUID


class CompetitorPath(BaseModel):
    brand_id: uuid.UUID
    competitor_id: uuid.UUID


class ListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    cursor: str | None = Field(default=None)
