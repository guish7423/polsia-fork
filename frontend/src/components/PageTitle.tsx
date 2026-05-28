"use client";
import { useI18n } from "@/lib/i18n";

export function PageTitle({ i18nKey, fallback }: { i18nKey: string; fallback?: string }) {
  const { t } = useI18n();
  return <h1 className="text-2xl font-bold text-white">{t(i18nKey)}</h1>;
}

export function SectionTitle({ i18nKey }: { i18nKey: string }) {
  const { t } = useI18n();
  return (
    <h2 className="text-sm font-semibold text-gray-400 mb-3 uppercase tracking-wider">
      {t(i18nKey)}
    </h2>
  );
}

export function Text({ i18nKey, fallback }: { i18nKey: string; fallback?: string }) {
  const { t } = useI18n();
  return <>{t(i18nKey)}</>;
}
