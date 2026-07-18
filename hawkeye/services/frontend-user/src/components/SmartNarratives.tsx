// Smart Narratives: turns raw numbers into plain-English, prioritized findings.
// This is the differentiator vs. a generic cloud console — it explains *why*.

import { Lightbulb, TrendingDown, ShieldAlert, AlertTriangle } from "lucide-react";
import type { DashboardSummary, MLPredictions, Recommendation, ComplianceSummary } from "../api";

type Narrative = {
  id: string;
  tone: "good" | "warn" | "bad" | "info";
  icon: React.ReactNode;
  title: string;
  body: string;
};

const TONE: Record<string, string> = {
  good: "border-good/30 bg-good/5 text-good",
  warn: "border-warn/30 bg-warn/5 text-warn",
  bad: "border-bad/30 bg-bad/5 text-bad",
  info: "border-primary/30 bg-primary/5 text-primary",
};

export function SmartNarratives({
  summary,
  predictions,
  recommendations,
  compliance,
}: {
  summary: DashboardSummary | null;
  predictions: MLPredictions | null;
  recommendations: Recommendation[];
  compliance: ComplianceSummary | null;
}) {
  const items: Narrative[] = [];

  if (summary) {
    const topCost = recommendations
      .filter((r) => (r.estimated_savings ?? 0) > 0)
      .sort((a, b) => (b.estimated_savings ?? 0) - (a.estimated_savings ?? 0))[0];
    if (topCost) {
      items.push({
        id: "savings",
        tone: "good",
        icon: <TrendingDown className="h-4 w-4" />,
        title: `$${topCost.estimated_savings?.toFixed(0)}/mo recoverable`,
        body: `“${topCost.title}” is the single biggest saving. Acting on all ${recommendations.length} recommendations frees ~$${summary.totalEstimatedSavings.toFixed(0)}/mo (${Math.round(
          (summary.totalEstimatedSavings / summary.totalMonthlyCostProjection) * 100
        )}% of projected spend).`,
      });
    }
    if ((summary.publicResources ?? 0) > 0) {
      items.push({
        id: "public",
        tone: "bad",
        icon: <ShieldAlert className="h-4 w-4" />,
        title: `${summary.publicResources} resource${summary.publicResources > 1 ? "s" : ""} publicly exposed`,
        body: `Public access widens blast radius and is the top risk driver. Restrict IAM before anything else — it carries no cost but the highest security weight.`,
      });
    }
    if ((summary.unusedResources ?? 0) > 0) {
      items.push({
        id: "unused",
        tone: "warn",
        icon: <AlertTriangle className="h-4 w-4" />,
        title: `${summary.unusedResources} idle / orphaned resources`,
        body: `These draw spend with no workload. Deleting or downsizing them is low-risk and recovers budget immediately.`,
      });
    }
  }

  if (predictions) {
    if ((predictions.anomalies.length ?? 0) > 0) {
      items.push({
        id: "anomaly",
        tone: "bad",
        icon: <AlertTriangle className="h-4 w-4" />,
        title: `ML flagged ${predictions.anomalies.length} anomal${predictions.anomalies.length > 1 ? "ies" : "y"}`,
        body: `Behavior deviates from fleet baseline. Open ML Insights to see the explainable drivers behind each flag.`,
      });
    }
  }

  if (compliance) {
    items.push({
      id: "compliance",
      tone: compliance.score >= 85 ? "good" : compliance.score >= 65 ? "warn" : "bad",
      icon: <ShieldAlert className="h-4 w-4" />,
      title: `Compliance posture ${compliance.score.toFixed(1)}/100`,
      body: `${compliance.violations} policy violation${compliance.violations === 1 ? "" : "s"} across ${compliance.total} resources. Biggest gaps: ${
        [
          compliance.public_resources?.length ? "public exposure" : "",
          compliance.no_backup?.length ? "missing backups" : "",
          compliance.no_audit_logging?.length ? "no audit logging" : "",
        ]
          .filter(Boolean)
          .join(", ") || "none"
      }.`,
    });
  }

  if (items.length === 0) {
    items.push({
      id: "ok",
      tone: "good",
      icon: <Lightbulb className="h-4 w-4" />,
      title: "Fleet looks healthy",
      body: "No anomalies, public exposure, or idle resources detected in the latest cycle.",
    });
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 mb-4">
        <Lightbulb className="h-4 w-4 text-primary" />
        <h2 className="text-sm font-semibold text-foreground">What Hawkeye is telling you</h2>
      </div>
      <div className="space-y-3">
        {items.map((n) => (
          <div key={n.id} className={`flex gap-3 rounded-lg border p-3 ${TONE[n.tone]}`}>
            <div className="mt-0.5 shrink-0">{n.icon}</div>
            <div>
              <div className="text-sm font-semibold leading-tight">{n.title}</div>
              <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{n.body}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
