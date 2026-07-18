import { Boxes, DollarSign, ShieldAlert, Activity } from "lucide-react";
import type { DashboardSummary, MLPredictions } from "../api";

function Card({
  label,
  value,
  sub,
  tone,
  icon,
  accent,
}: {
  label: string;
  value: string;
  sub?: string;
  tone?: "good" | "warn" | "bad";
  icon: React.ReactNode;
  accent?: string;
}) {
  const toneClass =
    tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : tone === "good" ? "text-good" : "text-foreground";
  return (
    <div className="relative overflow-hidden rounded-xl border border-border bg-card p-4">
      <div
        className="absolute -right-6 -top-6 h-20 w-20 rounded-full opacity-10 blur-2xl"
        style={{ background: accent ?? "#2dd4bf" }}
      />
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </div>
        <span className="text-muted-foreground/70">{icon}</span>
      </div>
      <div className={`mt-2 text-2xl font-bold tnum ${toneClass}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[11px] text-muted-foreground">{sub}</div>}
    </div>
  );
}

export function KpiCards({
  summary,
  predictions,
  loading,
}: {
  summary: DashboardSummary | null;
  predictions: MLPredictions | null;
  loading: boolean;
}) {
  if (loading && !summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="h-24 rounded-xl border border-border bg-card animate-pulse" />
        ))}
      </div>
    );
  }

  const anomalies = predictions?.anomalies.length ?? 0;
  const publicRes = summary?.publicResources ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <Card
        label="Resources"
        value={String(summary?.resourceCount ?? 0)}
        sub={`${Object.keys(summary?.byType ?? {}).length} types`}
        icon={<Boxes className="h-4 w-4" />}
        accent="#2dd4bf"
      />
      <Card
        label="Est. Monthly Cost"
        value={`$${((summary?.totalMonthlyCostProjection ?? 0) || 0).toFixed(2)}`}
        sub="projected · free tier"
        tone="good"
        icon={<DollarSign className="h-4 w-4" />}
        accent="#3ddc97"
      />
      <Card
        label="Public Exposure"
        value={String(publicRes)}
        sub={publicRes > 0 ? "review access" : "none exposed"}
        tone={publicRes > 0 ? "warn" : "good"}
        icon={<ShieldAlert className="h-4 w-4" />}
        accent="#f5b14c"
      />
      <Card
        label="ML Anomalies"
        value={String(anomalies)}
        sub={`${predictions?.scored ?? 0} scored`}
        tone={anomalies > 0 ? "bad" : "good"}
        icon={<Activity className="h-4 w-4" />}
        accent="#ff6b81"
      />
    </div>
  );
}
