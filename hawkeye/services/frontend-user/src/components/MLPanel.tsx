import type { MLPredictions } from "../api";
import { censorId } from "../lib/censor";

function Bar({ label, value, danger }: { label: string; value: number; danger?: boolean }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  return (
    <div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <span className={danger ? "text-bad tnum" : "text-foreground tnum"}>{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-1 h-1.5 rounded bg-muted overflow-hidden">
        <div className={`h-full ${danger ? "bg-bad" : "bg-primary"}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function MLPanel({ predictions, loading }: { predictions: MLPredictions | null; loading: boolean }) {
  if (loading && !predictions) {
    return <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />;
  }

  const items = predictions?.items ?? [];
  const ranked = [...items]
    .map((it) => {
      const exp = (it as unknown as { explanation?: any }).explanation;
      return { it, score: exp?.risk_score ?? 0, level: exp?.risk_level ?? "LOW" };
    })
    .sort((a, b) => b.score - a.score);
  const top = ranked.filter((r) => r.level === "HIGH" || r.level === "MEDIUM").slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Total Resources</div>
          <div className="text-2xl font-semibold text-foreground tnum">{predictions?.total_resources ?? 0}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Scored</div>
          <div className="text-2xl font-semibold text-foreground tnum">{predictions?.scored ?? 0}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Anomalies</div>
          <div className="text-2xl font-semibold text-bad tnum">{predictions?.anomalies.length ?? 0}</div>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Failure Risks</div>
          <div className="text-2xl font-semibold text-warn tnum">{predictions?.failure_risks.length ?? 0}</div>
        </div>
      </div>

      {top.length > 0 && (
        <div className="rounded-xl border border-border bg-card p-5">
          <div className="text-sm font-semibold text-foreground mb-3">Top Explainable Risks</div>
          <div className="space-y-2">
            {top.map(({ it, score, level }) => (
              <div key={it.resource_id} className="flex items-center gap-3">
                <span
                  className={`text-[10px] rounded px-1.5 py-0.5 shrink-0 w-14 text-center ${
                    level === "HIGH" ? "bg-bad/15 text-bad" : "bg-warn/15 text-warn"
                  }`}
                >
                  {level}
                </span>
                <span className="font-mono text-xs text-muted-foreground truncate flex-1" title={it.resource_id}>
                  {censorId(it.resource_id)}
                </span>
                <div className="w-32 h-1.5 rounded bg-muted overflow-hidden">
                  <div
                    className={`h-full ${level === "HIGH" ? "bg-bad" : "bg-warn"}`}
                    style={{ width: `${Math.round(score * 100)}%` }}
                  />
                </div>
                <span className="text-xs tnum text-foreground w-10 text-right">{Math.round(score * 100)}%</span>
              </div>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground mt-3">
            Ranked by blended explainable risk (model score + structural signals). Open a resource for the full driver breakdown.
          </p>
        </div>
      )}

      <div className="rounded-xl border border-border bg-card">
        <div className="px-5 py-4 border-b border-border text-sm font-semibold text-foreground">Per-Resource ML Predictions</div>
        <div className="p-3 space-y-2 max-h-[60vh] overflow-y-auto">
          {items.length === 0 && (
            <p className="text-sm text-muted-foreground px-2 py-4">
              No scored resources. The ML service needs metrics/cost history to score resources (idle serverless services
              report near-zero features and are returned as neutral).
            </p>
          )}
          {items.map((it) => (
            <div key={it.resource_id} className="rounded-xl border border-border bg-muted/30 p-3">
              <div className="flex items-center justify-between gap-2">
                <span className="font-mono text-xs text-foreground truncate" title={it.resource_id}>
                  {censorId(it.resource_id)}
                </span>
                <div className="flex gap-2 shrink-0">
                  {it.anomaly?.is_anomaly && <span className="text-[11px] rounded px-2 py-0.5 bg-bad/15 text-bad">anomaly</span>}
                  {it.failure?.is_high_risk && <span className="text-[11px] rounded px-2 py-0.5 bg-warn/15 text-warn">risk</span>}
                  {!it.anomaly?.is_anomaly && !it.failure?.is_high_risk && (
                    <span className="text-[11px] rounded px-2 py-0.5 bg-good/15 text-good">healthy</span>
                  )}
                </div>
              </div>
              <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-2">
                <Bar label="Anomaly score" value={it.anomaly?.score ?? 0} danger={it.anomaly?.is_anomaly} />
                <Bar label="Failure probability" value={it.failure?.probability ?? 0} danger={it.failure?.is_high_risk} />
              </div>
              {(() => {
                const exp = (it as unknown as { explanation?: any }).explanation;
                if (!exp) return null;
                return (
                  <div className="mt-2 space-y-1">
                    <div className="flex items-center gap-2 text-[11px]">
                      <span className="text-muted-foreground">Risk {Math.round(exp.risk_score * 100)}% · {exp.risk_level}</span>
                    </div>
                    <p className="text-[11px] text-muted-foreground">{exp.reason}</p>
                    {exp.drivers?.length > 0 && (
                      <div className="flex flex-wrap gap-1">
                        {exp.drivers.slice(0, 3).map((d: any, i: number) => (
                          <span key={i} className="text-[10px] rounded bg-muted px-1.5 py-0.5 text-foreground">
                            {d.label}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })()}
              {it.cost_forecast && (
                <div className="mt-2 text-xs text-muted-foreground">
                  Cost forecast: <span className="text-foreground tnum">${it.cost_forecast.predicted_total.toFixed(2)}</span> (7d)
                  {it.cost_forecast.spike && <span className="text-warn"> · spike</span>}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
