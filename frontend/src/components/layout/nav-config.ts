import type { LucideIcon } from "lucide-react"
import {
  BookOpenCheck,
  ClipboardList,
  FilePlus2,
  FileText,
  Inbox,
  LayoutDashboard,
  Rocket,
  ScrollText,
  Search,
  Sparkles,
  Users,
} from "lucide-react"
import type { Role } from "@/types"

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
  /** Short hint shown in the collapsed sidebar's tooltip. */
  description?: string
}

export interface NavGroup {
  /** Group heading. `null` renders the items without one. */
  label: string | null
  items: NavItem[]
}

/**
 * Role-aware navigation.
 *
 * Grouped so each workspace reads as a workflow rather than a flat list: the
 * things you *do* first, then the records they produce, then the shared
 * reference material. Every role's first entry is now a dashboard — before
 * this, all four landed on a list page with no sense of what needed attention.
 */
export const NAV_BY_ROLE: Record<Role, NavGroup[]> = {
  GOVERNMENT: [
    {
      label: null,
      items: [
        {
          label: "Dashboard",
          to: "/gov",
          icon: LayoutDashboard,
          end: true,
          description: "What needs your attention",
        },
      ],
    },
    {
      label: "Procurement",
      items: [
        {
          label: "Challenges",
          to: "/gov/challenges",
          icon: FileText,
          description: "Structured procurement challenges",
        },
        {
          label: "New Challenge",
          to: "/gov/challenges/new",
          icon: FilePlus2,
          description: "Convert a problem into a challenge",
        },
        {
          label: "Pilots",
          to: "/gov/pilots",
          icon: Rocket,
          description: "Controlled pilots and their KPIs",
        },
      ],
    },
    {
      label: "Reference",
      items: [
        {
          label: "Knowledge Base",
          to: "/knowledge-base",
          icon: BookOpenCheck,
          description: "Outcomes of past pilots",
        },
      ],
    },
  ],

  STARTUP: [
    {
      label: null,
      items: [
        {
          label: "Dashboard",
          to: "/startup",
          icon: LayoutDashboard,
          end: true,
          description: "Your opportunities at a glance",
        },
      ],
    },
    {
      label: "Opportunities",
      items: [
        {
          label: "Browse Challenges",
          to: "/startup/challenges",
          icon: Search,
          description: "Open government challenges",
        },
        {
          label: "My Proposals",
          to: "/startup/proposals",
          icon: ClipboardList,
          description: "What you have submitted",
        },
      ],
    },
    {
      label: "Company",
      items: [
        {
          label: "Company Profile",
          to: "/startup/profile",
          icon: Users,
          description: "Capabilities the AI matches on",
        },
        {
          label: "Knowledge Base",
          to: "/knowledge-base",
          icon: BookOpenCheck,
          description: "Outcomes of past pilots",
        },
      ],
    },
  ],

  EXPERT: [
    {
      label: null,
      items: [
        {
          label: "Dashboard",
          to: "/expert",
          icon: LayoutDashboard,
          end: true,
          description: "Your evaluation workload",
        },
      ],
    },
    {
      label: "Evaluation",
      items: [
        {
          label: "Evaluation Queue",
          to: "/expert/queue",
          icon: Inbox,
          description: "Proposals awaiting your review",
        },
      ],
    },
    {
      label: "Reference",
      items: [
        {
          label: "Knowledge Base",
          to: "/knowledge-base",
          icon: BookOpenCheck,
          description: "Outcomes of past pilots",
        },
      ],
    },
  ],

  ADMIN: [
    {
      label: null,
      items: [
        {
          label: "Dashboard",
          to: "/admin",
          icon: LayoutDashboard,
          end: true,
          description: "Platform activity",
        },
      ],
    },
    {
      label: "Operations",
      items: [
        {
          label: "Users",
          to: "/admin/users",
          icon: Users,
          description: "Accounts and access",
        },
        {
          label: "Audit Logs",
          to: "/admin/audit-logs",
          icon: ScrollText,
          description: "Every state-changing action",
        },
      ],
    },
    {
      label: "Reference",
      items: [
        {
          label: "Knowledge Base",
          to: "/knowledge-base",
          icon: BookOpenCheck,
          description: "Outcomes of past pilots",
        },
      ],
    },
  ],
}

export const ROLE_LABEL: Record<Role, string> = {
  GOVERNMENT: "Government",
  STARTUP: "Startup",
  EXPERT: "Domain Expert",
  ADMIN: "Administrator",
}

/** One line describing what this role does, shown under the role chip. */
export const ROLE_TAGLINE: Record<Role, string> = {
  GOVERNMENT: "Publish challenges, run pilots, decide outcomes",
  STARTUP: "Discover challenges and submit proposals",
  EXPERT: "Evaluate proposals against the rubric",
  ADMIN: "Operate the platform",
}

export const ROLE_HOME: Record<Role, string> = {
  GOVERNMENT: "/gov",
  STARTUP: "/startup",
  EXPERT: "/expert",
  ADMIN: "/admin",
}

/** Flat list, for resolving the current page's title from a pathname. */
export function flattenNav(role: Role): NavItem[] {
  return NAV_BY_ROLE[role].flatMap((group) => group.items)
}

export const AI_MATCHING_ICON = Sparkles
