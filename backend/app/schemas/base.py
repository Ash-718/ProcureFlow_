"""
Schema foundations: camelCase aliasing, Java-compatible encodings, `Page<T>`.

The frontend is typed against Jackson's output, so this module's job is to make
Pydantic produce byte-equivalent JSON. Three encodings were verified against
live Spring responses (captured in `tests/fixtures/spring_contract.json`) and
each is a place a naive port silently drifts:

**camelCase.** Pydantic emits snake_case by default. Every schema derives from
:class:`CamelModel`, and FastAPI serialises with ``by_alias=True``, so
``full_name`` goes out as ``fullName``. A mismatch does not error — the field
simply arrives ``undefined`` and the UI renders blank.

**Numbers.** Jackson writes ``BigDecimal`` as a JSON *number* with trailing
zeros stripped: ``NUMERIC(5,2)`` ``0.40`` appears as ``0.4``, and ``75.00`` as
``75.0``. Pydantic serialises ``Decimal`` as a *string* (``"0.40"``), which
would turn ``overallScore.toFixed(1)`` into a runtime error. Response schemas
therefore declare ``float``, never ``Decimal``.

**Timestamps.** Java's ``Instant.toString()`` produces ``2025-08-02T20:12:00.092961Z``
— UTC, ``Z`` suffix, and a fractional part of 0, 3, 6 or 9 digits depending on
the value. Python's ``isoformat()`` produces ``+00:00`` and always 0 or 6
digits. :func:`format_instant` reproduces Java's rule for microsecond-precision
values, which is every value PostgreSQL's ``TIMESTAMPTZ`` can hold.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Annotated, Generic, Sequence, TypeVar

from pydantic import BaseModel, ConfigDict, PlainSerializer
from pydantic.alias_generators import to_camel

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Encodings
# ---------------------------------------------------------------------------

def format_instant(value: datetime | None) -> str | None:
    """
    Render a datetime the way Java's ``Instant.toString()`` does.

    Java emits no fractional part when the value is whole-second, three digits
    when it is whole-millisecond, and six when it is not. Python's
    ``isoformat()`` always emits six (or none), so the millisecond case is
    handled explicitly. Both forms parse identically in JavaScript; matching
    exactly simply removes a class of diff noise when comparing against the
    Java backend.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)

    base = value.strftime("%Y-%m-%dT%H:%M:%S")
    micro = value.microsecond
    if micro == 0:
        return base + "Z"
    if micro % 1000 == 0:
        return f"{base}.{micro // 1000:03d}Z"
    return f"{base}.{micro:06d}Z"


def format_local_date(value: date | None) -> str | None:
    """Java's ``LocalDate.toString()`` — plain ``YYYY-MM-DD``."""
    return None if value is None else value.isoformat()


#: ``Instant`` on the Java side. Always serialises to a string.
Instant = Annotated[
    datetime,
    PlainSerializer(format_instant, return_type=str, when_used="always"),
]
OptionalInstant = Annotated[
    datetime | None,
    PlainSerializer(format_instant, return_type=str | None, when_used="always"),
]

#: ``LocalDate`` on the Java side.
LocalDate = Annotated[
    date,
    PlainSerializer(format_local_date, return_type=str, when_used="always"),
]
OptionalLocalDate = Annotated[
    date | None,
    PlainSerializer(format_local_date, return_type=str | None, when_used="always"),
]


# ---------------------------------------------------------------------------
# Base models
# ---------------------------------------------------------------------------

class CamelModel(BaseModel):
    """
    Response base: camelCase output, populated straight from ORM objects.

    ``populate_by_name`` keeps snake_case construction working in Python
    (``ChallengeResponse(problem_statement=...)``) while the wire stays
    camelCase.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
        ser_json_timedelta="float",
    )


class CamelRequest(BaseModel):
    """
    Request base.

    Accepts camelCase (what the frontend sends) *and* snake_case, so tests and
    internal callers can use Python-natural names. ``extra="ignore"`` mirrors
    Jackson's default of discarding unknown properties rather than 400-ing —
    the frontend sends a few fields some endpoints do not consume.
    """

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        str_strip_whitespace=True,
    )


# ---------------------------------------------------------------------------
# Spring's Page<T>
# ---------------------------------------------------------------------------

class SortInfo(BaseModel):
    """Spring's nested `sort` object. Emitted for shape parity."""

    model_config = ConfigDict(populate_by_name=True)

    sorted: bool = True
    unsorted: bool = False
    empty: bool = False


class PageableInfo(BaseModel):
    """Spring's nested `pageable` object."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    page_number: int
    page_size: int
    sort: SortInfo = SortInfo()
    offset: int
    paged: bool = True
    unpaged: bool = False


class Page(BaseModel, Generic[T]):
    """
    A Spring Data `PageImpl`, reproduced in full.

    `frontend/src/types/index.ts` only declares five of these fields, but the
    live endpoint returns eleven. Emitting the complete shape costs nothing and
    means anything reading `first`, `last`, `numberOfElements` or `pageable`
    later still works — whereas emitting only five would be a silent
    regression the TypeScript types could not catch.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    content: list[T]
    pageable: PageableInfo
    total_elements: int
    total_pages: int
    last: bool
    first: bool
    size: int
    number: int
    sort: SortInfo = SortInfo()
    number_of_elements: int
    empty: bool

    @classmethod
    def create(cls, items: Sequence[T], *, page: int, size: int,
               total: int, sorted_: bool = True) -> "Page[T]":
        """
        Build a page from a slice plus the total row count.

        ``page`` is zero-based, matching Spring and the frontend's
        `AdminApi.auditLogs(page = 0, size = 50)`.
        """
        safe_size = max(size, 1)
        total_pages = (total + safe_size - 1) // safe_size
        content = list(items)
        sort_info = SortInfo(sorted=sorted_, unsorted=not sorted_, empty=not sorted_)
        return cls(
            content=content,
            pageable=PageableInfo(
                page_number=page,
                page_size=size,
                sort=sort_info,
                offset=page * safe_size,
            ),
            total_elements=total,
            total_pages=total_pages,
            # Spring reports `last` true for an empty result set as well.
            last=page >= total_pages - 1,
            first=page == 0,
            size=size,
            number=page,
            sort=sort_info,
            number_of_elements=len(content),
            empty=not content,
        )


__all__ = [
    "CamelModel",
    "CamelRequest",
    "Instant",
    "LocalDate",
    "OptionalInstant",
    "OptionalLocalDate",
    "Page",
    "PageableInfo",
    "SortInfo",
    "format_instant",
    "format_local_date",
]
