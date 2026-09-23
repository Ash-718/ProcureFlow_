/**
 * The procurement lifecycle.
 *
 * Kept separate from the component that draws it so the stage constants and
 * the status mapping can be imported without pulling in a React component.
 */

export const LIFECYCLE_STAGES = [
  { key: "PROBLEM", label: "Problem" },
  { key: "CHALLENGE", label: "Challenge" },
  { key: "MATCHING", label: "AI Matching" },
  { key: "PROPOSALS", label: "Proposals" },
  { key: "EVALUATION", label: "Evaluation" },
  { key: "SHORTLIST", label: "Shortlist" },
  { key: "PILOT", label: "Pilot" },
  { key: "KPI", label: "KPI Tracking" },
  { key: "DECISION", label: "Decision" },
  { key: "KNOWLEDGE", label: "Knowledge" },
] as const

export type LifecycleStage = (typeof LIFECYCLE_STAGES)[number]["key"]

/**
 * The furthest stage a challenge has reached, from its status.
 *
 * Mirrors the backend's `challenge_status` enum, so the rail reflects real
 * record state rather than a hardcoded step.
 */
export function stageForChallengeStatus(status: string): LifecycleStage {
  switch (status) {
    case "DRAFT":
      return "CHALLENGE"
    case "PUBLISHED":
      return "PROPOSALS"
    case "MATCHING":
      return "MATCHING"
    case "SHORTLISTED":
      return "SHORTLIST"
    case "PILOT":
      return "PILOT"
    case "CLOSED":
      return "DECISION"
    default:
      return "PROBLEM"
  }
}
