"use client";
import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api, type MeInfo } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

const STEPS = [1, 2, 3] as const;

type Config = {
  name: string;
  industry: string;
  website_url: string;
  timezone: string;
};

export default function OnboardingPage() {
  const { t } = useI18n();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [me, setMe] = useState<MeInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [agentTriggering, setAgentTriggering] = useState(false);
  const [agentTriggered, setAgentTriggered] = useState(false);
  const [config, setConfig] = useState<Config>({
    name: "",
    industry: "",
    website_url: "",
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.get<MeInfo>("/auth/me")
      .then((info) => {
        setMe(info);
        if (info.onboarding_completed) {
          router.replace("/dashboard");
        }
      })
      .catch(() => router.replace("/dashboard"))
      .finally(() => setLoading(false));
  }, [router]);

  const copyKey = useCallback(async () => {
    if (!me?.api_key) return;
    await navigator.clipboard.writeText(me.api_key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [me]);

  const saveConfig = async () => {
    setSaving(true);
    try {
      await api.put("/config", config);
    } catch {
      // Config might not have backend endpoint, just continue
    }
    setSaving(false);
    setStep(3);
  };

  const triggerAgent = async () => {
    setAgentTriggering(true);
    try {
      await api.post("/agents/orchestrator/trigger");
    } catch {
      // May fail if no Celery — that's fine
    }
    setAgentTriggered(true);
    setAgentTriggering(false);
  };

  const completeOnboarding = async () => {
    await api.post("/auth/onboarding/complete");
    router.push("/dashboard");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-950">
        <div className="text-gray-400">{t("onboard.loading")}</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl">
        {/* Steps indicator */}
        <div className="flex justify-center mb-8 gap-2">
          {STEPS.map((s) => (
            <div key={s} className="flex items-center gap-2">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                  s === step
                    ? "bg-indigo-600 text-white"
                    : s < step
                    ? "bg-green-600 text-white"
                    : "bg-gray-700 text-gray-400"
                }`}
              >
                {s < step ? "✓" : s}
              </div>
              {s < 3 && <div className={`w-12 h-0.5 ${s < step ? "bg-green-600" : "bg-gray-700"}`} />}
            </div>
          ))}
        </div>

        <div className="bg-gray-900 rounded-xl p-8 border border-gray-800">
          {/* Step 1: API Key */}
          {step === 1 && me && (
            <div className="space-y-6">
              <div className="text-center">
                <h1 className="text-2xl font-bold text-white">{t("onboard.title")}</h1>
                <p className="text-gray-400 mt-2">{t("onboard.welcome_msg")}</p>
              </div>

              <div>
                <h2 className="text-lg font-semibold text-white mb-2">{t("onboard.step1_title")}</h2>
                <p className="text-sm text-gray-400 mb-4">{t("onboard.step1_desc")}</p>

                <div className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                  <div className="text-xs text-gray-500 mb-1">{t("onboard.api_key_hint")}</div>
                  <code className="text-sm text-indigo-300 break-all font-mono">{me.api_key}</code>
                </div>

                <button
                  onClick={copyKey}
                  className="mt-3 px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-md text-sm"
                >
                  {copied ? t("onboard.copied") : t("onboard.copy_key")}
                </button>
              </div>

              <div className="flex justify-between pt-4">
                <div />
                <button
                  onClick={() => setStep(2)}
                  className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm"
                >
                  {t("onboard.next")}
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Company Setup */}
          {step === 2 && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-xl font-bold text-white">{t("onboard.step2_title")}</h2>
                <p className="text-gray-400 mt-1 text-sm">{t("onboard.step2_desc")}</p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{t("settings.company_name")}</label>
                  <input
                    type="text"
                    value={config.name}
                    onChange={(e) => setConfig((c) => ({ ...c, name: e.target.value }))}
                    className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm border border-gray-700 focus:border-indigo-500 focus:outline-none"
                    placeholder="My Company"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{t("settings.industry")}</label>
                  <input
                    type="text"
                    value={config.industry}
                    onChange={(e) => setConfig((c) => ({ ...c, industry: e.target.value }))}
                    className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm border border-gray-700 focus:border-indigo-500 focus:outline-none"
                    placeholder="Technology / SaaS / E-commerce"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{t("settings.website_url")}</label>
                  <input
                    type="text"
                    value={config.website_url}
                    onChange={(e) => setConfig((c) => ({ ...c, website_url: e.target.value }))}
                    className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm border border-gray-700 focus:border-indigo-500 focus:outline-none"
                    placeholder="https://example.com"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">{t("settings.timezone")}</label>
                  <input
                    type="text"
                    value={config.timezone}
                    onChange={(e) => setConfig((c) => ({ ...c, timezone: e.target.value }))}
                    className="w-full bg-gray-800 text-white rounded px-3 py-2 text-sm border border-gray-700 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              <p className="text-xs text-gray-500">{t("onboard.config_hint")}</p>

              <div className="flex justify-between pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="px-4 py-2 text-gray-400 hover:text-white text-sm"
                >
                  Back
                </button>
                <button
                  onClick={saveConfig}
                  disabled={saving}
                  className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-md text-sm"
                >
                  {saving ? "Saving…" : t("onboard.next")}
                </button>
              </div>
            </div>
          )}

          {/* Step 3: Trigger Agent + Done */}
          {step === 3 && (
            <div className="space-y-6">
              <div className="text-center">
                <h2 className="text-xl font-bold text-white">{t("onboard.step3_title")}</h2>
                <p className="text-gray-400 mt-1 text-sm">{t("onboard.step3_desc")}</p>
              </div>

              <div className="bg-gray-800 rounded-lg p-6 text-center">
                {agentTriggered ? (
                  <div className="space-y-4">
                    <div className="text-4xl">🎉</div>
                    <p className="text-green-400 font-medium">{t("onboard.agent_ready")}</p>
                    <p className="text-sm text-gray-400">{t("onboard.run_check")}</p>
                  </div>
                ) : (
                  <button
                    onClick={triggerAgent}
                    disabled={agentTriggering}
                    className="px-8 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-base font-medium"
                  >
                    {agentTriggering ? t("onboard.triggering") : t("onboard.trigger_agent")}
                  </button>
                )}
              </div>

              <div className="flex justify-between pt-2">
                <button
                  onClick={completeOnboarding}
                  className="px-4 py-2 text-gray-400 hover:text-white text-sm"
                >
                  {t("onboard.skip")}
                </button>
                {agentTriggered && (
                  <button
                    onClick={completeOnboarding}
                    className="px-6 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-md text-sm"
                  >
                    {t("onboard.finish")}
                  </button>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
