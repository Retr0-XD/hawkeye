import { useEffect, useState } from "react";
import { api, type CostPoint } from "../api";

// Simple inline SVG line chart for daily cost trend (no external chart lib).
export function CostTrend() {
  const [data, setData] = useState<CostPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .costTrend(30)
      .then((r) => {
        if (alive) setData(r.items ?? []);
      })
      .catch(() => {
        if (alive) setData([]);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="text-sm font-medium mb-3">Cost Trend (30d)</div>
        <div className="h-40 animate-pulse rounded bg-muted/40" />
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="text-sm font-medium mb-3">Cost Trend (30d)</div>
        <p className="text-sm text-muted-foreground">
          No billing data. Enable Cloud Billing Export → BigQuery (dataset <code>hawkeye</code>, table{" "}
          <code>billing</code>) to populate cost trends. The platform is currently within the $0 free tier.
        </p>
      </div>
    );
  }

  const W = 480;
  const H = 160;
  const pad = 24;
  const max = Math.max(...data.map((d) => d.total_cost), 0.0001);
  const pts = data
    .slice()
    .reverse()
    .map((d, i) => {
      const x = pad + (i * (W - 2 * pad)) / Math.max(1, data.length - 1);
      const y = H - pad - (d.total_cost / max) * (H - 2 * pad);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    });
  const line = pts.join(" ");
  const area = `${pad},${H - pad} ${line} ${W - pad},${H - pad}`;

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-sm font-semibold text-foreground">Cost Trend (30d)</h2>
        <span className="text-xs text-muted-foreground">daily total · USD</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        <defs>
          <linearGradient id="costFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity="0.35" />
            <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity="0" />
          </linearGradient>
        </defs>
        <polygon points={area} fill="url(#costFill)" />
        <polyline points={line} fill="none" stroke="hsl(var(--primary))" strokeWidth="2.5" strokeLinejoin="round" />
        {data.length > 0 && (
          <text x={pad} y={H - 6} fill="hsl(var(--muted-foreground))" fontSize="10">
            {data[data.length - 1].date}
          </text>
        )}
        {data.length > 0 && (
          <text x={W - pad} y={H - 6} fill="hsl(var(--muted-foreground))" fontSize="10" textAnchor="end">
            {data[0].date}
          </text>
        )}
      </svg>
    </div>
  );
}
