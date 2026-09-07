import type { LucideIcon } from "lucide-react"
import {
  LayoutDashboard, FilePlus2, Rocket, BookOpenCheck, ClipboardList,
  Inbox, Users, ScrollText, Search,
} from "lucide-react"
import type { Role } from "@/types"

export interface NavItem {
  label: string
  to: string
  icon: LucideIcon
  end?: boolean
}

export const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  GOVERNMENT: [
    { label: "Challenges", to: "/gov", icon: LayoutDashboard, end: true },
    { label: "New Challenge", to: "/gov/challenges/new", icon: FilePlus2 },
    { label: "Pilots", to: "/gov/pilots", icon: Rocket },
    { label: "Knowledge Base", to: "/knowledge-base", icon: BookOpenCheck },
  ],
  STARTUP: [
    { label: "My Profile", to: "/startup", icon: LayoutDashboard, end: true },
    { label: "Browse Challenges", to: "/startup/challenges", icon: Search },
    { label: "My Proposals", to: "/startup/proposals", icon: ClipboardList },
  ],
  EXPERT: [
    { label: "Evaluation Queue", to: "/expert", icon: Inbox, end: true },
    { label: "Knowledge Base", to: "/knowledge-base", icon: BookOpenCheck },
  ],
  ADMIN: [
    { label: "Users", to: "/admin", icon: Users, end: true },
    { label: "Audit Logs", to: "/admin/audit-logs", icon: ScrollText },
    { label: "Knowledge Base", to: "/knowledge-base", icon: BookOpenCheck },
  ],
}

export const ROLE_LABEL: Record<Role, string> = {
  GOVERNMENT: "Government",
  STARTUP: "Startup",
  EXPERT: "Expert",
  ADMIN: "Admin",
}

export const ROLE_HOME: Record<Role, string> = {
  GOVERNMENT: "/gov",
  STARTUP: "/startup",
  EXPERT: "/expert",
  ADMIN: "/admin",
}
