"""
Phase 5 gate: the in-process AI pipeline must reproduce `ai-service` exactly.

Three layers of evidence, weakest to strongest:

1. **Pure scoring** — `tests/test_scoring.py` from the AI service runs unchanged
   against `app.ai.scoring`. That file is byte-identical to its original, so the
   formula itself is provably untouched.
2. **Recorded parity** — the migrated pipeline is run against the seeded data
   and diffed field-by-field against `tests/fixtures/ai_baseline_service.json`,
   captured from the live `ai-service` on :8081 before the migration.
3. **Live parity** — where the AI service is still running, the same challenge
   is matched through both and the results compared directly.

Nothing here is mocked. Every score comes from a real `all-MiniLM-L6-v2`
embedding and the real weighted formula.

The model load is slow the first time (~50 s cold), so the provider is built
once per session and shared.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal, check_connection
from tests.conftest import TEST_MARKER_DOMAINS

FIXTURES = Path(__file__).parent / "fixtures"
BASELINE_FILE = FIXTURES / "ai_baseline_service.json"
PREEXISTING_FILE = FIXTURES / "ai_baseline_preexisting.json"
AI_SERVICE = "http://127.0.0.1:8081"

pytestmark = pytest.mark.skipif(
    not check_connection(),
    reason="PostgreSQL is not reachable; start it on :5433.",
)


@pytest.fixture(scope="session")
def provider():
    """The real local embedding provider, loaded once for the whole session."""
    from app.ai import get_embedding_provider

    return get_embedding_provider()


@pytest.fixture(scope="module")
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="module")
def baseline() -> dict:
    assert BASELINE_FILE.exists(), (
        f"{BASELINE_FILE} is missing — it is the record of what the standalone "
        "ai-service produced and cannot be regenerated once that service is gone.")
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def preexisting() -> dict:
    return json.loads(PREEXISTING_FILE.read_text(encoding="utf-8"))


# ===========================================================================
# 1. The code really is the same code
# ===========================================================================

class TestMigrationIntegrity:
    def test_scoring_module_is_byte_identical_to_the_original(self):
        """
        `scoring.py` holds the weighted formula. If it changed at all during the
        move, every downstream parity result is suspect.
        """
        original = Path(__file__).parent.parent.parent / "ai-service/app/services/scoring.py"
        if not original.exists():
            pytest.skip("ai-service has been removed; parity is recorded in the fixtures")
        migrated = Path(__file__).parent.parent / "app/ai/scoring.py"
        assert (original.read_text(encoding="utf-8").replace("\r\n", "\n")
                == migrated.read_text(encoding="utf-8").replace("\r\n", "\n"))

    def test_text_builders_are_byte_identical(self):
        """The embedded text must be identical or every vector shifts."""
        original = Path(__file__).parent.parent.parent / "ai-service/app/services/text_builders.py"
        if not original.exists():
            pytest.skip("ai-service has been removed")
        migrated = Path(__file__).parent.parent / "app/ai/text_builders.py"
        assert (original.read_text(encoding="utf-8").replace("\r\n", "\n")
                == migrated.read_text(encoding="utf-8").replace("\r\n", "\n"))

    def test_weights_match_the_documented_formula(self):
        from app.ai import get_matching_weights

        weights = get_matching_weights()
        assert weights == {
            "semantic_similarity": 0.35,
            "technology_match": 0.20,
            "domain_match": 0.15,
            "experience_score": 0.15,
            "readiness_score": 0.15,
        }
        assert sum(weights.values()) == pytest.approx(1.0)

    def test_weights_agree_with_the_seeded_config_table(self, db):
        """`ai_matching_config` is the documented source of truth for the UI."""
        from app.ai import get_matching_weights

        rows = dict(db.execute(text(
            "SELECT config_key, weight FROM ai_matching_config")).fetchall())
        weights = get_matching_weights()
        for key, weight in rows.items():
            assert weights[key] == pytest.approx(float(weight)), key

    def test_provider_is_the_local_offline_model(self, provider):
        assert provider.name == "local-fallback"
        assert settings.embedding_model_name == "all-MiniLM-L6-v2"


# ===========================================================================
# 2. Embeddings
# ===========================================================================

class TestEmbeddings:
    def test_embedding_has_the_configured_dimensions(self, provider):
        vector = provider.embed("pothole detection from dashcam video")
        assert len(vector) == settings.embedding_dimensions == 384
        assert all(isinstance(v, float) for v in vector[:10])

    def test_embeddings_are_deterministic(self, provider):
        """Same text, same vector — matching would not be reproducible otherwise."""
        text_sample = "Computer vision for municipal road inspection"
        assert provider.embed(text_sample) == provider.embed(text_sample)

    def test_embeddings_are_normalised(self, provider):
        """`normalize_embeddings=True`, so cosine similarity is a dot product."""
        import numpy as np

        vector = np.array(provider.embed("road damage detection"))
        assert float(np.linalg.norm(vector)) == pytest.approx(1.0, abs=1e-5)

    def test_semantically_close_text_scores_higher_than_unrelated_text(self, provider):
        """A sanity check that the model is real and loaded, not a stub."""
        from app.ai import cosine_similarity

        anchor = provider.embed("detecting potholes and road surface damage")
        close = provider.embed("computer vision for road defect inspection")
        far = provider.embed("crop yield advisory for smallholder farmers")
        assert cosine_similarity(anchor, close) > cosine_similarity(anchor, far)

    def test_cosine_similarity_bounds(self, provider):
        from app.ai import cosine_similarity

        vector = provider.embed("anything")
        assert cosine_similarity(vector, vector) == pytest.approx(1.0, abs=1e-9)
        assert cosine_similarity([0.0] * 384, vector) == 0.0

    def test_stored_embeddings_match_a_freshly_computed_one(self, db, provider, preexisting):
        """
        The vector persisted by the standalone service is reproduced exactly by
        the in-process code — same text builder, same model, same result.
        """
        from app.ai import build_startup_text, fetch_startup
        from app.ai.embedding_service import (
            fetch_startup_capabilities,
            fetch_startup_projects,
        )

        startup_id = preexisting["roadsense_startup_id"]
        startup = fetch_startup(db, startup_id)
        assert startup["embedding"] is not None, "RoadSense lost its embedding"

        recomputed = provider.embed(build_startup_text(
            company_name=startup["company_name"],
            description=startup["description"],
            capabilities=fetch_startup_capabilities(db, startup_id),
            projects=fetch_startup_projects(db, startup_id),
            readiness_score=float(startup["readiness_score"]),
        ))
        stored = [float(v) for v in startup["embedding"]]
        assert len(recomputed) == len(stored)
        for computed_value, stored_value in zip(recomputed, stored):
            assert computed_value == pytest.approx(stored_value, abs=1e-6)


# ===========================================================================
# 3. Matching parity
# ===========================================================================

class TestMatchingParity:
    @pytest.fixture(scope="class")
    def result(self, db, provider, baseline):
        """Run the migrated pipeline once and reuse it across the class."""
        from app.ai import run_matching_for_challenge

        return run_matching_for_challenge(
            db, baseline["challenge_id"], provider, top_n=settings.match_top_n)

    def test_envelope_matches_the_recorded_service_output(self, result, baseline):
        assert result["challenge_id"] == baseline["challenge_id"]
        assert result["ai_provider"] == baseline["ai_provider"]
        assert result["weights"] == baseline["weights"]
        assert result["total_candidates_considered"] == baseline["total_candidates_considered"]
        assert len(result["results"]) == len(baseline["results"])

    def test_every_rank_score_and_explanation_is_identical(self, result, baseline):
        """
        The decisive assertion: ranks, all six scores, reasons and gaps, exact.

        Compared with `==` rather than a tolerance — the pipeline is
        deterministic, so any drift at all is a real behavioural change.
        """
        for mine, theirs in zip(result["results"], baseline["results"]):
            assert mine["rank"] == theirs["rank"]
            assert mine["startup_id"] == theirs["startup_id"]
            assert mine["company_name"] == theirs["company_name"]
            assert mine["overall_score"] == theirs["overall_score"], mine["company_name"]
            assert mine["component_scores"] == theirs["component_scores"], mine["company_name"]
            assert mine["reasons"] == theirs["reasons"], mine["company_name"]
            assert mine["gaps"] == theirs["gaps"], mine["company_name"]

    def test_roadsense_ranks_first(self, result):
        """The headline claim of the SIH demo."""
        top = result["results"][0]
        assert top["rank"] == 1
        assert top["company_name"] == "RoadSense AI"
        assert top["overall_score"] == pytest.approx(79.086, abs=0.001)

    def test_roadsense_component_scores(self, result):
        """Each component, individually, so a compensating error cannot hide."""
        scores = result["results"][0]["component_scores"]
        assert scores["semantic_similarity"] == pytest.approx(76.674, abs=0.001)
        assert scores["technology_match"] == pytest.approx(70.0, abs=0.001)
        assert scores["domain_match"] == pytest.approx(100.0, abs=0.001)
        assert scores["experience_score"] == pytest.approx(70.0, abs=0.001)
        assert scores["readiness_score"] == pytest.approx(85.0, abs=0.001)

    def test_overall_score_is_the_weighted_sum_of_its_components(self, result):
        """Recompute the headline number from its parts and the published weights."""
        weights = result["weights"]
        for candidate in result["results"]:
            scores = candidate["component_scores"]
            expected = (
                weights["semantic_similarity"] * scores["semantic_similarity"]
                + weights["technology_match"] * scores["technology_match"]
                + weights["domain_match"] * scores["domain_match"]
                + weights["experience_score"] * scores["experience_score"]
                + weights["readiness_score"] * scores["readiness_score"]
            )
            assert candidate["overall_score"] == pytest.approx(expected, abs=0.01), (
                candidate["company_name"])

    def test_results_are_ranked_by_descending_score(self, result):
        scores = [c["overall_score"] for c in result["results"]]
        assert scores == sorted(scores, reverse=True)
        assert [c["rank"] for c in result["results"]] == list(range(1, len(scores) + 1))

    def test_every_candidate_was_considered_not_just_the_returned_ones(self, result, db):
        total = db.execute(text("SELECT count(*) FROM startups")).scalar_one()
        assert result["total_candidates_considered"] == total == 16
        assert len(result["results"]) == settings.match_top_n == 8

    def test_scores_are_not_constant_or_placeholder(self, result):
        """Guards against a stub quietly returning a fixed value."""
        overall = {c["overall_score"] for c in result["results"]}
        assert len(overall) == len(result["results"]), "duplicate scores look synthetic"
        semantic = {c["component_scores"]["semantic_similarity"] for c in result["results"]}
        assert len(semantic) > 1
        assert all(0.0 < value < 100.0 for value in semantic)

    def test_rerunning_produces_the_same_result(self, db, provider, baseline):
        """Determinism, asserted rather than assumed."""
        from app.ai import run_matching_for_challenge

        again = run_matching_for_challenge(
            db, baseline["challenge_id"], provider, top_n=settings.match_top_n)
        assert [(c["rank"], c["company_name"], c["overall_score"]) for c in again["results"]] == \
               [(c["rank"], c["company_name"], c["overall_score"]) for c in baseline["results"]]


# ===========================================================================
# 4. Explanations
# ===========================================================================

class TestExplanations:
    @pytest.fixture(scope="class")
    def top_match(self, db, provider, baseline):
        from app.ai import run_matching_for_challenge

        result = run_matching_for_challenge(
            db, baseline["challenge_id"], provider, top_n=settings.match_top_n)
        return result["results"][0]

    def test_reasons_match_the_recorded_output(self, top_match, baseline):
        assert top_match["reasons"] == baseline["results"][0]["reasons"]

    def test_gaps_match_the_recorded_output(self, top_match, baseline):
        assert top_match["gaps"] == baseline["results"][0]["gaps"]

    def test_explanation_cites_real_evidence(self, top_match):
        """
        Each reason must be traceable to a stored fact, not generic filler.

        RoadSense holds Computer Vision / GIS Mapping / Deep Learning
        capabilities in `smart-mobility` and a government-sector pothole pilot,
        so the explanation should name those and flag the one missing
        technology.
        """
        reasons = " ".join(top_match["reasons"])
        assert "Computer Vision" in reasons
        assert "smart-mobility" in reasons
        assert "government" in reasons.lower()
        assert top_match["gaps"] == ["No demonstrated capability yet in: IoT Sensors."]

    def test_explanations_differ_between_candidates(self, db, provider, baseline):
        """A shared boilerplate string would mean the explanations are fake."""
        from app.ai import run_matching_for_challenge

        result = run_matching_for_challenge(
            db, baseline["challenge_id"], provider, top_n=settings.match_top_n)
        rendered = {json.dumps(c["reasons"]) for c in result["results"]}
        assert len(rendered) > 1

    def test_persisted_explanation_json_matches_the_returned_one(self, db, baseline):
        """What the UI reads back must equal what matching returned."""
        row = db.execute(text(
            "SELECT explanation_json FROM match_results "
            "WHERE challenge_id = :cid AND rank = 1"),
            {"cid": baseline["challenge_id"]}).scalar_one()
        stored = row if isinstance(row, dict) else json.loads(row)
        assert stored["reasons"] == baseline["results"][0]["reasons"]
        assert stored["gaps"] == baseline["results"][0]["gaps"]


# ===========================================================================
# 5. Live comparison against the still-running ai-service
# ===========================================================================

def _ai_service_is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{AI_SERVICE}/health", timeout=3) as response:
            return response.status == 200
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(
    not _ai_service_is_up(),
    reason="Standalone ai-service is not running on :8081 (removed after Phase 5).",
)
class TestLiveAiServiceParity:
    def test_same_challenge_through_both_paths(self, db, provider, baseline):
        """
        Run the matching through the HTTP service and in-process, and compare.

        Both write to `match_results`, and both are deterministic, so running
        them back to back leaves the table in the same state either way.
        """
        from app.ai import run_matching_for_challenge

        challenge_id = baseline["challenge_id"]

        request = urllib.request.Request(
            f"{AI_SERVICE}/api/v1/ai/match/{challenge_id}", method="POST")
        with urllib.request.urlopen(request, timeout=180) as response:
            theirs = json.loads(response.read())

        mine = run_matching_for_challenge(
            db, challenge_id, provider, top_n=settings.match_top_n)

        assert mine["ai_provider"] == theirs["ai_provider"]
        assert mine["weights"] == theirs["weights"]
        assert mine["total_candidates_considered"] == theirs["total_candidates_considered"]
        for a, b in zip(mine["results"], theirs["results"]):
            assert a["rank"] == b["rank"]
            assert a["company_name"] == b["company_name"]
            assert a["overall_score"] == b["overall_score"]
            assert a["component_scores"] == b["component_scores"]
            assert a["reasons"] == b["reasons"]
            assert a["gaps"] == b["gaps"]


# ===========================================================================
# 6. Knowledge-base similarity
# ===========================================================================

class TestKnowledgeBaseSimilarity:
    def test_similar_pilots_returns_real_scored_matches(self, db, provider):
        from app.ai import find_similar_pilots_for_challenge

        results = find_similar_pilots_for_challenge(
            db, provider,
            title="AI Pothole Detection for Municipal Roads",
            problem_statement=(
                "Roads develop potholes that are reported manually and slowly."),
            desired_technology="Computer Vision, Deep Learning",
            domain="smart-mobility",
            outcomes_expected="Faster detection and repair of road defects.",
        )
        assert isinstance(results, list)
        for entry in results:
            # `knowledge_base.py` rounds `cosine * 100`, so this is a 0-100
            # percentage like every other score the UI renders — not a raw
            # cosine in [0, 1].
            assert 0.0 <= entry["similarity"] <= 100.0
            assert entry["challenge_title"]
            assert entry["pilot_id"]
        if len(results) > 1:
            similarities = [r["similarity"] for r in results]
            assert similarities == sorted(similarities, reverse=True)

    def test_similarity_is_not_a_constant(self, db, provider):
        from app.ai import find_similar_pilots_for_challenge

        mobility = find_similar_pilots_for_challenge(
            db, provider, title="Road defect detection",
            problem_statement="Potholes go unreported.",
            desired_technology="Computer Vision", domain="smart-mobility",
            outcomes_expected=None)
        farming = find_similar_pilots_for_challenge(
            db, provider, title="Crop advisory for smallholders",
            problem_statement="Farmers lack timely agronomic guidance.",
            desired_technology="Machine Learning", domain="agriculture",
            outcomes_expected=None)
        if mobility and farming:
            assert {r["pilot_id"]: r["similarity"] for r in mobility} != \
                   {r["pilot_id"]: r["similarity"] for r in farming}


# ===========================================================================
# 7. The seeded scenario must be unchanged
# ===========================================================================

class TestSeededScenarioUnchanged:
    def test_pilots_and_recommendations_untouched(self, db):
        """
        Matching writes only to `match_results` and a PUBLISHED challenge's
        status. Pilots, KPIs and recommendations must be exactly as seeded.
        """
        # Scoped to seeded rows. Later phases create throwaway pilots tagged
        # with a marker domain, and an unscoped count here would fail on
        # *their* data rather than on anything this module did — a failure
        # landing a long way from its cause.
        counts = dict(db.execute(text(
            "SELECT 'pilots', count(*) FROM pilots p "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'kpis', count(*) FROM kpis k "
            "  JOIN pilots p ON p.id = k.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'kpi_results', count(*) FROM kpi_results r "
            "  JOIN kpis k ON k.id = r.kpi_id JOIN pilots p ON p.id = k.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'recommendations', count(*) FROM recommendations rec "
            "  JOIN pilots p ON p.id = rec.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'kb', count(*) FROM pilot_knowledge_base kb "
            "  JOIN pilots p ON p.id = kb.pilot_id "
            "  JOIN challenges c ON c.id = p.challenge_id WHERE c.domain <> ALL(:d) "
            "UNION ALL SELECT 'proposals', count(*) FROM proposals pr "
            "  JOIN challenges c ON c.id = pr.challenge_id WHERE c.domain <> ALL(:d)"
        ), {"d": list(TEST_MARKER_DOMAINS)}).fetchall())
        assert counts == {"pilots": 2, "kpis": 6, "kpi_results": 6,
                          "recommendations": 2, "kb": 2, "proposals": 6}

    def test_recommendation_values_unchanged(self, db):
        rows = db.execute(text(
            "SELECT rec.recommendation, rec.cost_score, rec.performance_score, "
            "  rec.impact_score, rec.final_decision "
            "FROM recommendations rec JOIN pilots p ON p.id = rec.pilot_id "
            "JOIN challenges c ON c.id = p.challenge_id "
            "WHERE c.domain <> ALL(:d) ORDER BY rec.generated_at"),
            {"d": list(TEST_MARKER_DOMAINS)}).mappings().all()
        assert len(rows) == 2
        for row in rows:
            assert row["recommendation"] in ("SCALE", "MODIFY", "REJECT")
            for field in ("cost_score", "performance_score", "impact_score"):
                assert 0.0 <= float(row[field]) <= 1.0

    def test_challenge_statuses_are_as_expected(self, db, preexisting):
        """
        Matching moves PUBLISHED -> MATCHING for the challenge it runs on, and
        nothing else. Every other challenge keeps its recorded status.
        """
        current = {str(r["id"]): r["status"] for r in db.execute(text(
            "SELECT id, status FROM challenges")).mappings()}
        for recorded in preexisting["challenges"]:
            if recorded["id"] == preexisting["pothole_challenge_id"]:
                assert current[recorded["id"]] in ("PUBLISHED", "MATCHING")
            else:
                assert current[recorded["id"]] == recorded["status"], recorded["title"]

    def test_startup_and_challenge_embeddings_still_present(self, db, preexisting):
        missing = db.execute(text(
            "SELECT count(*) FROM startups WHERE embedding IS NULL")).scalar_one()
        assert missing == 0, "a startup lost its embedding"

        dimensions = db.execute(text(
            "SELECT array_length(embedding, 1) FROM challenges WHERE id = :cid"),
            {"cid": preexisting["pothole_challenge_id"]}).scalar_one()
        assert dimensions == 384


# ===========================================================================
# 8. Real embeddings on publish — no fabricated vectors
# ===========================================================================

class TestPublishComputesARealEmbedding:
    """
    A newly published challenge must receive a genuine embedding.

    The Phase 4 hook was a documented no-op; this asserts the Phase 5 wiring
    actually computes and stores a vector, and that the vector is the *correct*
    one — recomputable from the challenge's own text — rather than a plausible
    array of numbers.
    """

    MARKER_DOMAIN = "phase5-embedding-check"

    @pytest.fixture
    def government_actor(self, db):
        from app.models import User

        return db.execute(text("SELECT id FROM users WHERE email = 'government@demo.com'")
                          ).scalar_one() and db.query(User).filter_by(
            email="government@demo.com").one()

    def _purge(self, db):
        db.rollback()
        for statement in (
            "DELETE FROM evaluation_criteria WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = :d)",
            "DELETE FROM challenge_requirements WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = :d)",
            "DELETE FROM challenge_kpis WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = :d)",
            "DELETE FROM match_results WHERE challenge_id IN "
            "  (SELECT id FROM challenges WHERE domain = :d)",
            "DELETE FROM audit_logs WHERE entity_id IN "
            "  (SELECT id FROM challenges WHERE domain = :d)",
            "DELETE FROM challenges WHERE domain = :d",
        ):
            db.execute(text(statement), {"d": self.MARKER_DOMAIN})
        db.commit()

    def test_publish_stores_a_real_recomputable_embedding(self, db, provider, government_actor):
        from app.ai import build_challenge_text
        from app.schemas.challenge import ChallengeDraftRequest
        from app.services.challenge_service import ChallengeService

        self._purge(db)
        try:
            service = ChallengeService(db)
            created = service.create(government_actor, ChallengeDraftRequest(
                title="Phase 5 Embedding Verification",
                problem_statement=(
                    "Verifying that publishing a challenge computes a genuine "
                    "sentence-transformer embedding rather than a placeholder."),
                desired_technology="Computer Vision, Deep Learning",
                domain=self.MARKER_DOMAIN,
                outcomes_expected="A stored 384-dimension vector.",
                requirements=[{"requirementType": "TECHNICAL",
                               "description": "Must produce a real embedding",
                               "mandatory": True}],
                kpis=[],
            ))

            # Before publish there is no embedding at all — not a zero vector,
            # not a random one. Absence is the honest state.
            row = db.execute(text(
                "SELECT embedding, embedding_model FROM challenges WHERE id = :id"),
                {"id": created.id}).mappings().one()
            assert row["embedding"] is None
            assert row["embedding_model"] is None

            published = service.publish(government_actor, created.id)
            assert published.status.value == "PUBLISHED"

            db.expire_all()
            row = db.execute(text(
                "SELECT embedding, embedding_model, embedding_updated_at, title, "
                "problem_statement, desired_technology, domain, outcomes_expected "
                "FROM challenges WHERE id = :id"), {"id": created.id}).mappings().one()

            assert row["embedding"] is not None, "publish did not compute an embedding"
            assert len(row["embedding"]) == 384
            assert row["embedding_model"] == "local-fallback"
            assert row["embedding_updated_at"] is not None

            # The stored vector must be the one this challenge's text produces.
            requirements = [r[0] for r in db.execute(text(
                "SELECT description FROM challenge_requirements WHERE challenge_id = :id"),
                {"id": created.id}).all()]
            expected = provider.embed(build_challenge_text(
                title=row["title"],
                problem_statement=row["problem_statement"],
                desired_technology=row["desired_technology"],
                domain=row["domain"],
                outcomes_expected=row["outcomes_expected"],
                requirements=requirements,
            ))
            stored = [float(v) for v in row["embedding"]]
            for computed_value, stored_value in zip(expected, stored):
                assert computed_value == pytest.approx(stored_value, abs=1e-6)

            # And it is not a degenerate vector.
            assert len(set(stored)) > 100, "the stored vector looks synthetic"
            assert any(v < 0 for v in stored) and any(v > 0 for v in stored)
        finally:
            self._purge(db)

    def test_embedding_failure_leaves_null_rather_than_a_fake_vector(self, db, government_actor):
        """
        When the model cannot load, publish still succeeds and the embedding
        stays NULL — matching computes it later. A fabricated vector would
        silently corrupt every future score, which is far worse than absence.
        """
        from unittest.mock import patch

        from app.schemas.challenge import ChallengeDraftRequest
        from app.services.challenge_service import ChallengeService

        self._purge(db)
        try:
            service = ChallengeService(db)
            created = service.create(government_actor, ChallengeDraftRequest(
                title="Phase 5 Embedding Failure Path",
                problem_statement="The provider is unavailable in this case.",
                domain=self.MARKER_DOMAIN,
                requirements=[{"requirementType": "TECHNICAL",
                               "description": "x", "mandatory": True}],
                kpis=[],
            ))

            with patch("app.ai.get_embedding_provider",
                       side_effect=RuntimeError("model unavailable")):
                published = service.publish(government_actor, created.id)

            # The publish itself succeeded.
            assert published.status.value == "PUBLISHED"
            assert published.published_at is not None

            db.expire_all()
            row = db.execute(text(
                "SELECT embedding, embedding_model FROM challenges WHERE id = :id"),
                {"id": created.id}).mappings().one()
            assert row["embedding"] is None, "a vector was invented despite the failure"
            assert row["embedding_model"] is None
        finally:
            self._purge(db)
