"use client";
import {
  useState,
  useEffect,
  useRef,
  useCallback,
  type KeyboardEvent,
} from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { useI18n } from "@/lib/i18n";
import {
  searchApi,
  type SearchResultItem,
  type SearchResultGroup,
} from "@/lib/api";

function flattenResults(groups: SearchResultGroup[]): SearchResultItem[] {
  return groups.flatMap((g) => g.items);
}

function groupResults(items: SearchResultItem[]): SearchResultGroup[] {
  const groupMap = new Map<string, SearchResultItem[]>();
  for (const item of items) {
    const arr = groupMap.get(item.type) ?? [];
    arr.push(item);
    groupMap.set(item.type, arr);
  }
  const typeOrder = ["task", "agent", "alert", "run"];
  const labelKey: Record<string, string> = {
    task: "search.group.tasks",
    agent: "search.group.agents",
    alert: "search.group.alerts",
    run: "search.group.runs",
  };
  const groups: SearchResultGroup[] = [];
  for (const t of typeOrder) {
    const items = groupMap.get(t);
    if (items) {
      groups.push({ type: t, label: labelKey[t] ?? t, items: items.slice(0, 5) });
    }
  }
  return groups;
}

function highlightText(text: string, query: string): React.ReactNode {
  if (!query.trim()) return text;
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const parts = text.split(new RegExp(`(${escaped})`, "gi"));
  return parts.map((part, i) =>
    part.toLowerCase() === query.toLowerCase() ? (
      <mark key={i} className="bg-indigo-500/40 text-white rounded-sm px-0.5">
        {part}
      </mark>
    ) : (
      part
    ),
  );
}

export function GlobalSearch() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [groups, setGroups] = useState<SearchResultGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const { t } = useI18n();
  const router = useRouter();

  const flatItems = flattenResults(groups);

  // ── Keyboard shortcut ──────────────────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };
    document.addEventListener("keydown", handler as unknown as EventListener);
    return () =>
      document.removeEventListener("keydown", handler as unknown as EventListener);
  }, []);

  // ── Focus input when opened ────────────────────────────────────────────────

  useEffect(() => {
    if (open) {
      // Small delay to let the DOM settle
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery("");
      setGroups([]);
      setSelectedIndex(0);
    }
  }, [open]);

  // ── Debounced search ───────────────────────────────────────────────────────

  const doSearch = useCallback(async (q: string) => {
    if (!q.trim()) {
      setGroups([]);
      return;
    }
    setLoading(true);
    try {
      const res = await searchApi(q);
      setGroups(groupResults(res.results));
      setSelectedIndex(0);
    } catch {
      setGroups([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleInputChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => doSearch(value), 300);
    },
    [doSearch],
  );

  // ── Keyboard navigation ────────────────────────────────────────────────────

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, flatItems.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && flatItems[selectedIndex]) {
      e.preventDefault();
      navigateTo(flatItems[selectedIndex]);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  // ── Navigation ─────────────────────────────────────────────────────────────

  const navigateTo = useCallback(
    (item: SearchResultItem) => {
      setOpen(false);
      router.push(item.url);
    },
    [router],
  );

  // ── Close on overlay click ─────────────────────────────────────────────────

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) setOpen(false);
  };

  // ── Render ─────────────────────────────────────────────────────────────────

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[15vh]"
      onClick={handleOverlayClick}
    >
      <div className="w-full max-w-xl bg-gray-900 rounded-xl shadow-2xl border border-gray-700 overflow-hidden">
        {/* ── Search input ──────────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-700">
          <Search size={18} className="text-gray-400 shrink-0" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={t("search.placeholder")}
            className="flex-1 bg-transparent text-white placeholder-gray-500 outline-none text-base"
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        {/* ── Results / Loading ─────────────────────────────────────── */}
        <div className="max-h-96 overflow-y-auto">
          {loading && (
            <div className="px-4 py-8 text-center text-sm text-gray-400">
              Searching...
            </div>
          )}

          {!loading && query.trim() !== "" && groups.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-gray-400">
              {t("search.no_results")}
            </div>
          )}

          {!loading &&
            groups.map((group) => (
              <div key={group.type}>
                <div className="px-4 py-2 text-xs font-semibold uppercase tracking-wider text-gray-500 bg-gray-800/50">
                  {t(group.label)}
                </div>
                {group.items.map((item) => {
                  const idx = flatItems.indexOf(item);
                  const active = idx === selectedIndex;
                  return (
                    <button
                      key={`${item.type}-${item.id}`}
                      onClick={() => navigateTo(item)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className={`w-full text-left px-4 py-3 flex flex-col gap-0.5 transition-colors ${
                        active
                          ? "bg-indigo-600/30 text-white"
                          : "text-gray-300 hover:bg-gray-800"
                      }`}
                    >
                      <span className="text-sm font-medium">
                        {highlightText(item.title, query)}
                      </span>
                      {item.description && (
                        <span className="text-xs text-gray-400 line-clamp-1">
                          {highlightText(item.description, query)}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            ))}
        </div>

        {/* ── Footer hint ──────────────────────────────────────────── */}
        <div className="px-4 py-2 border-t border-gray-700 flex items-center gap-4 text-xs text-gray-500">
          <span>
            <kbd className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 font-mono">
              ↑↓
            </kbd>{" "}
            navigate
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 font-mono">
              ↵
            </kbd>{" "}
            select
          </span>
          <span>
            <kbd className="px-1.5 py-0.5 bg-gray-800 rounded text-gray-400 font-mono">
              esc
            </kbd>{" "}
            close
          </span>
        </div>
      </div>
    </div>
  );
}
