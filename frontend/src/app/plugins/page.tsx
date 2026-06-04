"use client";

import { useState, useEffect } from "react";
import { PageTitle } from "@/components/PageTitle";
import { useI18n } from "@/lib/i18n";
import { Plugin } from "@/lib/api";
import { Plus, Trash2, Power, AlertCircle, Loader2 } from "lucide-react";

export default function PluginsPage() {
  const { t } = useI18n();
  const [plugins, setPlugins] = useState<Plugin[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState({ name: "", description: "", webhook_url: "", hooks: "" });
  const [submitting, setSubmitting] = useState(false);

  const fetchPlugins = async () => {
    try {
      setLoading(true);
      const res = await fetch("/api/v1/plugins");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setPlugins(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load plugins");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchPlugins(); }, []);

  const handleRegister = async () => {
    setSubmitting(true);
    try {
      const hooks = formData.hooks
        ? formData.hooks.split(",").map((h) => h.trim()).filter(Boolean)
        : [];
      const res = await fetch("/api/v1/plugins", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: formData.name,
          manifest: JSON.stringify({
            description: formData.description,
            hooks,
          }),
          webhook_url: formData.webhook_url || undefined,
        }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setShowForm(false);
      setFormData({ name: "", description: "", webhook_url: "", hooks: "" });
      await fetchPlugins();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register plugin");
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggle = async (id: number, enabled: boolean) => {
    try {
      const res = await fetch(`/api/v1/plugins/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: !enabled }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchPlugins();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to toggle plugin");
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(t("plugins.deleteConfirm") || "Are you sure?")) return;
    try {
      const res = await fetch(`/api/v1/plugins/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await fetchPlugins();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete plugin");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageTitle i18nKey="plugins.title" />

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <span className="text-sm">{error}</span>
          <button onClick={() => setError(null)} className="ml-auto text-red-500 hover:text-red-700">&times;</button>
        </div>
      )}

      <div className="flex justify-between items-center">
        <p className="text-sm text-gray-500">{plugins.length} {t("plugins.plugins")}</p>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors text-sm"
        >
          <Plus className="w-4 h-4" />
          {t("plugins.register")}
        </button>
      </div>

      {showForm && (
        <div className="p-4 bg-white border border-gray-200 rounded-lg space-y-3">
          <input
            placeholder={t("plugins.name") || "Plugin name"}
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <input
            placeholder={t("plugins.description") || "Description"}
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <input
            placeholder={t("plugins.webhookUrl") || "Webhook URL (optional)"}
            value={formData.webhook_url}
            onChange={(e) => setFormData({ ...formData, webhook_url: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <input
            placeholder={t("plugins.hooksPlaceholder") || "Hook names, comma-separated (e.g. before_agent_run, after_agent_run)"}
            value={formData.hooks}
            onChange={(e) => setFormData({ ...formData, hooks: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md text-sm"
          />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowForm(false)} className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-800">
              {t("common.cancel") || "Cancel"}
            </button>
            <button
              onClick={handleRegister}
              disabled={submitting || !formData.name}
              className="px-4 py-1.5 bg-indigo-600 text-white rounded-md text-sm hover:bg-indigo-700 disabled:opacity-50"
            >
              {submitting ? t("plugins.registering") || "Registering..." : t("plugins.register") || "Register"}
            </button>
          </div>
        </div>
      )}

      {plugins.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <Power className="w-12 h-12 mx-auto mb-3 opacity-50" />
          <p className="text-lg font-medium text-gray-500">{t("plugins.emptyTitle") || "No plugins registered"}</p>
          <p className="text-sm mt-1">{t("plugins.emptyDesc") || "Register your first plugin to extend agent capabilities"}</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {plugins.map((p) => {
            const manifest = typeof p.manifest === "string" ? JSON.parse(p.manifest) : p.manifest;
            return (
              <div key={p.id} className="p-4 bg-white border border-gray-200 rounded-lg hover:shadow-sm transition-shadow">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-medium text-gray-900">{p.name}</h3>
                    {manifest?.description && (
                      <p className="text-xs text-gray-500 mt-0.5">{manifest.description}</p>
                    )}
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                    p.enabled ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"
                  }`}>
                    {p.enabled ? (t("common.enabled") || "Enabled") : (t("common.disabled") || "Disabled")}
                  </span>
                </div>
                {manifest?.hooks && manifest.hooks.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {manifest.hooks.map((hook: string) => (
                      <span key={hook} className="px-2 py-0.5 bg-indigo-50 text-indigo-600 rounded text-xs">
                        {hook}
                      </span>
                    ))}
                  </div>
                )}
                <div className="flex gap-2 pt-2 border-t border-gray-100">
                  <button
                    onClick={() => handleToggle(p.id, p.enabled)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-indigo-600 transition-colors"
                  >
                    <Power className="w-3 h-3" />
                    {p.enabled ? (t("common.disable") || "Disable") : (t("common.enable") || "Enable")}
                  </button>
                  <button
                    onClick={() => handleDelete(p.id)}
                    className="flex items-center gap-1 text-xs text-gray-500 hover:text-red-600 transition-colors ml-auto"
                  >
                    <Trash2 className="w-3 h-3" />
                    {t("common.delete") || "Delete"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
