import type { Alert, Recommendation } from "../api";

type Item = {
  kind: "alert" | "recommendation";
  title: string;
  sub: string;
  at?: string;
  tone: string;
};

export function ActivityTimeline({
  alerts,
  recommendations,
}: {
  alerts: Alert[];
  recommendations: Recommendation[];
}) {
  const items: Item[] = [
    ...alerts.map((a) => ({
      kind: "alert" as const,
      title: a.title ?? a.type ?? "Alert",
      sub: (a.resource_id ?? "").split("/").pop() ?? "",
      at: a.created_at,
      tone: "text-warn",
    })),
    ...recommendations.map((r) => ({
      kind: "recommendation" as const,
      title: r.title ?? r.type ?? "Recommendation",
      sub: (r.resource_id ?? "").split("/").pop() ?? "",
      at: undefined,
      tone: "text-aurora",
    })),
  ].slice(0, 8);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <h2 className="text-sm font-semibold text-foreground mb-4">Recent Activity</h2>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">No recent activity. Alerts and recommendations will appear here.</p>
      ) : (
        <ol className="relative border-l border-border ml-2 space-y-4">
          {items.map((it, i) => (
            <li key={i} className="ml-4">
              <span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${it.kind === "alert" ? "bg-warn" : "bg-primary"}`} />
              <div className="text-sm text-foreground">{it.title}</div>
              <div className="text-[11px] text-muted-foreground font-mono truncate">{it.sub}</div>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
