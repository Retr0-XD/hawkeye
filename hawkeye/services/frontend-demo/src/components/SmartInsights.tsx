import { Lightbulb, ShieldAlert, TrendingDown, AlertTriangle, ArrowUpRight } from "lucide-react";
import type { SmartInsights as Insights, InsightItem } from "../api";
import { censorId } from "../lib/censor";

const LEVEL_STYLES: Record<string, string> = {
  HIGH: "bg-bad/15 text-bad border-bad/30",
  MEDIUM: "bg-warn/15 text-warn border-warn/30",
  LOW: "bg-good/15 text-good border-good/30",
};

const KIND_ICON: Record<string, React.ReactNode> = {
  risk: <ShieldAlert className="h-4 w-4" />,
  recommendation: <TrendingDown className="h-4 w-4" />,
  compliance: <AlertTriangle className="h-4 w-4" />,
};

function RiskBar({ score }: { score: number }) {
  const pct = Math.max(0, Math.min(100, score * 100));
  const color = score >= 0.45 ? "bg-bad" : score >= 0.2 ? "bg-warn" : "bg-good";
  return (
    <div className="mt-2">
      <div className="flex justify-between text-[11px] text-muted-foreground">
        <span>Risk score</span>
        <span className="text-foreground tnum">{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-muted overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function InsightCard({ item, onOpen }: { item: InsightItem; onOpen?: (id: string) => void }) {
  const level = LEVEL_STYLES[item.level] ?? LEVEL_STYLES.LOW;
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="flex items-start gap-3">
        <div className={`mt-0.5 h-8 w-8 rounded-lg grid place-items-center border ${level}`}>
          {KIND_ICON[item.kind]}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] uppercase tracking-wider rounded px-1.5 py-0.5 border ${level}`}>
              {item.level}
            </span>
            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{item.kind}</span>
          </div>
          <div className="mt-1 text-sm font-semibold text-foreground">{item.title}</div>
          <p className="mt-1 text-xs text-muted-foreground">{item.detail}</p>

          {item.drivers && item.drivers.length > 0 && (
            <div className="mt-2 space-y-1">
              <div className="text-[11px] font-medium text-muted-foreground">Why (top drivers):</div>
              {item.drivers.slice(0, 3).map((d, i) => (
                <div key={i} className="flex items-start gap-2 text-[11px]">
                  <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                  <span className="text-foreground">
                    {d.label} <span className="text-muted-foreground">— {d.reason}</span>
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
            {item.resource_id && (
              <button
                className="font-mono text-primary hover:underline"
                onClick={() => onOpen?.(item.resource_id as string)}
              >
                {censorId(item.resource_id)}
              </button>
            )}
            {item.savings ? (
              <span className="text-good tnum">${Number(item.savings).toFixed(2)}/yr</span>
            ) : null}
            {item.blast_radius ? (
              <span className="flex items-center gap-1">
                <ArrowUpRight className="h-3 w-3" /> blast radius {item.blast_radius}
              </span>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

export function SmartInsights({
  insights,
  loading,
  onOpen,
}: {
  insights: Insights | null;
  loading: boolean;
  onOpen?: (id: string) => void;
}) {
  if (loading && !insights) {
    return <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />;
  }

  const items = insights?.insights ?? [];
  const ranking = insights?.risk_ranking ?? [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Actionable Insights</div>
          <div className="text-2xl font-semibold text-foreground tnum">{items.length}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">High Risk</div>
          <div className="text-2xl font-semibold text-bad tnum">{insights?.high_risk_count ?? 0}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Est. Savings</div>
          <div className="text-2xl font-semibold text-good tnum">
            ${Number(insights?.total_estimated_savings ?? 0).toFixed(2)}
          </div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Compliance</div>
          <div className="text-2xl font-semibold text-foreground tnum">{insights?.compliance.score ?? 100}</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 space-y-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Lightbulb className="h-4 w-4 text-primary" /> Prioritized Insights
          </div>
          {items.length === 0 ? (
            <div className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
              No active insights. The engine continuously ranks risks, recommendations and compliance gaps.
            </div>
          ) : (
            items.map((it, i) => <InsightCard key={i} item={it} onOpen={onOpen} />)
          )}
        </div>

        <div className="rounded-xl border border-border bg-card">
          <div className="px-5 py-4 border-b border-border text-sm font-semibold text-foreground">
            Risk Ranking (explainable)
          </div>
          <div className="p-3 space-y-2 max-h-[70vh] overflow-y-auto">
            {ranking.length === 0 ? (
              <p className="text-sm text-muted-foreground px-2 py-4">No scored resources.</p>
            ) : (
              ranking.map((r) => (
                <div key={r.resource_id} className="rounded-xl border border-border bg-muted/30 p-3">
                  <button
                    className="w-full text-left font-mono text-xs text-foreground truncate hover:text-primary"
                    title={r.resource_id}
                    onClick={() => onOpen?.(r.resource_id)}
                  >
                    {censorId(r.resource_id)}
                  </button>
                  <p className="mt-1 text-[11px] text-muted-foreground">{r.reason}</p>
                  <RiskBar score={r.risk_score} />
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
