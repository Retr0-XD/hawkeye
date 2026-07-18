// Cost Ranking: ranks resources by monthly cost and shows deviation from the
// fleet average. Surfaces the few resources that drive most of the bill.

import type { Resource } from "../api";
import { censorName } from "../lib/censor";

export function CostRanking({
  resources,
  limit = 8,
}: {
  resources: Resource[];
  limit?: number;
}) {
  const withCost = resources
    .filter((r) => (r.monthly_cost_projection ?? 0) > 0)
    .sort((a, b) => (b.monthly_cost_projection ?? 0) - (a.monthly_cost_projection ?? 0));
  const avg =
    withCost.reduce((s, r) => s + (r.monthly_cost_projection ?? 0), 0) / (withCost.length || 1);
  const top = withCost.slice(0, limit);
  const max = top[0]?.monthly_cost_projection ?? 1;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Cost Drivers</h2>
        <span className="text-[11px] text-muted-foreground tnum">
          fleet avg ${avg.toFixed(0)}/mo
        </span>
      </div>
      {top.length === 0 ? (
        <div className="h-40 grid place-items-center text-sm text-muted-foreground">
          No cost data yet
        </div>
      ) : (
        <div className="space-y-2.5">
          {top.map((r) => {
            const v = r.monthly_cost_projection ?? 0;
            const pct = (v / max) * 100;
            const over = v > avg;
            const dev = avg ? Math.round(((v - avg) / avg) * 100) : 0;
            return (
              <div key={r.id} className="flex items-center gap-3 text-sm">
                <div className="w-[130px] shrink-0 truncate text-muted-foreground" title={r.name}>
                  {censorName(r.name ?? r.id.split("/").pop() ?? r.id)}
                </div>
                <div className="flex-1 h-5 rounded bg-muted/50 overflow-hidden relative">
                  <div
                    className={`h-full rounded ${over ? "bg-bad/70" : "bg-good/70"}`}
                    style={{ width: `${pct}%` }}
                  />
                  {/* fleet-average marker */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-foreground/60"
                    style={{ left: `${Math.min(100, (avg / max) * 100)}%` }}
                    title="fleet average"
                  />
                </div>
                <div className="w-16 shrink-0 text-right tnum text-foreground">
                  ${v.toFixed(0)}
                </div>
                <div
                  className={`w-12 shrink-0 text-right tnum text-xs ${
                    over ? "text-bad" : "text-good"
                  }`}
                >
                  {dev > 0 ? "+" : ""}
                  {dev}%
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="text-[11px] text-muted-foreground mt-3">
        Bars past the marker exceed fleet average. These are the first targets for
        right-sizing.
      </p>
    </div>
  );
}
