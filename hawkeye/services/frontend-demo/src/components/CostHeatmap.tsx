// Cost Heatmap: weekly cost intensity by service. Reveals spikes and patterns
// a single total number hides.

import { Heatmap } from "./charts";

export function CostHeatmap({
  rows,
  cols,
  values,
}: {
  rows: string[];
  cols: string[];
  values: number[][];
}) {
  const max = Math.max(...values.flat(), 1);
  const peak = values
    .flatMap((row, ri) => row.map((v, ci) => ({ v, ri, ci })))
    .sort((a, b) => b.v - a.v)[0];

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Weekly Cost Intensity</h2>
        <span className="text-[11px] text-muted-foreground">
          peak: {rows[peak.ri]} · {cols[peak.ci]}
        </span>
      </div>
      <Heatmap rows={rows} cols={cols} values={values} color="#2dd4bf" />
      <div className="flex items-center gap-2 mt-3 text-[11px] text-muted-foreground">
        <span>low</span>
        <div className="h-2 w-24 rounded-full" style={{ background: "linear-gradient(90deg, rgba(45,212,191,0.12), #2dd4bf)" }} />
        <span>high (${max})</span>
      </div>
    </div>
  );
}
