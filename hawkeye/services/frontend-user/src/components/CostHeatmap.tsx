// Cost Heatmap: weekly cost intensity by service. Reveals spikes and patterns
// a single total number hides. Accepts either explicit rows/cols/values (demo
// stub) or a live daily cost trend that is reshaped into a weekday × week grid.

import { Heatmap } from "./charts";
import type { CostPoint } from "../api";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

export function CostHeatmap({
  rows,
  cols,
  values,
  trend,
}: {
  rows?: string[];
  cols?: string[];
  values?: number[][];
  trend?: CostPoint[];
}) {
  // Derive a real grid from the live daily cost trend when no explicit data
  // is supplied (the authenticated console always uses this path).
  let useRows = rows ?? [];
  let useCols = cols ?? [];
  let useValues = values ?? [];

  if (useValues.length === 0 && trend && trend.length > 0) {
    // Group the last N days into weeks (columns) by weekday (rows).
    const recent = trend.slice(-35); // up to 5 weeks
    const weeks = Math.ceil(recent.length / 7);
    useRows = WEEKDAYS;
    useCols = Array.from({ length: weeks }, (_, w) => `W${w + 1}`);
    useValues = WEEKDAYS.map((_, di) =>
      Array.from({ length: weeks }, (_, wi) => {
        const idx = wi * 7 + di;
        return idx < recent.length ? recent[idx].total_cost : 0;
      })
    );
  }

  const hasData = useValues.length > 0 && useValues.some((r) => r.some((v) => v > 0));
  const max = Math.max(...useValues.flat(), 1);
  const peak = hasData
    ? useValues
        .flatMap((row, ri) => row.map((v, ci) => ({ v, ri, ci })))
        .sort((a, b) => b.v - a.v)[0]
    : null;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Weekly Cost Intensity</h2>
        {peak && (
          <span className="text-[11px] text-muted-foreground">
            peak: {useRows[peak.ri]} · {useCols[peak.ci]}
          </span>
        )}
      </div>
      {hasData ? (
        <Heatmap rows={useRows} cols={useCols} values={useValues} color="#2dd4bf" />
      ) : (
        <div className="h-24 flex items-center justify-center rounded bg-muted/40 text-xs text-muted-foreground">
          No cost data yet — trend will populate as billing accrues.
        </div>
      )}
      <div className="flex items-center gap-2 mt-3 text-[11px] text-muted-foreground">
        <span>low</span>
        <div className="h-2 w-24 rounded-full" style={{ background: "linear-gradient(90deg, rgba(45,212,191,0.12), #2dd4bf)" }} />
        <span>high (${max.toFixed(2)})</span>
      </div>
    </div>
  );
}
