"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "@/lib/i18n";
import {
  uploadKnowledgeDocument,
  listKnowledgeDocuments,
  deleteKnowledgeDocument,
  semanticSearchKnowledge,
  type KnowledgeDocument,
  type KnowledgeSearchResult,
} from "@/lib/api";
import {
  BookOpen,
  FileText,
  Loader2,
  Trash2,
  Upload,
  Search,
  X,
  AlertCircle,
  CheckCircle,
  Clock,
  UploadCloud,
} from "lucide-react";

type View = "list" | "search";

export default function KnowledgePage() {
  const { t } = useI18n();

  // ── Documents ──────────────────────────────────────────────────────────────
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ── Upload ─────────────────────────────────────────────────────────────────
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ── Search ─────────────────────────────────────────────────────────────────
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<KnowledgeSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);

  // ── Delete ─────────────────────────────────────────────────────────────────
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<KnowledgeDocument | null>(null);

  // ── View toggle ────────────────────────────────────────────────────────────
  const [view, setView] = useState<View>("list");

  // ── Fetch documents ────────────────────────────────────────────────────────
  const fetchDocs = useCallback(async () => {
    setDocsLoading(true);
    setError(null);
    try {
      const res = await listKnowledgeDocuments();
      setDocuments(res.documents);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load documents");
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocs();
  }, [fetchDocs]);

  // ── Upload handlers ────────────────────────────────────────────────────────
  const handleFile = useCallback(
    async (file: File) => {
      setUploading(true);
      setError(null);
      try {
        await uploadKnowledgeDocument(file);
        await fetchDocs();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Upload failed");
      } finally {
        setUploading(false);
      }
    },
    [fetchDocs],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) handleFile(file);
      e.target.value = "";
    },
    [handleFile],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  // ── Delete handler ─────────────────────────────────────────────────────────
  const handleDelete = useCallback(async (doc: KnowledgeDocument) => {
    setConfirmDelete(null);
    setDeletingId(doc.id);
    try {
      await deleteKnowledgeDocument(doc.id);
      setDocuments((prev) => prev.filter((d) => d.id !== doc.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setDeletingId(null);
    }
  }, []);

  // ── Search handler ─────────────────────────────────────────────────────────
  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setSearching(true);
    setSearched(true);
    try {
      const results = await semanticSearchKnowledge(query);
      setSearchResults(results);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Search failed");
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  }, [query]);

  // ── Status badge ───────────────────────────────────────────────────────────
  const StatusBadge = ({ status }: { status: KnowledgeDocument["status"] }) => {
    switch (status) {
      case "uploading":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-yellow-900/50 text-yellow-400 border border-yellow-700">
            <Clock size={12} className="animate-pulse" />
            {t("knowledge.status_uploading")}
          </span>
        );
      case "ready":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-green-900/50 text-green-400 border border-green-700">
            <CheckCircle size={12} />
            {t("knowledge.status_ready")}
          </span>
        );
      case "error":
        return (
          <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-900/50 text-red-400 border border-red-700">
            <AlertCircle size={12} />
            {t("knowledge.status_error")}
          </span>
        );
    }
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white">{t("knowledge.title")}</h1>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setView(view === "list" ? "search" : "list")}
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors ${
              view === "search"
                ? "bg-indigo-600 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
          >
            <Search size={16} />
            {t("knowledge.search")}
          </button>
          <label
            className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg cursor-pointer transition-colors ${
              uploading
                ? "bg-indigo-600/50 text-gray-300 cursor-not-allowed"
                : "bg-indigo-600 hover:bg-indigo-500 text-white"
            }`}
          >
            {uploading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <Upload size={16} />
            )}
            {uploading ? t("knowledge.uploading") : t("knowledge.upload")}
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleFileChange}
              disabled={uploading}
              accept=".pdf,.txt,.md,.csv,.json,.html,.htm"
            />
          </label>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="flex items-center gap-2 bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-3 text-sm">
          <AlertCircle size={16} />
          <span>{error}</span>
          <button onClick={() => setError(null)} className="ml-auto">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Drag-and-drop zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? "border-indigo-500 bg-indigo-900/20"
            : "border-gray-600 hover:border-gray-500 bg-gray-800/50"
        }`}
      >
        <UploadCloud
          size={40}
          className={`mx-auto mb-2 ${dragOver ? "text-indigo-400" : "text-gray-500"}`}
        />
        <p className={`text-sm ${dragOver ? "text-indigo-300" : "text-gray-400"}`}>
          {dragOver ? t("knowledge.drag_active") : t("knowledge.drop_hint")}
        </p>
        <p className="text-xs text-gray-500 mt-1">PDF, TXT, Markdown, CSV, JSON, HTML</p>
      </div>

      {/* Loading state */}
      {docsLoading && (
        <div className="flex items-center justify-center py-12 text-gray-400">
          <Loader2 size={24} className="animate-spin mr-2" />
          Loading...
        </div>
      )}

      {/* ── Document list ──────────────────────────────────────────────────── */}
      {!docsLoading && view === "list" && (
        <>
          {documents.length === 0 ? (
            <div className="text-center py-12 text-gray-400">
              <BookOpen size={48} className="mx-auto mb-3 text-gray-600" />
              <p>{t("knowledge.empty")}</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead>
                  <tr className="text-gray-500 text-xs uppercase tracking-wider border-b border-gray-700">
                    <th className="py-3 px-4 font-medium">{t("knowledge.filename")}</th>
                    <th className="py-3 px-4 font-medium">{t("knowledge.type")}</th>
                    <th className="py-3 px-4 font-medium">{t("knowledge.status")}</th>
                    <th className="py-3 px-4 font-medium text-right">{t("knowledge.chunks")}</th>
                    <th className="py-3 px-4 font-medium">{t("knowledge.date")}</th>
                    <th className="py-3 px-4 font-medium"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {documents.map((doc) => (
                    <tr
                      key={doc.id}
                      className="text-gray-300 hover:bg-gray-800/50 transition-colors"
                    >
                      <td className="py-3 px-4">
                        <div className="flex items-center gap-2">
                          <FileText size={16} className="text-gray-500 shrink-0" />
                          <span className="truncate max-w-[240px]" title={doc.filename}>
                            {doc.filename}
                          </span>
                        </div>
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded">
                          {doc.file_type.toUpperCase()}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <StatusBadge status={doc.status} />
                      </td>
                      <td className="py-3 px-4 text-right text-gray-400">
                        {doc.chunk_count}
                      </td>
                      <td className="py-3 px-4 text-gray-400 text-xs">
                        {new Date(doc.created_at).toLocaleDateString()}
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={() => setConfirmDelete(doc)}
                          disabled={deletingId === doc.id}
                          className="flex items-center gap-1.5 px-3 py-1.5 bg-red-700 hover:bg-red-600 disabled:opacity-50 text-white text-xs rounded transition-colors ml-auto"
                          title={t("knowledge.delete")}
                        >
                          {deletingId === doc.id ? (
                            <Loader2 size={12} className="animate-spin" />
                          ) : (
                            <Trash2 size={12} />
                          )}
                          {t("knowledge.delete")}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {/* ── Search view ────────────────────────────────────────────────────── */}
      {!docsLoading && view === "search" && (
        <div className="space-y-4">
          <div className="flex gap-3">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder={t("knowledge.search_placeholder")}
              className="flex-1 bg-gray-800 text-white rounded-lg px-4 py-2 border border-gray-700 focus:border-indigo-500 focus:outline-none text-sm"
            />
            <button
              onClick={handleSearch}
              disabled={searching || !query.trim()}
              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
            >
              {searching ? (
                <Loader2 size={16} className="animate-spin" />
              ) : (
                <Search size={16} />
              )}
              {searching ? t("knowledge.searching") : t("knowledge.search")}
            </button>
          </div>

          {searched && searchResults.length === 0 && !searching && (
            <div className="text-center py-12 text-gray-400">
              <Search size={48} className="mx-auto mb-3 text-gray-600" />
              <p>{t("knowledge.no_results")}</p>
            </div>
          )}

          <div className="space-y-3">
            {searchResults.map((r, i) => (
              <div
                key={`${r.id}-${r.chunk_index}`}
                className="bg-gray-800 rounded-lg p-4 border border-gray-700"
              >
                <div className="flex items-center gap-2 mb-2">
                  <FileText size={14} className="text-gray-500" />
                  <span className="text-white text-sm font-medium truncate">
                    {r.filename}
                  </span>
                  <span className="text-xs bg-gray-700 text-gray-400 px-2 py-0.5 rounded ml-auto shrink-0">
                    {r.file_type.toUpperCase()}
                  </span>
                </div>
                <p className="text-gray-400 text-sm mb-2 line-clamp-3">{r.snippet}</p>
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>
                    {t("knowledge.score")}: {(r.score * 100).toFixed(0)}%
                  </span>
                  <span>
                    {t("knowledge.snippet")} #{r.chunk_index + 1}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Confirm delete dialog ──────────────────────────────────────────── */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
          <div className="bg-gray-800 rounded-lg border border-gray-700 w-full max-w-md mx-4 p-6 space-y-4">
            <div className="flex items-center gap-3">
              <AlertCircle size={20} className="text-red-400" />
              <h3 className="text-white font-semibold">{t("knowledge.delete_confirm")}</h3>
            </div>
            <p className="text-gray-400 text-sm">
              {t("knowledge.delete_confirm_body").replace(
                "{name}",
                confirmDelete.filename,
              )}
            </p>
            {confirmDelete.error_message && (
              <div className="bg-red-900/30 border border-red-700 text-red-300 rounded p-2 text-xs">
                {t("knowledge.error_prefix")}: {confirmDelete.error_message}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-2">
              <button
                onClick={() => setConfirmDelete(null)}
                className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm rounded transition-colors"
              >
                {t("knowledge.cancel")}
              </button>
              <button
                onClick={() => handleDelete(confirmDelete)}
                className="px-4 py-2 bg-red-700 hover:bg-red-600 text-white text-sm rounded transition-colors"
              >
                {t("knowledge.confirm")}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
