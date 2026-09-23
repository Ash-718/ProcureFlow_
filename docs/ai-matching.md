# AI Matching Methodology

This is the centerpiece of ProcureFlow: turning a published challenge into a
ranked, explained list of candidate startups. This document describes exactly
how it works — the pipeline, the formula, the fallback strategy, and the
engineering decisions made where the reference spec left something open.

## 1. Pipeline overview

```
Challenge published                Startup profile saved
      │                                    │
      ▼                                    ▼
Build structured text            Build structured text
representation                   representation
      │                                    │
      ▼                                    ▼
EmbeddingProvider.embed()        EmbeddingProvider.embed()
      │                                    │
      ▼                                    ▼
Store in challenges.embedding    Store in startups.embedding
      (double precision[])              (double precision[])

Government clicks "Find Suitable Startups"
      │
      ▼
Router calls app.ai.run_matching_for_challenge() in-process
      │
      ▼
For every startup:
  1. cosine_similarity(challenge.embedding, startup.embedding)   [35%]
  2. technology_match(challenge.desired_technology, capabilities) [20%]
  3. domain_match(challenge.domain, capabilities/projects)        [15%]
  4. experience_score(challenge.domain, past projects)            [15%]
  5. readiness_score(startup.readiness_score)                     [15%]
      │
      ▼
overall_score = weighted sum → persisted to match_results, ranked, returned
      with a template-generated explanation (reasons + gaps)
```

Both "on save" triggers (challenge publish, startup profile/capability/project
save) fire an eager embedding recomputation — but if that call fails or a row
somehow has no embedding yet, the matching run computes it on the spot before
scoring, so a stale/missing embedding never blocks a match. This is the
"AI fallback" made concrete, not just for provider failures but for timing too.

## 2. Text representations

**Challenge** (`backend/app/ai/text_builders.py::build_challenge_text`):

```
Challenge: <title>
Domain: <domain>
Problem statement: <problem_statement>
Desired technology: <desired_technology>
Expected outcomes: <outcomes_expected>
Requirements: <requirement 1>; <requirement 2>; ...
```

**Startup** (`build_startup_text`):

```
Startup: <company_name>
Description: <description>
Capabilities: <tech> (<domain>, proficiency <n>/5); ...
Past projects: <title> — <domain> sector, tech: <stack>, client: <type>, outcome: <summary>; ...
Pilot readiness score: <n>/100
```

These are deliberately plain and inspectable — a judge can read exactly what
goes into the embedding model, with no hidden preprocessing.

## 3. The weighted formula

```
overall_score =
    0.35 * semantic_similarity
  + 0.20 * technology_match
  + 0.15 * domain_match
  + 0.15 * experience_score
  + 0.15 * readiness_score
```

All components and the overall score are reported on a 0-100 scale. Weights
live in `backend/app/core/config.py` (env-overridable:
`WEIGHT_SEMANTIC_SIMILARITY`, etc.) and are also recorded in
`database/schema.sql`'s `ai_matching_config` table for transparency/audit —
the API's `/api/v1/ai/match/{id}` response and `/health` endpoint both report
the active weights, so nothing about the score is hidden from the caller.

### 3.1 Semantic similarity (35%)

Cosine similarity between the challenge and startup embedding vectors,
clamped to `[0, 1]` (a negative cosine similarity contributes 0, not a
penalty below zero — see `RecommendationCalculator`-style clamping in
`backend/app/ai/scoring.py::compute_overall_score`).

### 3.2 Technology match (20%)

`backend/app/ai/scoring.py::compute_technology_match`. The
challenge's `desired_technology` field is a comma-separated string; each term
is matched (case-insensitive, substring-tolerant in either direction) against
the startup's capability `technology_tag`s. A matched term contributes its
best-matching capability's `proficiency_level / 5`; an unmatched term
contributes 0. The score is the average across all desired terms — so a
startup covering every desired technology at top proficiency scores 1.0, and
one covering none scores 0.0. A challenge with no desired technology listed
scores every startup 0.5 (neutral) here rather than 0, since the omission is
the challenge author's choice, not evidence against any startup.

### 3.3 Domain match (15%)

`compute_domain_match`. Full credit (scaled by proficiency) if a capability is
explicitly tagged with the challenge's domain; partial credit (0.4) if only a
past *project* was delivered in that domain with no matching capability tag;
zero otherwise.

### 3.4 Experience score (15%)

`compute_experience_score`. Rewards relevant delivery history:

- Up to 0.6 for same-domain project count, capped at 3 projects (so a 10th
  similar project doesn't keep inflating the score).
- +0.3 if any same-domain project had a **government** client — the spec
  explicitly calls out government-sector experience as a differentiator, and
  the seed data's ranking depends on this (e.g. RoadSense AI's Pune
  Municipal Corporation pothole pilot is what pulls it ahead of otherwise
  similar competitors).
- +0.1 (small) general-delivery credit for off-domain projects, capped at 2,
  so a startup with zero relevant history isn't scored identically to one
  with no history at all.

### 3.5 Readiness score (15%)

`startups.readiness_score` (0-100, self-reported by the startup, see
Section 6 of this doc), normalized to `[0, 1]`.

## 4. Explanations

`backend/app/ai/explanations.py::build_match_explanation` turns the
component scores into 2-4 "reasons" and 0-2 "gaps" — purely template-driven
from the actual numbers (which technologies matched/didn't, whether the
domain match came from a capability or a project, whether there's government
experience, how high readiness is). This is deterministic and reproducible:
the same inputs always produce the same explanation, which matters for a
government procurement context where "why did this score what it did" needs
a real, auditable answer — not a shifting LLM paraphrase.

## 5. AI fallback strategy (Section 6 of the build spec)

Two abstractions, each with a local (offline) and an LLM-backed implementation:

| | Local (default) | LLM |
|---|---|---|
| `EmbeddingProvider` | `sentence-transformers` `all-MiniLM-L6-v2`, runs on CPU, no API key, no network call | OpenAI-compatible `/embeddings` endpoint |
| `TextGenerationProvider` | Returns the template text unchanged | Polishes the template draft into flowing prose via an OpenAI-compatible `/chat/completions` call |

Selection is via `EMBEDDING_PROVIDER=local|llm` (`backend/.env`). If set to
`llm` but `LLM_API_KEY` is missing, the service logs a warning and **silently
falls back to local** — a missing key never crashes a request. Every match
response includes `"ai_provider"` so the frontend/judge can see which path
actually ran (seed data and this whole build were developed and demoed
against `local-fallback`, since no LLM key is provisioned in this environment).

Match explanations are deliberately **not** run through the LLM polish step —
they're structured (reasons/gaps arrays) for the UI's bullet-list rendering,
and deterministic template text serves that better than paraphrased prose.
The LLM polish path is exercised on the **proposal AI-assist summary**
instead (`backend/app/ai/proposal_analysis.py`), where flowing prose
is actually what an expert evaluator wants to read.

## 6. Deliberate deviations from the reference spec (and why)

- **pgvector → `double precision[]` + numpy.** This dev/demo environment has
  no Docker and no MSVC build toolchain to compile the pgvector extension
  from source, and there's no pre-built Windows binary for it. Embeddings are
  stored as native Postgres `double precision[]` arrays; cosine similarity is
  computed in the AI service with numpy — exact, real, reproducible
  computation, just without an ANN index. At this project's scale (tens of
  startups/challenges) brute-force similarity is effectively instant; the
  only thing sacrificed is the index, which only matters at a much larger
  scale. Swapping the column to `vector(384)` + an `ivfflat` index is a
  drop-in change if pgvector becomes available — nothing else about the
  pipeline would need to change.
- **Readiness score is self-reported**, via a slider in the startup's profile
  page, rather than computed from some other signal — the schema defines the
  column but not how it's populated, and self-assessment is the most
  defensible default for a prototype (a judge can see exactly why a number is
  what it is).
- **Technology-direction heuristic for the *recommendation* engine** (not
  matching) is documented separately in `docs/architecture.md` and in
  `RecommendationCalculator`'s Javadoc, since it's a related but distinct
  piece of "AI-assisted" scoring.
