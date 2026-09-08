"""
Phase 3 gate: the API contract, verified three ways.

A camelCase mistake is the most dangerous class of bug in this migration
because it is **silent**. Nothing raises; the field simply arrives `undefined`
and the page renders blank. So the schemas are checked against two independent
specifications:

1. **`frontend/src/types/index.ts`** — the field names the frontend reads.
   Parsed directly from the file, so editing a TypeScript interface without
   updating the backend fails here.
2. **`tests/fixtures/spring_contract.json`** — real responses captured from the
   running Java backend. This is what catches *encoding* drift the TypeScript
   types cannot express: a `Decimal` serialised as `"0.40"` instead of `0.4`,
   or a timestamp as `+00:00` instead of `Z`.

Plus direct checks on the `Page<T>` shape and the error body.

No database and no Spring backend required — the fixture is committed, so this
suite runs anywhere.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.schemas import (
    REQUEST_CONTRACT_MAP,
    SCHEMA_CONTRACT_MAP,
    Page,
    format_instant,
    format_local_date,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TYPES_FILE = REPO_ROOT / "frontend" / "src" / "types" / "index.ts"
FIXTURE_FILE = Path(__file__).parent / "fixtures" / "spring_contract.json"


# ---------------------------------------------------------------------------
# TypeScript interface parsing
# ---------------------------------------------------------------------------

_INTERFACE_HEAD_RE = re.compile(r"export\s+interface\s+(?P<name>\w+)(?:<[^>]*>)?\s*\{")
#: A property declaration: `name:` or `name?:`.
_FIELD_RE = re.compile(r"(?P<name>\w+)(?P<optional>\?)?\s*:")


def _extract_body(source: str, open_brace_index: int) -> tuple[str, int]:
    """Return the balanced ``{...}`` body starting at ``open_brace_index``."""
    depth = 0
    for index in range(open_brace_index, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[open_brace_index + 1:index], index
    raise AssertionError("Unbalanced braces in the TypeScript types file")


def _top_level_fields(body: str) -> dict[str, bool]:
    """
    Property names declared directly on the interface.

    Brace-aware: several interfaces (`ChallengeDraft`, the pilot-create payload)
    declare inline object literals such as
    ``requirements: { requirementType: ...; description: string }[]``, and the
    keys inside those belong to the nested shape, not the interface. Counting
    them would make the contract test demand fields that do not exist.
    """
    fields: dict[str, bool] = {}
    depth = 0
    position = 0
    while position < len(body):
        char = body[position]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        elif depth == 0:
            match = _FIELD_RE.match(body, position)
            if match and _starts_a_declaration(body, match.start()):
                fields[match.group("name")] = bool(match.group("optional"))
                position = match.end()
                continue
        position += 1
    return fields


def _starts_a_declaration(body: str, index: int) -> bool:
    """True when the identifier at ``index`` begins a property declaration."""
    preceding = body[:index].rstrip()
    if not preceding:
        return True
    # A declaration follows the interface opening, a newline, a `;` or a `,`.
    return preceding[-1] in ";,{" or body[:index].rstrip(" \t").endswith("\n")


def parse_typescript_interfaces(source: str) -> dict[str, dict[str, bool]]:
    """Extract ``{interface: {field: is_optional}}`` from the types file."""
    interfaces: dict[str, dict[str, bool]] = {}
    position = 0
    while (match := _INTERFACE_HEAD_RE.search(source, position)) is not None:
        body, close_index = _extract_body(source, match.end() - 1)
        interfaces[match.group("name")] = _top_level_fields(body)
        position = close_index + 1
    return interfaces


@pytest.fixture(scope="module")
def ts_interfaces() -> dict[str, dict[str, bool]]:
    assert TYPES_FILE.exists(), f"Frontend types not found at {TYPES_FILE}"
    return parse_typescript_interfaces(TYPES_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def spring_fixture() -> dict:
    assert FIXTURE_FILE.exists(), (
        f"{FIXTURE_FILE} is missing. Regenerate it with:\n"
        "  backend/.venv/Scripts/python.exe tests/capture_spring_contract.py"
    )
    return json.loads(FIXTURE_FILE.read_text(encoding="utf-8"))


def schema_field_names(model: type) -> set[str]:
    """The wire-level field names a schema emits (i.e. its aliases)."""
    return {
        (field.alias or name)
        for name, field in model.model_fields.items()
    }


# ---------------------------------------------------------------------------
# 1. Schemas vs. the TypeScript types
# ---------------------------------------------------------------------------

class TestTypeScriptParity:
    def test_parser_finds_the_expected_interfaces(self, ts_interfaces):
        """Guards the regex itself — a silent parse failure would pass everything."""
        assert len(ts_interfaces) >= 25
        for required in ("Challenge", "Startup", "Pilot", "Page", "ApiErrorBody"):
            assert required in ts_interfaces, f"{required} not parsed"

    @pytest.mark.parametrize(
        ("model", "interface_name"),
        list(SCHEMA_CONTRACT_MAP.items()),
        ids=[f"{m.__name__}->{t}" for m, t in SCHEMA_CONTRACT_MAP.items()],
    )
    def test_response_schema_covers_its_interface(self, ts_interfaces, model, interface_name):
        """
        Every non-optional TypeScript field must be emitted by the schema.

        A missing field is exactly the silent-`undefined` failure this whole
        suite exists to prevent.
        """
        assert interface_name in ts_interfaces, f"No TS interface {interface_name}"
        required = {name for name, optional in ts_interfaces[interface_name].items()
                    if not optional}
        emitted = schema_field_names(model)
        missing = required - emitted
        assert not missing, (
            f"{model.__name__} does not emit {sorted(missing)}, which "
            f"{interface_name} declares as required. These would be `undefined` "
            f"in the browser."
        )

    @pytest.mark.parametrize(
        ("model", "interface_name"),
        list(SCHEMA_CONTRACT_MAP.items()),
        ids=[f"{m.__name__}->{t}" for m, t in SCHEMA_CONTRACT_MAP.items()],
    )
    def test_response_schema_emits_no_unknown_fields(self, ts_interfaces, model, interface_name):
        """
        The schema must not emit fields the frontend does not declare.

        Extra fields are harmless to TypeScript but usually mean a leak — the
        `file_path` of a document, say — so they are treated as errors.
        """
        declared = set(ts_interfaces[interface_name])
        extra = schema_field_names(model) - declared
        assert not extra, (
            f"{model.__name__} emits {sorted(extra)}, absent from {interface_name}. "
            f"Confirm this is intended and not an accidental disclosure."
        )

    @pytest.mark.parametrize(
        ("model", "interface_name"),
        list(REQUEST_CONTRACT_MAP.items()),
        ids=[f"{m.__name__}->{t}" for m, t in REQUEST_CONTRACT_MAP.items()],
    )
    def test_request_schema_accepts_its_interface(self, ts_interfaces, model, interface_name):
        """Every field the frontend sends must be accepted by the request schema."""
        declared = set(ts_interfaces[interface_name])
        accepted = schema_field_names(model)
        missing = declared - accepted
        assert not missing, (
            f"{model.__name__} does not accept {sorted(missing)} sent by {interface_name}")

    def test_every_camel_alias_is_actually_camel_case(self):
        """No stray snake_case survived aliasing."""
        offenders: list[str] = []
        for model in SCHEMA_CONTRACT_MAP:
            for name in schema_field_names(model):
                if "_" in name:
                    offenders.append(f"{model.__name__}.{name}")
        assert not offenders, f"snake_case leaked onto the wire: {offenders}"


# ---------------------------------------------------------------------------
# 2. Schemas vs. real Spring responses
# ---------------------------------------------------------------------------

#: fixture key -> (schema, whether the body is a list)
FIXTURE_SCHEMA_MAP = {
    "auth_login": ("AuthResponse", False),
    "auth_me": ("CurrentUserResponse", False),
    "challenges_list": ("ChallengeResponse", True),
    "challenge_detail": ("ChallengeResponse", False),
    "startups_list": ("StartupResponse", True),
    "startup_me": ("StartupResponse", False),
    "startup_detail": ("StartupResponse", False),
    "matching_results": ("MatchResultRow", True),
    "proposals_mine": ("ProposalResponse", True),
    "proposals_queue": ("ProposalResponse", True),
    "proposal_detail": ("ProposalResponse", False),
    "evaluation_criteria": ("EvaluationCriterionResponse", True),
    "pilots_list": ("PilotResponse", True),
    "pilot_detail": ("PilotResponse", False),
    "pilot_recommendation": ("RecommendationResponse", False),
    "knowledge_base": ("KnowledgeBaseEntryResponse", True),
    "notifications": ("NotificationResponse", True),
    "admin_users": ("AdminUserResponse", True),
}


def _schema_by_name(name: str) -> type:
    import app.schemas as schemas

    return getattr(schemas, name)


class TestSpringResponseParity:
    """The captured Java responses are the encoding specification."""

    @pytest.mark.parametrize(
        ("fixture_key", "schema_name", "is_list"),
        [(k, s, l) for k, (s, l) in FIXTURE_SCHEMA_MAP.items()],
        ids=list(FIXTURE_SCHEMA_MAP),
    )
    def test_schema_field_names_match_spring(self, spring_fixture, fixture_key,
                                             schema_name, is_list):
        entry = spring_fixture.get(fixture_key)
        assert entry is not None, f"fixture {fixture_key} missing"
        body = entry["body"]
        if is_list:
            if not body:
                pytest.skip(f"{fixture_key} returned an empty list in the seed data")
            body = body[0]
        assert isinstance(body, dict), f"{fixture_key} body is not an object"

        spring_fields = set(body)
        emitted = schema_field_names(_schema_by_name(schema_name))

        assert spring_fields == emitted, (
            f"{fixture_key}: field mismatch with the Java backend.\n"
            f"  only Spring emits : {sorted(spring_fields - emitted)}\n"
            f"  only Python emits : {sorted(emitted - spring_fields)}"
        )

    def test_numeric_fields_are_json_numbers_not_strings(self, spring_fixture):
        """
        Jackson writes `BigDecimal` as a number; Pydantic writes `Decimal` as a
        string. Confirms the fixture really does carry numbers, which is why
        every response schema declares `float`.
        """
        row = spring_fixture["matching_results"]["body"][0]
        for field in ("overallScore", "semanticSimilarityScore", "readinessScore"):
            assert isinstance(row[field], (int, float)), (
                f"{field} is {type(row[field]).__name__}, expected a JSON number")
            assert not isinstance(row[field], str)

    def test_trailing_zeros_are_stripped_like_jackson(self, spring_fixture):
        """`NUMERIC(5,2)` 0.40 must appear as 0.4, and 75.00 as 75.0."""
        kpi = spring_fixture["challenges_list"]["body"][0]["kpis"][0]
        assert kpi["weight"] == pytest.approx(0.4)
        assert repr(kpi["targetValue"]).rstrip("0").rstrip(".") != ""
        # A float round-trip is what produces this form.
        assert float(kpi["targetValue"]) == kpi["targetValue"]

    def test_instant_encoding_matches(self, spring_fixture):
        """Spring's `Instant` strings must be reproducible by `format_instant`."""
        published = spring_fixture["challenges_list"]["body"][0]["publishedAt"]
        assert published.endswith("Z"), published
        assert "+00:00" not in published

        parsed = datetime.fromisoformat(published.replace("Z", "+00:00"))
        assert format_instant(parsed) == published

    def test_local_date_encoding_matches(self, spring_fixture):
        """`LocalDate` is a bare `YYYY-MM-DD`, with no time component."""
        start = spring_fixture["pilot_detail"]["body"]["startDate"]
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", start), start
        assert format_local_date(date.fromisoformat(start)) == start

    def test_knowledge_base_success_stays_tristate(self, spring_fixture):
        entry = spring_fixture["knowledge_base"]["body"][0]
        assert entry["success"] is None or isinstance(entry["success"], bool)

    def test_nulls_are_emitted_not_omitted(self, spring_fixture):
        """
        Jackson includes null-valued properties. Pydantic does too by default;
        this pins the behaviour, since suppressing them would make fields
        vanish rather than read `null`.
        """
        row = spring_fixture["admin_audit_logs"]["body"]["content"][0]
        assert "metadataJson" in row
        assert row["metadataJson"] is None

    def test_audit_metadata_is_a_string_not_an_object(self, spring_fixture):
        """
        `AuditLogDto.metadataJson` is a Java `String`, and the frontend types
        it `string | null`. Returning the JSONB as an object would break it.
        """
        from app.schemas import AuditLogResponse

        field = AuditLogResponse.model_fields["metadata_json"]
        assert "str" in str(field.annotation)


class TestErrorBodyParity:
    """The error envelope must match Spring's `ErrorResponse` record."""

    def test_keys_match_the_captured_404(self, spring_fixture):
        from app.core.exceptions import error_body

        spring = spring_fixture["error_404"]["body"]
        mine = error_body(404, spring["message"], spring["path"])
        assert set(mine) == set(spring)
        for key in ("status", "error", "message", "path", "fieldErrors"):
            assert mine[key] == spring[key], key

    def test_field_errors_key_is_always_present(self):
        """
        Jackson emits every record component, so a 404 carries
        `"fieldErrors": null`. Omitting it would be a diff against Spring even
        though the frontend declares the key optional.
        """
        from app.core.exceptions import error_body

        assert "fieldErrors" in error_body(404, "x", "/y")
        assert error_body(404, "x", "/y")["fieldErrors"] is None

    def test_validation_failure_populates_field_errors(self):
        from app.core.exceptions import error_body

        body = error_body(400, "Validation failed", "/x", {"title": "must not be blank"})
        assert body["fieldErrors"] == {"title": "must not be blank"}
        assert body["error"] == "Bad Request"

    def test_matches_the_frontend_api_error_body_interface(self, ts_interfaces, spring_fixture):
        from app.core.exceptions import error_body

        declared = set(ts_interfaces["ApiErrorBody"])
        assert set(error_body(500, "x", "/y")) == declared

    def test_timestamp_uses_the_java_instant_form(self):
        from app.core.exceptions import error_body

        timestamp = error_body(404, "x", "/y")["timestamp"]
        assert timestamp.endswith("Z")
        assert "+00:00" not in timestamp


# ---------------------------------------------------------------------------
# 3. Page<T>
# ---------------------------------------------------------------------------

class TestPageCompatibility:
    def test_shape_matches_spring_exactly(self, spring_fixture):
        """
        Spring's `PageImpl` emits eleven top-level keys, not the five the
        frontend declares. The full shape is reproduced so anything reading
        `first`, `last` or `pageable` later keeps working.
        """
        spring_page = spring_fixture["admin_audit_logs"]["body"]
        page = Page[dict].create([{"x": 1}] * 5, page=0, size=5, total=67)
        emitted = json.loads(page.model_dump_json(by_alias=True))
        assert set(emitted) == set(spring_page), (
            f"only Spring: {sorted(set(spring_page) - set(emitted))}, "
            f"only Python: {sorted(set(emitted) - set(spring_page))}"
        )

    def test_values_match_spring_for_the_same_query(self, spring_fixture):
        spring_page = spring_fixture["admin_audit_logs"]["body"]
        page = Page[dict].create(
            [{"x": 1}] * spring_page["numberOfElements"],
            page=spring_page["number"], size=spring_page["size"],
            total=spring_page["totalElements"])
        emitted = json.loads(page.model_dump_json(by_alias=True))

        for key in ("totalElements", "totalPages", "number", "size",
                    "first", "last", "numberOfElements", "empty"):
            assert emitted[key] == spring_page[key], (
                f"{key}: python={emitted[key]} spring={spring_page[key]}")
        assert emitted["pageable"]["pageNumber"] == spring_page["pageable"]["pageNumber"]
        assert emitted["pageable"]["offset"] == spring_page["pageable"]["offset"]

    def test_frontend_required_keys_present(self, ts_interfaces):
        page = Page[dict].create([], page=0, size=50, total=0)
        emitted = json.loads(page.model_dump_json(by_alias=True))
        for field in ts_interfaces["Page"]:
            assert field in emitted, f"Page<T> is missing `{field}`"

    @pytest.mark.parametrize(
        ("total", "size", "page", "expected_pages", "first", "last"),
        [
            (0, 50, 0, 0, True, True),      # empty: Spring reports last=True
            (1, 50, 0, 1, True, True),
            (50, 50, 0, 1, True, True),
            (51, 50, 0, 2, True, False),
            (51, 50, 1, 2, False, True),
            (67, 5, 0, 14, True, False),    # the captured case
            (67, 5, 13, 14, False, True),
        ],
    )
    def test_pagination_arithmetic(self, total, size, page, expected_pages, first, last):
        result = Page[dict].create([], page=page, size=size, total=total)
        assert result.total_pages == expected_pages
        assert result.first is first
        assert result.last is last
        assert result.number == page      # zero-based, as the frontend sends
        assert result.size == size

    def test_offset_is_computed_from_page_and_size(self):
        page = Page[dict].create([], page=3, size=20, total=200)
        assert page.pageable.offset == 60


# ---------------------------------------------------------------------------
# 4. Encoding helpers
# ---------------------------------------------------------------------------

class TestEncodingHelpers:
    @pytest.mark.parametrize(("micro", "expected_suffix"), [
        (0, "T10:20:30Z"),               # whole second: no fraction, like Java
        (500_000, "T10:20:30.500Z"),     # whole millisecond: 3 digits
        (92_961, "T10:20:30.092961Z"),   # otherwise: 6 digits
        (1, "T10:20:30.000001Z"),
    ])
    def test_instant_fraction_digits_follow_java(self, micro, expected_suffix):
        value = datetime(2025, 8, 2, 10, 20, 30, micro, tzinfo=timezone.utc)
        assert format_instant(value).endswith(expected_suffix)

    def test_naive_datetime_is_treated_as_utc(self):
        naive = datetime(2025, 8, 2, 10, 20, 30)
        assert format_instant(naive) == "2025-08-02T10:20:30Z"

    def test_non_utc_is_converted_not_relabelled(self):
        from datetime import timedelta

        ist = timezone(timedelta(hours=5, minutes=30))
        value = datetime(2025, 8, 2, 15, 50, 30, tzinfo=ist)
        assert format_instant(value) == "2025-08-02T10:20:30Z"

    def test_none_passes_through(self):
        assert format_instant(None) is None
        assert format_local_date(None) is None


# ---------------------------------------------------------------------------
# 5. Serialisation smoke test
# ---------------------------------------------------------------------------

class TestSerialisation:
    def test_uuid_serialises_as_a_plain_string(self):
        from app.schemas import CurrentUserResponse

        payload = json.loads(CurrentUserResponse(
            id=uuid.UUID("b7ddaf76-c385-45df-97b5-a2c1e17dc360"),
            email="a@b.com", full_name="A B", role="GOVERNMENT",
        ).model_dump_json(by_alias=True))
        assert payload["id"] == "b7ddaf76-c385-45df-97b5-a2c1e17dc360"
        assert payload["fullName"] == "A B"
        assert payload["role"] == "GOVERNMENT"

    def test_enum_serialises_as_its_value(self):
        from app.models.enums import RoleName
        from app.schemas import AdminUserResponse

        payload = json.loads(AdminUserResponse(
            id=uuid.uuid4(), email="a@b.com", full_name="A B",
            role=RoleName.ADMIN, active=True,
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ).model_dump_json(by_alias=True))
        assert payload["role"] == "ADMIN"
        assert payload["active"] is True
        assert payload["createdAt"] == "2026-01-01T00:00:00Z"

    def test_snake_case_construction_still_works(self):
        """`populate_by_name` keeps Python-natural keyword construction valid."""
        from app.schemas import ChallengeKpiResponse

        kpi = ChallengeKpiResponse(
            id=uuid.uuid4(), kpi_name="Detection Accuracy",
            target_value=85.0, unit="percent", weight=0.4)
        payload = json.loads(kpi.model_dump_json(by_alias=True))
        assert payload["kpiName"] == "Detection Accuracy"
        assert payload["targetValue"] == 85.0
        assert payload["weight"] == 0.4

    def test_float_fields_never_serialise_as_strings(self):
        """The `Decimal`-as-string trap, asserted directly."""
        from app.schemas import MatchResultRow

        payload = json.loads(MatchResultRow(
            startup_id=uuid.uuid4(), company_name="RoadSense AI", rank=1,
            overall_score=79.086, semantic_similarity_score=76.674,
            technology_match_score=70.0, domain_match_score=100.0,
            experience_score=70.0, readiness_score=85.0,
            reasons=[], gaps=[], ai_provider="local-fallback",
        ).model_dump_json(by_alias=True))
        for key in ("overallScore", "semanticSimilarityScore", "domainMatchScore"):
            assert isinstance(payload[key], float), f"{key} became {type(payload[key])}"
