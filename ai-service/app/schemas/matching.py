from pydantic import BaseModel


class ComponentScores(BaseModel):
    semantic_similarity: float
    technology_match: float
    domain_match: float
    experience_score: float
    readiness_score: float


class MatchCandidate(BaseModel):
    startup_id: str
    company_name: str
    rank: int
    overall_score: float
    component_scores: ComponentScores
    reasons: list[str]
    gaps: list[str]


class MatchResponse(BaseModel):
    challenge_id: str
    ai_provider: str
    weights: dict[str, float]
    total_candidates_considered: int
    results: list[MatchCandidate]


class EmbeddingComputeResponse(BaseModel):
    id: str
    embedding_dimensions: int
    ai_provider: str


class ProposalAnalysisResponse(BaseModel):
    proposal_id: str
    ai_provider: str
    summary: str


class KnowledgeBaseMatch(BaseModel):
    pilot_id: str
    challenge_title: str
    domain: str
    technology_tags: list[str]
    outcome_summary: str | None
    success: bool | None
    similarity: float


class KnowledgeBaseSimilarResponse(BaseModel):
    ai_provider: str
    results: list[KnowledgeBaseMatch]
