"""
Meaningful tests of the matching formula's math (Section 20): given fixed inputs,
assert the exact expected component scores — not just "it runs without error".
"""
from app.services.scoring import (
    compute_domain_match,
    compute_experience_score,
    compute_overall_score,
    compute_technology_match,
    normalize_readiness,
    split_technology_list,
)

WEIGHTS = {
    "semantic_similarity": 0.35,
    "technology_match": 0.20,
    "domain_match": 0.15,
    "experience_score": 0.15,
    "readiness_score": 0.15,
}


def test_split_technology_list_handles_whitespace_and_empty():
    assert split_technology_list("Computer Vision, IoT Sensors,  GIS Mapping ") == [
        "Computer Vision",
        "IoT Sensors",
        "GIS Mapping",
    ]
    assert split_technology_list(None) == []
    assert split_technology_list("") == []


def test_technology_match_full_coverage_top_proficiency():
    desired = ["Computer Vision", "Deep Learning"]
    capabilities = [
        {"technology_tag": "Computer Vision", "domain_tag": "x", "proficiency_level": 5},
        {"technology_tag": "Deep Learning", "domain_tag": "x", "proficiency_level": 5},
    ]
    result = compute_technology_match(desired, capabilities)
    assert result.score == 1.0
    assert result.matched == desired
    assert result.unmatched == []


def test_technology_match_partial_coverage_and_proficiency_scaling():
    desired = ["Computer Vision", "IoT Sensors"]
    capabilities = [
        {"technology_tag": "Computer Vision", "domain_tag": "x", "proficiency_level": 3},
    ]
    result = compute_technology_match(desired, capabilities)
    # Computer Vision matched at proficiency 3/5 = 0.6; IoT Sensors unmatched = 0.
    # Average across 2 desired techs = 0.3
    assert round(result.score, 4) == 0.3
    assert result.matched == ["Computer Vision"]
    assert result.unmatched == ["IoT Sensors"]


def test_technology_match_no_desired_technologies_is_neutral():
    result = compute_technology_match([], [{"technology_tag": "X", "domain_tag": "y", "proficiency_level": 5}])
    assert result.score == 0.5


def test_technology_match_is_case_insensitive_and_substring_tolerant():
    result = compute_technology_match(
        ["computer vision"], [{"technology_tag": "Computer Vision Systems", "domain_tag": "x", "proficiency_level": 4}]
    )
    assert result.matched == ["computer vision"]
    assert round(result.score, 4) == 0.8


def test_domain_match_full_credit_from_capability():
    result = compute_domain_match(
        "smart-mobility",
        [{"technology_tag": "CV", "domain_tag": "smart-mobility", "proficiency_level": 4}],
        [],
    )
    assert result.matched_via == "capability"
    assert result.score == 0.8


def test_domain_match_partial_credit_from_project_only():
    result = compute_domain_match(
        "smart-mobility",
        [{"technology_tag": "CV", "domain_tag": "agri-tech", "proficiency_level": 5}],
        [{"domain": "smart-mobility", "title": "x", "client_type": "PRIVATE"}],
    )
    assert result.matched_via == "project"
    assert result.score == 0.4


def test_domain_match_zero_when_no_overlap_anywhere():
    result = compute_domain_match("cybersecurity", [], [{"domain": "agri-tech", "title": "x", "client_type": "PRIVATE"}])
    assert result.matched_via is None
    assert result.score == 0.0


def test_experience_score_caps_at_three_relevant_projects_plus_government_bonus():
    domain = "health-tech"
    projects = [
        {"domain": domain, "title": "p1", "client_type": "GOVERNMENT"},
        {"domain": domain, "title": "p2", "client_type": "PRIVATE"},
        {"domain": domain, "title": "p3", "client_type": "PRIVATE"},
        {"domain": domain, "title": "p4", "client_type": "PRIVATE"},  # beyond the cap of 3
    ]
    result = compute_experience_score(domain, projects)
    # raw = min(4,3)/3 * 0.6 = 0.6 ; govt_bonus = 0.3 (has relevant govt project) ; general_bonus = 0 (no "other" projects)
    assert round(result.score, 4) == 0.9
    assert result.has_relevant_government_experience is True


def test_experience_score_zero_relevant_projects_only_general_bonus():
    result = compute_experience_score(
        "health-tech",
        [
            {"domain": "agri-tech", "title": "p1", "client_type": "PRIVATE"},
            {"domain": "agri-tech", "title": "p2", "client_type": "PRIVATE"},
        ],
    )
    # raw = 0 ; govt_bonus = 0 ; general_bonus = min(2,2)/2 * 0.1 = 0.1
    assert round(result.score, 4) == 0.1
    assert result.has_relevant_government_experience is False


def test_experience_score_government_client_in_other_domain_gives_smaller_bonus():
    result = compute_experience_score(
        "health-tech",
        [{"domain": "agri-tech", "title": "p1", "client_type": "GOVERNMENT"}],
    )
    # raw = 0 ; govt_bonus = 0.1 (govt experience, but not in this domain) ; general_bonus = min(1,2)/2*0.1 = 0.05
    assert round(result.score, 4) == 0.15


def test_normalize_readiness_clamps_to_0_1_range():
    assert normalize_readiness(85) == 0.85
    assert normalize_readiness(150) == 1.0
    assert normalize_readiness(-10) == 0.0


def test_overall_score_matches_documented_weighted_formula():
    result = compute_overall_score(
        semantic_similarity_0_1=0.8,
        technology_match_0_1=0.7,
        domain_match_0_1=1.0,
        experience_0_1=0.6,
        readiness_0_1=0.85,
        weights=WEIGHTS,
    )
    expected = (0.35 * 0.8 + 0.20 * 0.7 + 0.15 * 1.0 + 0.15 * 0.6 + 0.15 * 0.85) * 100
    assert round(result.overall, 3) == round(expected, 3)
    assert result.semantic_similarity == 80.0
    assert result.technology_match == 70.0
    assert result.domain_match == 100.0
    assert result.experience == 60.0
    assert result.readiness == 85.0


def test_overall_score_clamps_negative_semantic_similarity_to_zero():
    # cosine similarity can be negative for unrelated/opposed embeddings; the formula
    # must not let that pull the overall score below what the other components earn.
    result = compute_overall_score(
        semantic_similarity_0_1=-0.4,
        technology_match_0_1=0.0,
        domain_match_0_1=0.0,
        experience_0_1=0.0,
        readiness_0_1=0.0,
        weights=WEIGHTS,
    )
    assert result.overall == 0.0
    assert result.semantic_similarity == 0.0


def test_overall_score_perfect_candidate_scores_100():
    result = compute_overall_score(1.0, 1.0, 1.0, 1.0, 1.0, WEIGHTS)
    assert result.overall == 100.0
