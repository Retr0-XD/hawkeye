import type { Resource, MLPredictions } from "../api";

const TYPE_COLORS: Record<string, string> = {
  Container: "bg-aurora/15 text-aurora",
  Network: "bg-indigo/15 text-indigo",
  Storage: "bg-warn/15 text-warn",
  Database: "bg-good/15 text-good",
  Compute: "bg-bad/15 text-bad",
};

function Badge({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ${className ?? "bg-panel2 text-muted"}`}>
      {children}
    </span>
  );
}

export function ResourceGrid({
  resources,
  predByResource,
  loading,
}: {
  resources: Resource[];
  predByResource: Map<string, MLPredictions["items"][number]>;
  loading: boolean;
}) {
  if (loading && resources.length === 0) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-36 rounded-2xl surface animate-pulse" />
        ))}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-ink">Resource Inventory</h2>
        <span className="text-xs text-muted tnum">{resources.length} resources</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        {resources.map((r) => {
          const pred = predByResource.get(r.id);
          const anomaly = pred?.anomaly?.is_anomaly;
          const risk = pred?.failure?.is_high_risk;
          const name = r.name ?? r.id.split("/").pop() ?? r.id;
          const statusColor = r.status === "ACTIVE" ? "bg-good" : "bg-muted";
          return (
            <div
              key={r.id}
              className={`surface rounded-2xl p-4 transition hover:border-aurora/40 ${
                anomaly ? "border-bad/40" : risk ? "border-warn/40" : ""
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <div className="font-semibold text-ink truncate" title={name}>
                    {name}
                  </div>
                  <div className="text-[11px] text-muted font-mono truncate mt-0.5">{r.id}</div>
                </div>
                <span className={`mt-1 h-2 w-2 rounded-full shrink-0 ${statusColor} ${r.status === "ACTIVE" ? "live-dot" : ""}`} />
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <Badge className={TYPE_COLORS[r.type ?? ""]}>{r.type ?? "—"}</Badge>
                {r.region && <Badge>{r.region}</Badge>}
                {r.public_access && <Badge className="bg-warn/15 text-warn">public</Badge>}
              </div>
              <div className="mt-3 flex items-center justify-between text-xs">
                <span className="text-muted">est. cost</span>
                <span className="text-ink font-medium tnum">${(r.monthly_cost_projection ?? 0).toFixed(2)}/mo</span>
              </div>
              {(anomaly || risk) && (
                <div className="mt-2">
                  <Badge className={anomaly ? "bg-bad/15 text-bad" : "bg-warn/15 text-warn"}>
                    {anomaly ? "⚠ anomaly" : "⚠ risk"}
                  </Badge>
                </div>
              )}
            </div>
          );
        })}
        {resources.length === 0 && (
          <div className="col-span-full surface rounded-2xl p-8 text-center text-muted">No resources found.</div>
        )}
      </div>
    </div>
  );
}
