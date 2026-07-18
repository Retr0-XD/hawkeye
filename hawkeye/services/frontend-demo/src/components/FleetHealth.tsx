// Fleet Health hero: a single at-a-glance read of posture + cost + risk.
// Computes everything from the summary/predictions so it stays honest.

import { RadialGauge } from "./charts";
import type { DashboardSummary, MLPredictions } from "../api";

function healthScore(s: DashboardSummary, p: MLPredictions | null): number {
  const total = s.resourceCount || 1;
  const publicPenalty = (s.publicResources || 0) * 6;
  const unusedPenalty = (s.unusedResources || 0) * 2;
  const anomalyPenalty = (p?.anomalies.length || 0) * 5;
  const failurePenalty = (p?.failure_risks.length || 0) * 4;
  const raw = 100 - (publicPenalty + unusedPenalty + anomalyPenalty + failurePenalty) / total * 100 * 0.15;
  return Math.max(0, Math.min(100, raw));
}

function Stat({ label, value, sub, tone }: { label: string; value: string; sub?: string; tone?: "good" | "warn" | "bad" }) {
  const color = tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "good" ? "text-good" : "text-foreground";
  return (
    <div className="flex flex-col">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className={`tnum text-xl font-semibold leading-tight ${color}`}>{value}</span>
      {sub && <span className="text-[11px] text-muted-foreground">{sub}</span>}
    </div>
  );
}

export function FleetHealth({
  summary,
  predictions,
}: {
  summary: DashboardSummary | null;
  predictions: MLPredictions | null;
}) {
  if (!summary) {
    return <div className="h-44 rounded-xl border border-border bg-card animate-pulse" />;
  }
  const score = healthScore(summary, predictions);
  const scoreColor = score >= 85 ? "#3ddc97" : score >= 65 ? "#f5b14c" : "#ff6b81";
  const savingsPct = summary.totalMonthlyCostProjection
    ? Math.round((summary.totalEstimatedSavings / summary.totalMonthlyCostProjection) * 100)
    : 0;

  return (
    <div className="rounded-xl border border-border bg-card p-5 flex flex-col sm:flex-row gap-6 items-center sm:items-stretch">
      <div className="flex flex-col items-center justify-center gap-2 shrink-0">
        <RadialGauge value={score} label="Fleet Health" color={scoreColor} size={132} />
        <span className="text-[11px] text-muted-foreground">composite of risk · cost · hygiene</span>
      </div>
      <div className="flex-1 grid grid-cols-2 sm:grid-cols-4 gap-4 sm:gap-5 content-center">
        <Stat
          label="Resources"
          value={String(summary.resourceCount)}
          sub={`${Object.keys(summary.byType ?? {}).length} types`}
        />
        <Stat
          label="Monthly Spend"
          value={`$${summary.totalMonthlyCostProjection.toFixed(0)}`}
          sub="projected"
        />
        <Stat
          label="Open Risks"
          value={String((predictions?.anomalies.length ?? 0) + (predictions?.failure_risks.length ?? 0))}
          sub={`${predictions?.anomalies.length ?? 0} anomaly · ${predictions?.failure_risks.length ?? 0} fail`}
          tone={(predictions?.anomalies.length ?? 0) > 0 ? "bad" : "good"}
        />
        <Stat
          label="Actionable Savings"
          value={`$${summary.totalEstimatedSavings.toFixed(0)}`}
          sub={`${savingsPct}% of spend`}
          tone="good"
        />
      </div>
    </div>
  );
}
