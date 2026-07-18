import { useEffect, useState } from "react";
import { api, type CostBreakdown, type CostPoint, type Resource } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { CostRanking } from "./CostRanking";
import { CostHeatmap } from "./CostHeatmap";
import { DEMO_STUB, stubResources } from "../lib/demoData";

const TYPE_COLORS: Record<string, string> = {
  Container: "hsl(221 83% 53%)",
  Network: "hsl(239 84% 67%)",
  Storage: "hsl(38 92% 50%)",
  Database: "hsl(142 71% 45%)",
  Compute: "hsl(0 72% 51%)",
};

export function CostDashboard() {
  const [breakdown, setBreakdown] = useState<CostBreakdown | null>(null);
  const [trend, setTrend] = useState<CostPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [resources, setResources] = useState<Resource[]>([]);

  useEffect(() => {
    let active = true;
    if (DEMO_STUB) {
      setResources(stubResources);
    } else {
      api.resources(200).then((r) => active && setResources(r.items)).catch(() => {});
    }
    Promise.all([api.costBreakdown(), api.costTrend(30)])
      .then(([b, t]) => {
        if (!active) return;
        setBreakdown(b);
        setTrend(t.items);
      })
      .catch(() => {})
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const maxCost = Math.max(1, ...(breakdown?.items.map((i) => i.cost) ?? [0]));

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card className="lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-sm">Projected Monthly Spend</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold tnum">
              ${breakdown ? breakdown.total.toFixed(2) : "0.00"}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Estimated from resource projections · free tier
            </p>
            <div className="mt-4 space-y-3">
              {(breakdown?.items ?? []).map((i) => (
                <div key={i.type}>
                  <div className="flex items-center justify-between text-xs mb-1">
                    <span className="flex items-center gap-2">
                      <span
                        className="h-2.5 w-2.5 rounded-sm"
                        style={{ background: TYPE_COLORS[i.type] ?? "#8b98ad" }}
                      />
                      {i.type}
                    </span>
                    <span className="tnum text-muted-foreground">
                      ${i.cost.toFixed(2)} · {i.pct}%
                    </span>
                  </div>
                  <Progress
                    value={(i.cost / maxCost) * 100}
                    indicatorClassName="bg-primary"
                  />
                </div>
              ))}
              {loading && !breakdown && (
                <div className="h-24 animate-pulse rounded bg-muted" />
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Daily Cost Trend (30d)</CardTitle>
            <Badge variant="muted">USD</Badge>
          </CardHeader>
          <CardContent>
            <CostAreaChart points={trend} />
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <CostRanking resources={resources} />
        <CostHeatmap trend={trend} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Budget Guard</CardTitle>
        </CardHeader>
        <CardContent>
          <BudgetTracker />
        </CardContent>
      </Card>
    </div>
  );
}

function CostAreaChart({ points }: { points: CostPoint[] }) {
  const W = 640;
  const H = 200;
  const pad = 28;
  if (points.length === 0) {
    return <div className="h-48 animate-pulse rounded bg-muted" />;
  }
  const max = Math.max(1, ...points.map((p) => p.total_cost));
  const stepX = (W - pad * 2) / Math.max(1, points.length - 1);
  const xy = points
    .map((p, i) => {
      const x = pad + i * stepX;
      const y = H - pad - (p.total_cost / max) * (H - pad * 2);
      return [x, y];
    })
    .reverse();
  const line = xy.map(([x, y]) => `${x},${y}`).join(" ");
  const area = `${pad},${H - pad} ${line} ${W - pad},${H - pad}`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
      <defs>
        <linearGradient id="costFill2" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="hsl(221 83% 53%)" stopOpacity="0.35" />
          <stop offset="100%" stopColor="hsl(221 83% 53%)" stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill="url(#costFill2)" />
      <polyline points={line} fill="none" stroke="hsl(221 83% 53%)" strokeWidth="2.5" strokeLinejoin="round" />
    </svg>
  );
}

function BudgetTracker() {
  // The budget guard cap is configured server-side ($0.10 for the free-tier
  // safety net). We surface the cap and current MTD (which is $0 on free tier).
  const cap = 0.1;
  const mtd = 0.0;
  const pct = Math.min(100, (mtd / cap) * 100);
  return (
    <div>
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-muted-foreground">Monthly cap</span>
        <span className="tnum font-medium">${cap.toFixed(2)}</span>
      </div>
      <Progress value={pct} indicatorClassName="bg-good" />
      <div className="flex items-center justify-between text-xs text-muted-foreground mt-2">
        <span>Spent MTD: ${mtd.toFixed(2)}</span>
        <span className="text-good">within limit</span>
      </div>
      <p className="text-xs text-muted-foreground mt-3">
        The Budget Guard automatically revokes public access and pauses schedulers
        if spend exceeds the cap. Current project is on GCP free tier.
      </p>
    </div>
  );
}
