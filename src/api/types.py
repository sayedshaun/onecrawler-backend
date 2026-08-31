"""Shared request-parameter types for the API layer.

Every id column is UUID(as_uuid=False), so ids stay `str` end to end. These types only
reject a malformed id up front with a 422, instead of letting it reach asyncpg and
raise a DataError from inside the query (which surfaces as a 500).
"""

from typing import Annotated

from fastapi import Path, Query
from pydantic import StringConstraints

_UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

UuidPath = Annotated[str, Path(pattern=_UUID_PATTERN)]
UuidQuery = Annotated[str | None, Query(pattern=_UUID_PATTERN)]
UuidStr = Annotated[str, StringConstraints(pattern=_UUID_PATTERN)]
