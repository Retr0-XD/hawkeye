import { useMemo } from "react";
import { AlertTriangle, Lightbulb, ShieldCheck } from "lucide-react";
import type { MLPredictions, Recommendation } from "../api";
import { BarChart, DistributionBar } from "./charts";

const RISK_COLORS: Record<string, string> = {
  HIGH: "#ff6b81",
  MEDIUM: "#f5b14c",
  LOW: "#3ddc97",
};

export function RiskDistribution({ predictions }: { predictions: MLPredictions | null }) {
  const dist = useMemo(() => {
    const counts: Record<string, number> = { HIGH: 0, MEDIUM: 0, LOW: 0 };
    for (const it of predictions?.items ?? []) {
      const lvl = (it as any)?.explanation?.risk_level ?? "LOW";
      counts[lvl] = (counts[lvl] ?? 0) + 1;
    }
    return [
      { label: "High", value: counts.HIGH, color: RISK_COLORS.HIGH },
      { label: "Medium", value: counts.MEDIUM, color: RISK_COLORS.MEDIUM },
      { label: "Low", value: counts.LOW, color: RISK_COLORS.LOW },
    ];
  }, [predictions]);

  return (
    <div className="rounded-xl border border-border bg-card p-5 elevate">
      <div className="flex items-center gap-2 mb-4">
        <AlertTriangle className="h-4 w-4 text-warn" />
        <h2 className="text-sm font-semibold text-foreground">Risk Distribution</h2>
      </div>
      <DistributionBar segments={dist} />
      <p className="mt-3 text-[11px] text-muted-foreground">
        Explainable risk across {predictions?.items?.length ?? 0} scored resources.
      </p>
    </div>
  );
}

export function RecommendationBreakdown({ recommendations }: { recommendations: Recommendation[] }) {
  const byType = useMemo(() => {
    const m: Record<string, number> = {};
    for (const r of recommendations) {
      const t = r.type ?? "Other";
      m[t] = (m[t] ?? 0) + 1;
    }
    return Object.entries(m)
      .map(([label, value]) => ({ label, value }))
      .sort((a, b) => b.value - a.value);
  }, [recommendations]);

  const totalSavings = useMemo(
    () => recommendations.reduce((s, r) => s + (Number(r.estimated_savings) || 0), 0),
    [recommendations]
  );

  return (
    <div className="rounded-xl border border-border bg-card p-5 elevate">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-primary" />
          <h2 className="text-sm font-semibold text-foreground">Recommendations by Type</h2>
        </div>
        <span className="text-xs text-muted-foreground tnum">
          ${totalSavings.toFixed(2)} est. savings
        </span>
      </div>
      <BarChart data={byType} height={Math.max(160, byType.length * 38)} color="#7c8cf8" />
    </div>
  );
}

export function ComplianceMiniCard({
  score,
  violations,
  total,
}: {
  score: number | null;
  violations: number;
  total: number;
}) {
  const color = score == null ? "#8b98ad" : score >= 90 ? "#3ddc97" : score >= 70 ? "#f5b14c" : "#ff6b81";
  return (
    <div className="rounded-xl border border-border bg-card p-5 elevate">
      <div className="flex items-center gap-2 mb-4">
        <ShieldCheck className="h-4 w-4 text-good" />
        <h2 className="text-sm font-semibold text-foreground">Compliance Posture</h2>
      </div>
      <div className="flex items-end gap-3">
        <div className="text-4xl font-bold tnum" style={{ color }}>
          {score ?? "—"}
        </div>
        <div className="text-xs text-muted-foreground mb-1">/ 100</div>
      </div>
      <div className="mt-3 text-xs text-muted-foreground">
        {violations} violations across {total} resources
      </div>
    </div>
  );
}
