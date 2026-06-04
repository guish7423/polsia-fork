"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import { Bell, BellRing, AlertTriangle, CreditCard, Settings, Bot, CheckCheck } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import {
  fetchUnreadCount,
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  type NotificationItem,
  type NotificationType,
} from "@/lib/api";

const TYPE_ICONS: Record<NotificationType, typeof Bell> = {
  alert: AlertTriangle,
  billing: CreditCard,
  system: Settings,
  agent: Bot,
};

function relativeTime(createdAt: string, t: (k: string) => string): string {
  const diff = Date.now() - new Date(createdAt).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return t("notification.just_now");
  if (mins < 60) return t("notification.minutes_ago").replace("{n}", String(mins));
  const hours = Math.floor(mins / 60);
  if (hours < 24) return t("notification.hours_ago").replace("{n}", String(hours));
  const days = Math.floor(hours / 24);
  return t("notification.days_ago").replace("{n}", String(days));
}

export function NotificationBell() {
  const { t } = useI18n();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const bellRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const loadUnreadCount = useCallback(async () => {
    try {
      const res = await fetchUnreadCount();
      setUnreadCount(res.count);
    } catch {
      // fail-open
    }
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const res = await fetchNotifications(10, 0);
      setNotifications(res.items);
    } catch {
      // fail-open
    }
  }, []);

  // Poll unread count every 30s
  useEffect(() => {
    loadUnreadCount();
    const id = setInterval(loadUnreadCount, 30_000);
    return () => clearInterval(id);
  }, [loadUnreadCount]);

  // Load full list when panel opens
  useEffect(() => {
    if (open) {
      loadNotifications();
      loadUnreadCount();
    }
  }, [open, loadNotifications, loadUnreadCount]);

  // Click outside to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (
        bellRef.current?.contains(e.target as Node) ||
        panelRef.current?.contains(e.target as Node)
      ) {
        return;
      }
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleMarkAllRead = async () => {
    try {
      await markAllNotificationsRead();
      setUnreadCount(0);
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true, read_at: new Date().toISOString() })));
    } catch {
      // fail-open
    }
  };

  const handleClickItem = async (n: NotificationItem) => {
    if (!n.read) {
      try {
        await markNotificationRead(n.id);
        setUnreadCount((c) => Math.max(0, c - 1));
        setNotifications((prev) =>
          prev.map((x) => (x.id === n.id ? { ...x, read: true, read_at: new Date().toISOString() } : x)),
        );
      } catch {
        // fail-open — still navigate
      }
    }
    setOpen(false);
    if (n.link) {
      router.push(n.link);
    }
  };

  const Icon = unreadCount > 0 ? BellRing : Bell;

  return (
    <>
      <button
        ref={bellRef}
        onClick={() => setOpen((o) => !o)}
        className="relative p-1.5 rounded-md text-gray-300 hover:text-white hover:bg-gray-700 transition-colors"
        aria-label={t("notification.title")}
      >
        <Icon size={18} />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex items-center justify-center min-w-[16px] h-4 px-1 text-[10px] font-bold text-white bg-red-500 rounded-full">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {open &&
        createPortal(
          <div
            ref={panelRef}
            className="fixed z-50 w-80 max-h-[420px] bg-gray-800 border border-gray-700 rounded-lg shadow-xl flex flex-col overflow-hidden"
            style={{
              top: (bellRef.current?.getBoundingClientRect().bottom ?? 0) + 4,
              right: document.body.offsetWidth - (bellRef.current?.getBoundingClientRect().right ?? 0) + 200,
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700">
              <h3 className="text-sm font-semibold text-white">{t("notification.title")}</h3>
              {notifications.some((n) => !n.read) && (
                <button
                  onClick={handleMarkAllRead}
                  className="flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
                >
                  <CheckCheck size={14} />
                  {t("notification.mark_all_read")}
                </button>
              )}
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="flex items-center justify-center py-10 text-sm text-gray-400">
                  {t("notification.empty")}
                </div>
              ) : (
                notifications.map((n) => {
                  const TypeIcon = TYPE_ICONS[n.notification_type] ?? Bell;
                  return (
                    <button
                      key={n.id}
                      onClick={() => handleClickItem(n)}
                      className={`w-full text-left px-4 py-3 flex gap-3 hover:bg-gray-700/50 transition-colors border-b border-gray-700/50 last:border-b-0 ${
                        !n.read ? "bg-indigo-900/20" : ""
                      }`}
                    >
                      <div className={`mt-0.5 ${!n.read ? "text-indigo-400" : "text-gray-500"}`}>
                        <TypeIcon size={16} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className={`text-sm truncate ${!n.read ? "text-white font-medium" : "text-gray-300"}`}>
                          {n.title}
                        </p>
                        {n.body && (
                          <p className="text-xs text-gray-400 truncate mt-0.5">{n.body}</p>
                        )}
                        <p className="text-[10px] text-gray-500 mt-1">
                          {relativeTime(n.created_at, t)}
                        </p>
                      </div>
                      {!n.read && (
                        <div className="w-2 h-2 rounded-full bg-indigo-400 mt-1.5 shrink-0" />
                      )}
                    </button>
                  );
                })
              )}
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
