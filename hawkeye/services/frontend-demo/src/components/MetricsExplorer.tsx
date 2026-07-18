import { useEffect, useMemo, useState } from "react";
import { Cpu, MemoryStick, Network } from "lucide-react";
import { api, type MetricPoint, type MetricSeries } from "../api";
import { censorId, censorName } from "../lib/censor";
import { DEMO_STUB, stubMetrics } from "../lib/demoData";
import { LineChart } from "./charts";

function groupSeries(points: MetricPoint[]): MetricSeries[] {
  const byRes = new Map<string, MetricSeries>();
  // Sort ascending by time so the line reads left->right.
  const sorted = [...points].sort((a, b) => (a.timestamp < b.timestamp ? -1 : 1));
  for (const p of sorted) {
    let s = byRes.get(p.resource_id);
    if (!s) {
      s = { resource_id: p.resource_id, name: p.resource_id.split("/").pop() ?? p.resource_id, points: [] };
      byRes.set(p.resource_id, s);
    }
    s.points.push({
      t: (p.timestamp || "").slice(11, 16) || p.timestamp,
      cpu: p.cpu_percent_avg,
      mem: p.memory_percent,
      net: p.network_out_bytes,
    });
  }
  return Array.from(byRes.values());
}

export function MetricsExplorer({ loading }: { loading?: boolean }) {
  const [points, setPoints] = useState<MetricPoint[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    if (DEMO_STUB) {
      setPoints(stubMetrics);
      return;
    }
    api
      .metrics(300)
      .then((d) => alive && setPoints(d.items ?? []))
      .catch((e) => alive && setErr(e instanceof Error ? e.message : String(e)));
    return () => {
      alive = false;
    };
  }, []);

  const series = useMemo(() => groupSeries(points), [points]);
  const selected = active ? series.find((s) => s.resource_id === active) ?? series[0] : series[0];

  if (err) return <div className="text-sm text-destructive">{err}</div>;
  if (loading && points.length === 0)
    return <div className="h-48 animate-pulse rounded-lg bg-muted" />;
  if (series.length === 0)
    return (
      <div className="h-48 grid place-items-center text-sm text-muted-foreground rounded-lg border border-dashed border-border">
        No telemetry ingested yet. Enable Cloud Monitoring export to populate live metrics.
      </div>
    );

  const cpuSeries = selected
    ? [{ label: "CPU %", values: selected.points.map((p) => p.cpu), color: "#2dd4bf" }]
    : [];
  const memSeries = selected
    ? [{ label: "Memory %", values: selected.points.map((p) => p.mem), color: "#7c8cf8" }]
    : [];
  const netSeries = selected
    ? [
        {
          label: "Network out (KB)",
          values: selected.points.map((p) => (p.net != null ? Math.round(p.net / 1024) : null)),
          color: "#f5b14c",
        },
      ]
    : [];
  const xLabels = selected?.points.map((p) => p.t);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">
        {series.map((s) => (
          <button
            key={s.resource_id}
            onClick={() => setActive(s.resource_id)}
            className={`px-2.5 py-1 rounded-md text-xs font-medium border transition ${
              selected?.resource_id === s.resource_id
                ? "border-primary/40 bg-primary/10 text-primary"
                : "border-border text-muted-foreground hover:text-foreground"
            }`}
            title={censorId(s.resource_id)}
          >
            {censorName(s.name)}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-foreground">
            <Cpu className="h-4 w-4 text-[#2dd4bf]" /> CPU utilization
          </div>
          <LineChart series={cpuSeries} xLabels={xLabels} emptyText="No CPU data" />
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-foreground">
            <MemoryStick className="h-4 w-4 text-[#7c8cf8]" /> Memory utilization
          </div>
          <LineChart series={memSeries} xLabels={xLabels} emptyText="No memory data" />
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex items-center gap-2 mb-3 text-sm font-medium text-foreground">
            <Network className="h-4 w-4 text-[#f5b14c]" /> Network egress
          </div>
          <LineChart series={netSeries} xLabels={xLabels} emptyText="No network data" />
        </div>
      </div>
    </div>
  );
}
