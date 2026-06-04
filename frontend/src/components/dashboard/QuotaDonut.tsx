"use client";
import { useI18n } from "@/lib/i18n";

interface QuotaDonutProps {
  labelKey: string;
  current: number;
  limit: number;
  usagePct: number;
  color: string;
  allowed?: boolean;
}

export function QuotaDonut({ labelKey, current, limit, usagePct, color, allowed }: QuotaDonutProps) {
  const { t } = useI18n();
  const radius = 36;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(usagePct, 100);
  const offset = circumference * (1 - clamped / 100);
  const displayCurrent = typeof current === "number" ? current.toLocaleString() : String(current);
  const displayLimit = typeof limit === "number" ? limit.toLocaleString() : String(limit);

  return (
    <div className="bg-gray-800 rounded-lg p-5 flex flex-col items-center">
      {/* SVG Donut */}
      <svg width="96" height="96" viewBox="0 0 96 96" className="-rotate-90">
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke="#1f2937"
          strokeWidth="8"
        />
        <circle
          cx="48"
          cy="48"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>

      {/* Center label overlay */}
      <div className="flex flex-col items-center -mt-14 mb-2">
        <span className="text-xl font-bold text-white">{clamped}%</span>
        <span className="text-[10px] text-gray-400">used</span>
      </div>

      {/* Label */}
      <p className="text-gray-400 text-xs uppercase tracking-wider mt-1">
        {t(labelKey)}
      </p>

      {/* Current / Limit */}
      <p className="text-white text-sm font-medium mt-0.5">
        {displayCurrent} / {displayLimit}
      </p>

      {/* Allowed badge */}
      {allowed && (
        <span className="mt-2 inline-block text-[10px] bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded font-medium">
          Allowed
        </span>
      )}
    </div>
  );
}
