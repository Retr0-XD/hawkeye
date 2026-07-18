import { useEffect, useState } from "react";
import { X, ShieldAlert, Activity, DollarSign, Network, Database, Boxes } from "lucide-react";
import { api, type Resource, type MLPredictions } from "../api";
import { censorId, censorName, censorEmail } from "../lib/censor";
import { consoleUrlForResource } from "../lib/console";
import { DEMO_STUB } from "../lib/demoData";

function Field({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] uppercase tracking-wider text-muted-foreground">{label}</span>
      <span className={`text-sm text-foreground ${mono ? "font-mono" : ""}`}>{value}</span>
    </div>
  );
}

function RiskMeter({ score, level }: { score: number; level: string }) {
  const pct = Math.max(0, Math.min(100, score * 100));
  const color = level === "HIGH" ? "bg-bad" : level === "MEDIUM" ? "bg-warn" : "bg-good";
  return (
    <div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>Explainable risk</span>
        <span className="text-foreground tnum">{pct.toFixed(0)}% · {level}</span>
      </div>
      <div className="mt-1 h-2 rounded bg-muted overflow-hidden">
        <div className={`h-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export function ResourceDetail({
  resourceId,
  onClose,
  predByResource,
  localResource,
}: {
  resourceId: string;
  onClose: () => void;
  predByResource: Map<string, MLPredictions["items"][number]>;
  localResource?: Resource | null;
}) {
  const [detail, setDetail] = useState<Resource | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError(null);
    // In demo (stub) mode the resource only exists client-side, so use the
    // passed-in local resource instead of calling the backend (which 404s).
    if (DEMO_STUB && localResource) {
      setDetail(localResource);
      setLoading(false);
      return;
    }
    api
      .resourceDetail(resourceId)
      .then((d) => alive && setDetail(d))
      .catch((e) => alive && setError(e instanceof Error ? e.message : String(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [resourceId, localResource]);

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const pred = predByResource.get(resourceId);
  const exp = (pred as unknown as { explanation?: any })?.explanation;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-border bg-card shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 flex items-center justify-between border-b border-border bg-card px-5 py-4">
          <div className="min-w-0">
            <div className="text-[11px] uppercase tracking-wider text-muted-foreground">Resource Detail</div>
            <div className="font-mono text-sm text-foreground truncate" title={resourceId}>
              {censorId(resourceId)}
            </div>
          </div>
          <button
            onClick={onClose}
            className="h-8 w-8 grid place-items-center rounded-lg text-muted-foreground hover:bg-muted hover:text-foreground"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {loading && <div className="h-40 animate-pulse rounded-lg bg-muted" />}
          {error && <div className="text-sm text-destructive">{error}</div>}

          {detail && (
            <>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4">
                <Field label="Name" value={censorName(detail.name)} />
                <Field label="Type" value={detail.type ?? "—"} />
                <Field label="Status" value={detail.status ?? "—"} />
                <Field label="Region" value={detail.region ?? "—"} />
                <Field label="Project" value={censorId(`gcp://x/${detail.project_id ?? "—"}`).split("/").pop()} />
                <Field
                  label="Owner"
                  value={censorEmail((detail as any).owner_email)}
                />
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <DollarSign className="h-3 w-3" /> Monthly cost
                  </div>
                  <div className="text-lg font-semibold text-foreground tnum">
                    ${(detail.monthly_cost_projection ?? 0).toFixed(2)}
                  </div>
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Activity className="h-3 w-3" /> CPU avg
                  </div>
                  {detail.cpu_utilization_avg != null ? (
                    <div className="text-lg font-semibold text-foreground tnum">
                      {detail.cpu_utilization_avg}%
                    </div>
                  ) : (
                    <div className="text-xs font-medium text-muted-foreground">No telemetry</div>
                  )}
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Boxes className="h-3 w-3" /> Memory avg
                  </div>
                  {detail.memory_utilization_avg != null ? (
                    <div className="text-lg font-semibold text-foreground tnum">
                      {detail.memory_utilization_avg}%
                    </div>
                  ) : (
                    <div className="text-xs font-medium text-muted-foreground">No telemetry</div>
                  )}
                </div>
                <div className="rounded-lg border border-border bg-muted/30 p-3">
                  <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                    <ShieldAlert className="h-3 w-3" /> Public
                  </div>
                  <div className={`text-lg font-semibold tnum ${detail.public_access ? "text-bad" : "text-good"}`}>
                    {detail.public_access ? "Yes" : "No"}
                  </div>
                </div>
              </div>

              {detail.cpu_utilization_avg == null && detail.memory_utilization_avg == null && (
                <div className="rounded-lg border border-dashed border-border bg-muted/20 px-3 py-2 text-[11px] text-muted-foreground">
                  No live telemetry ingested yet. Enable Cloud Monitoring export (and Billing
                  export to BigQuery) to populate CPU, memory, and cost trends.
                </div>
              )}

              {exp && (
                <div className="rounded-xl border border-border bg-muted/20 p-4 space-y-3">
                  <RiskMeter score={exp.risk_score} level={exp.risk_level} />
                  <div>
                    <div className="text-[11px] font-medium text-muted-foreground">Explanation</div>
                    <p className="text-sm text-foreground">{exp.reason}</p>
                  </div>
                  {exp.drivers?.length > 0 && (
                    <div className="space-y-1">
                      <div className="text-[11px] font-medium text-muted-foreground">Contributing factors</div>
                      {exp.drivers.map((d: any, i: number) => (
                        <div key={i} className="flex items-start gap-2 text-xs">
                          <span className="mt-1 h-1.5 w-1.5 rounded-full bg-primary shrink-0" />
                          <span className="text-foreground">
                            {d.label} <span className="text-muted-foreground">— {d.reason}</span>
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="flex flex-wrap gap-2">
                <a
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-primary hover:bg-muted"
                  href={consoleUrlForResource(detail.id, detail.type, detail.project_id)}
                  target="_blank"
                  rel="noreferrer"
                >
                  <Network className="h-3 w-3" /> Open in Console
                </a>
                {detail.type === "Database" && (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground">
                    <Database className="h-3 w-3" /> Encryption: {detail.encryption_status ?? "unknown"}
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
