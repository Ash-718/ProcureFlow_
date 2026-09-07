import { Badge, type BadgeProps } from "@/components/ui/badge"

type Variant = NonNullable<BadgeProps["variant"]>

const STATUS_MAP: Record<string, Variant> = {
  DRAFT: "neutral",
  PUBLISHED: "brand",
  MATCHING: "brand",
  SHORTLISTED: "success",
  PILOT: "brand",
  CLOSED: "neutral",

  SUBMITTED: "brand",
  UNDER_REVIEW: "warning",
  REJECTED: "danger",

  ACTIVE: "brand",
  COMPLETED: "success",
  TERMINATED: "danger",

  PENDING: "neutral",
  IN_PROGRESS: "brand",
  DONE: "success",
  DELAYED: "warning",

  VERIFIED: "success",
  FLAGGED: "danger",

  SCALE: "success",
  MODIFY: "warning",
  REJECT: "danger",

  true: "success",
  false: "danger",
}

const LABEL_OVERRIDE: Record<string, string> = {
  true: "Success",
  false: "Not Scaled",
}

export function StatusBadge({ status }: { status: string }) {
  const variant = STATUS_MAP[status] ?? "neutral"
  const label = LABEL_OVERRIDE[status] ?? status.replaceAll("_", " ")
  return <Badge variant={variant}>{label}</Badge>
}
