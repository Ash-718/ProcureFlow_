import { useEffect, useRef, useState } from "react"
import { Bell } from "lucide-react"
import { NotificationApi } from "@/api/endpoints"
import type { NotificationItem } from "@/types"
import { formatDateTime } from "@/lib/utils"
import { cn } from "@/lib/utils"

export function NotificationBell() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationItem[]>([])
  const [unread, setUnread] = useState(0)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cancelled = false
    const poll = () => {
      NotificationApi.unreadCount()
        .then((r) => !cancelled && setUnread(r.unread))
        .catch(() => {})
    }
    poll()
    const interval = setInterval(poll, 20000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener("mousedown", onClickOutside)
    return () => document.removeEventListener("mousedown", onClickOutside)
  }, [])

  function toggle() {
    setOpen((v) => !v)
    if (!open) {
      NotificationApi.list().then(setItems).catch(() => {})
    }
  }

  async function markRead(id: string) {
    await NotificationApi.markRead(id).catch(() => {})
    setItems((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
    setUnread((c) => Math.max(0, c - 1))
  }

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={toggle}
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger-500 px-1 text-[10px] font-semibold text-white">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-lg">
          <div className="border-b border-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
            Notifications
          </div>
          <div className="max-h-80 overflow-y-auto">
            {items.length === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-400">No notifications yet.</p>
            )}
            {items.map((n) => (
              <button
                key={n.id}
                onClick={() => markRead(n.id)}
                className={cn(
                  "block w-full border-b border-slate-50 px-4 py-3 text-left text-sm last:border-0 hover:bg-slate-50",
                  !n.read && "bg-brand-50/50"
                )}
              >
                <p className={cn("text-slate-700", !n.read && "font-medium text-slate-900")}>{n.message}</p>
                <p className="mt-0.5 text-xs text-slate-400">{formatDateTime(n.createdAt)}</p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
