// Demo stub-data layer.
//
// The public demo dashboard is served from a shared URL. To avoid exposing
// real GCP resource names / ids / project internals, when VITE_DEMO_STUB=1 the
// dashboard renders synthetic, clearly-labelled "SAMPLE DATA" instead of the
// live API. Everything is fabricated and contains no real identifiers.
//
// This is NOT a fallback for missing data — it is an explicit opt-in demo mode
// toggled by build env so the production demo never leaks real inventory.

import type {
  DashboardSummary,
  Resource,
  Recommendation,
  Alert,
  MLPredictions,
  Graph,
  ComplianceSummary,
  SmartInsights,
  MetricPoint,
} from "../api";

export const DEMO_STUB = (import.meta.env.VITE_DEMO_STUB as string | undefined) === "1";

const SAMPLE_TYPES = ["Container", "Container", "Container", "Network", "Storage", "Database"];
const SAMPLE_REGIONS = ["us-central1", "us-east1", "europe-west1"];

function fakeId(i: number): string {
  // Deliberately non-real, clearly synthetic ids.
  return `gcp://demo/sample-project/resource-${String(i).padStart(3, "0")}`;
}

function fakeName(i: number): string {
  const adjectives = ["api", "web", "worker", "cache", "ingest", "report", "auth", "batch"];
  return `${adjectives[i % adjectives.length]}-svc-${i}`;
}

export const stubSummary: DashboardSummary = {
  resourceCount: 42,
  byType: { Container: 28, Network: 6, Storage: 4, Database: 3, Compute: 1 },
  totalMonthlyCostProjection: 1284.37,
  publicResources: 1,
  unusedResources: 5,
  recommendationCount: 11,
  totalEstimatedSavings: 412.5,
};

export const stubResources: Resource[] = Array.from({ length: 42 }).map((_, i) => {
  const type = SAMPLE_TYPES[i % SAMPLE_TYPES.length];
  const region = SAMPLE_REGIONS[i % SAMPLE_REGIONS.length];
  const cpu = type === "Container" ? Math.round((8 + (i % 7) * 4) * 10) / 10 : undefined;
  const mem = type === "Container" ? Math.round((20 + (i % 5) * 9) * 10) / 10 : undefined;
  return {
    id: fakeId(i + 1),
    name: fakeName(i + 1),
    type,
    status: i % 11 === 0 ? "PROVISIONING" : "ACTIVE",
    region,
    project_id: "sample-project",
    monthly_cost_projection: Math.round((5 + (i % 13) * 11) * 100) / 100,
    cpu_utilization_avg: cpu,
    memory_utilization_avg: mem,
    public_access: type === "Storage" && i % 17 === 0,
    encryption_status: type === "Database" ? "ENCRYPTED" : undefined,
    owner_email: "sample-owner@example.com",
  };
});

export const stubRecommendations: Recommendation[] = [
  { id: "rec-1", type: "SECURITY", resource_id: fakeId(4), title: "Restrict public access on Storage bucket", description: "Bucket is publicly accessible. Restrict via IAM unless intentionally public.", estimated_savings: 0, severity: "HIGH" },
  { id: "rec-2", type: "COST", resource_id: fakeId(12), title: "Right-size over-provisioned Cloud Run service", description: "Avg CPU < 5% over 14 days. Reduce allocated CPU/memory.", estimated_savings: 96.4, severity: "MEDIUM" },
  { id: "rec-3", type: "RELIABILITY", resource_id: fakeId(7), title: "Enable automated backups for Cloud SQL", description: "No backup configuration found. Enable PITR backups.", estimated_savings: 0, severity: "MEDIUM" },
  { id: "rec-4", type: "GOVERNANCE", resource_id: fakeId(19), title: "Add owner label & audit logging", description: "Resource has no owner label and audit logging disabled.", estimated_savings: 0, severity: "LOW" },
  { id: "rec-5", type: "PERFORMANCE", resource_id: fakeId(3), title: "High error rate detected", description: "Error rate avg > 2% over last 24h.", estimated_savings: 0, severity: "MEDIUM" },
  { id: "rec-6", type: "COST", resource_id: fakeId(22), title: "Delete orphaned disk", description: "Disk not attached to any instance for 30+ days.", estimated_savings: 38.2, severity: "LOW" },
  { id: "rec-7", type: "SECURITY", resource_id: fakeId(31), title: "Enable VPC Service Controls", description: "Sensitive service exposed outside perimeter.", estimated_savings: 0, severity: "HIGH" },
  { id: "rec-8", type: "GOVERNANCE", resource_id: fakeId(9), title: "Missing required labels", description: "env, team, cost-center labels missing.", estimated_savings: 0, severity: "LOW" },
  { id: "rec-9", type: "RELIABILITY", resource_id: fakeId(15), title: "Enable deletion protection", description: "Production database has no deletion protection.", estimated_savings: 0, severity: "MEDIUM" },
  { id: "rec-10", type: "COST", resource_id: fakeId(27), title: "Move to committed-use discount", description: "Stable baseline workload eligible for CUD.", estimated_savings: 210.0, severity: "LOW" },
  { id: "rec-11", type: "PERFORMANCE", resource_id: fakeId(5), title: "Scale-out recommendation", description: "p95 latency rising; add concurrency.", estimated_savings: 0, severity: "MEDIUM" },
];

export const stubAlerts: Alert[] = [
  { id: "alert-1", type: "LIFECYCLE_CHANGE", resource_id: fakeId(33), title: "New resource detected: resource-033", severity: "LOW", created_at: new Date(Date.now() - 3600_000).toISOString() },
  { id: "alert-2", type: "SECURITY", resource_id: fakeId(4), title: "Public exposure opened on Storage", severity: "HIGH", created_at: new Date(Date.now() - 7200_000).toISOString() },
  { id: "alert-3", type: "COST", resource_id: fakeId(12), title: "Cost spike +38% on resource-012", severity: "MEDIUM", created_at: new Date(Date.now() - 86400_000).toISOString() },
];

export const stubPredictions: MLPredictions = {
  scored: 42,
  total_resources: 42,
  anomalies: [fakeId(4)],
  failure_risks: [fakeId(15)],
  items: stubResources.slice(0, 6).map((r, i) => ({
    resource_id: r.id,
    predictable: true,
    anomaly: { score: i === 3 ? 0.82 : 0.1, is_anomaly: i === 3 },
    failure: { probability: i === 5 ? 0.71 : 0.05, is_high_risk: i === 5 },
    cost_forecast: { usual_daily: 2.1, predicted_daily: 2.4, predicted_total: 72, spike: false },
    explanation: {
      risk_score: i === 3 ? 0.82 : i === 5 ? 0.71 : 0.12,
      risk_level: i === 3 ? "HIGH" : i === 5 ? "MEDIUM" : "LOW",
      reason:
        i === 3
          ? "Public Storage bucket with no IAM restriction detected."
          : i === 5
          ? "Database missing deletion protection and backups."
          : "No significant risk signals detected — resource looks healthy.",
      drivers:
        i === 3
          ? [{ label: "Public access", contribution: 0.45, reason: "Bucket allows allUsers" }]
          : i === 5
          ? [{ label: "No backups", contribution: 0.25, reason: "Backup config disabled" }]
          : [],
    },
  })),
};

export const stubGraph: Graph = {
  edges: {
    [fakeId(1)]: [fakeId(2), fakeId(3)],
    [fakeId(2)]: [fakeId(4)],
    [fakeId(7)]: [fakeId(1)],
  },
};

export const stubCompliance: ComplianceSummary = {
  total: 42,
  score: 91.4,
  violations: 4,
  public_resources: [fakeId(4)],
  unencrypted: [],
  no_backup: [fakeId(15), fakeId(7)],
  no_audit_logging: [fakeId(19)],
};

export const stubInsights: SmartInsights = {
  insights: [
    { kind: "risk", level: "HIGH", resource_id: fakeId(4), title: "High risk: resource-004", detail: "Public Storage bucket with no IAM restriction.", blast_radius: 2 },
    { kind: "recommendation", level: "HIGH", resource_id: fakeId(31), title: "Enable VPC Service Controls", detail: "Sensitive service exposed outside perimeter.", savings: 0, blast_radius: 0 },
    { kind: "recommendation", level: "MEDIUM", resource_id: fakeId(12), title: "Right-size over-provisioned Cloud Run service", detail: "Avg CPU < 5% over 14 days.", savings: 96.4, blast_radius: 0 },
    { kind: "recommendation", level: "MEDIUM", resource_id: fakeId(7), title: "Enable automated backups for Cloud SQL", detail: "No backup configuration found.", savings: 0, blast_radius: 1 },
    { kind: "compliance", level: "MEDIUM", resource_id: null, title: "Compliance score 91.4/100", detail: "4 policy violations across 42 resources.", savings: 0, blast_radius: 0 },
  ],
  risk_ranking: stubPredictions.items.map((it) => ({
    resource_id: it.resource_id,
    risk_score: (it as any).explanation?.risk_score ?? 0,
    risk_level: (it as any).explanation?.risk_level ?? "LOW",
    reason: (it as any).explanation?.reason ?? "",
    drivers: (it as any).explanation?.drivers ?? [],
    anomaly: it.anomaly ?? { score: 0, is_anomaly: false },
    failure: it.failure ?? { probability: 0, is_high_risk: false },
  })),
  compliance: stubCompliance,
  total_estimated_savings: 412.5,
  high_risk_count: 1,
};

export const stubMetrics: MetricPoint[] = Array.from({ length: 30 }).map((_, i) => {
  const rid = fakeId((i % 6) + 1);
  const t = new Date(Date.now() - (30 - i) * 600_000).toISOString();
  const wave = Math.sin(i / 3) * 20 + 35;
  return {
    resource_id: rid,
    timestamp: t,
    cpu_percent_avg: Math.round(wave * 10) / 10,
    memory_percent: Math.round((wave + 15) * 10) / 10,
    network_out_bytes: Math.round(1024 * (50 + wave)),
  };
});

// Per-resource CPU time-series so table rows can render sparklines.
export const stubResourceMetrics: Record<string, number[]> = (() => {
  const map: Record<string, number[]> = {};
  for (let i = 0; i < 42; i++) {
    const id = fakeId(i + 1);
    const base = 10 + ((i * 7) % 60);
    const series: number[] = [];
    for (let h = 0; h < 24; h++) {
      const v = base + Math.sin(h / 3 + i) * 18 + (h % 5 === 0 ? 12 : 0);
      series.push(Math.max(1, Math.round(v * 10) / 10));
    }
    map[id] = series;
  }
  return map;
})();

// Cost heatmap: rows = top services, cols = last 7 days.
export const stubCostHeatmap = (() => {
  const rows = ["api-svc", "web-svc", "worker-svc", "cache-svc", "ingest-svc", "report-svc", "auth-svc", "batch-svc"];
  const cols = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const values = rows.map((_, r) =>
    cols.map((_, c) => Math.round(20 + ((r * 13 + c * 7) % 80) + (c >= 5 ? 15 : 0)))
  );
  return { rows, cols, values };
})();
