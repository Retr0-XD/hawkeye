import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

// Internal operations view. The platform's services are deployed as separate
// Cloud Run services; this panel is a read-only registry for operators.
const SERVICES = [
  { name: "ingestion", role: "GCP resource/billing/metrics/audit collection", url: "https://hawkeye-ingestion-cxhx2c65ea-uc.a.run.app" },
  { name: "processing", role: "Correlation, graph, recommendations", url: "https://hawkeye-processing-78803747777.us-central1.run.app" },
  { name: "api", role: "REST query API", url: "https://hawkeye-api-78803747777.us-central1.run.app" },
  { name: "ml", role: "Anomaly / failure / cost ML", url: "https://hawkeye-ml-78803747777.us-central1.run.app" },
  { name: "budget-guard", role: "Free-tier spend safety net", url: "https://hawkeye-budget-guard-78803747777.us-central1.run.app" },
  { name: "automation", role: "Approval-driven remediation", url: "https://hawkeye-automation-78803747777.us-central1.run.app" },
  { name: "frontend-demo", role: "Public demo dashboard", url: "https://hawkeye-frontend-demo-78803747777.us-central1.run.app" },
  { name: "frontend-user", role: "Authenticated user console", url: "https://hawkeye-frontend-user-78803747777.us-central1.run.app" },
];

// In the public demo we must not leak internal service URLs. Show only the
// service names + roles (no clickable endpoints). The full registry with live
// URLs is available in the authenticated user console.
function maskUrl(url: string): string {
  const host = url.replace("https://", "");
  const at = host.indexOf(".");
  const head = at > 0 ? host.slice(0, Math.min(6, at)) : host.slice(0, 6);
  return `${head}***.run.app`;
}

export function AdminPanel({ censored = false }: { censored?: boolean }) {
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Service Registry</CardTitle>
        </CardHeader>
        <CardContent>
          {censored && (
            <div className="mb-3 rounded-lg border border-warn/30 bg-warn/5 px-3 py-2 text-xs text-warn">
              Endpoints are hidden in the public demo. Sign in to the User Console to see live service URLs.
            </div>
          )}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {SERVICES.map((s) => (
              <div
                key={s.name}
                className="flex items-start justify-between gap-3 rounded-lg border border-border bg-muted/30 p-3"
              >
                <div className="min-w-0">
                  <div className="font-mono text-sm text-foreground">{s.name}</div>
                  <div className="text-xs text-muted-foreground mt-0.5">{s.role}</div>
                  {censored ? (
                    <span className="text-[11px] text-muted-foreground/70 break-all">
                      {maskUrl(s.url)}
                    </span>
                  ) : (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-[11px] text-primary hover:underline break-all"
                    >
                      {s.url.replace("https://", "")}
                    </a>
                  )}
                </div>
                <Badge variant="success">live</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Pipeline</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <Badge variant="muted">Ingestion</Badge>
            <span>→</span>
            <Badge variant="muted">Pub/Sub</Badge>
            <span>→</span>
            <Badge variant="muted">Processing</Badge>
            <span>→</span>
            <Badge variant="muted">Firestore · BigQuery</Badge>
            <span>→</span>
            <Badge variant="muted">API</Badge>
            <span>→</span>
            <Badge variant="muted">ML · Automation</Badge>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            Schedulers run every 5 minutes (ingestion-tick, processing-tick,
            budget-guard-tick) and automation every 10 minutes. All services
            scale to zero except the two frontends (min-instances=1 for warm loads).
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
