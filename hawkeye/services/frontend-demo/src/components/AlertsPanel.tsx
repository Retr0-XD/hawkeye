import type { Alert } from "../api";
import { censorId } from "../lib/censor";

export function AlertsPanel({ alerts, loading }: { alerts: Alert[]; loading: boolean }) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="px-5 py-4 border-b border-border text-sm font-semibold text-foreground flex items-center justify-between">
        <span>Lifecycle Alerts</span>
        <span className="text-xs text-muted-foreground tnum">{alerts.length} items</span>
      </div>
      <div className="p-3 space-y-2 max-h-72 overflow-y-auto">
        {loading && alerts.length === 0 && <div className="h-24 animate-pulse rounded bg-muted" />}
        {!loading && alerts.length === 0 && (
          <p className="text-sm text-muted-foreground px-2 py-3">
            No lifecycle alerts. The Processing service emits alerts when resources are created, changed, or deleted.
          </p>
        )}
        {alerts.map((a) => (
          <div key={a.id} className="rounded-xl border border-border bg-muted/30 p-3 flex items-start gap-3">
            <span className="mt-1.5 h-2 w-2 rounded-full bg-primary shrink-0" />
            <div className="min-w-0">
              <div className="text-sm text-foreground">{a.title ?? a.type ?? "Alert"}</div>
              {a.description && <p className="text-xs text-muted-foreground mt-0.5">{a.description}</p>}
              <div className="text-xs text-muted-foreground mt-1 font-mono truncate">{censorId(a.resource_id ?? "")}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
