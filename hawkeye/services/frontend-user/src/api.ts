// API client for the Hawkeye user console.
// Combines the public dashboard API (shared with the demo) and the
// authenticated user endpoints (approve/reject recommendations).
const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "https://hawkeye-api-78803747777.us-central1.run.app";

import { getStoredToken } from "./auth";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

async function authed<T>(path: string, method: string = "GET"): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (res.status === 401) {
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status}`);
  }
  return (await res.json()) as T;
}

export interface Resource {
  id: string;
  name?: string;
  type?: string;
  status?: string;
  region?: string;
  project_id?: string;
  created_at?: string;
  monthly_cost_projection?: number;
  cpu_utilization_avg?: number;
  memory_utilization_avg?: number;
  public_access?: boolean;
  encryption_status?: string;
  owner_email?: string;
}

export interface Recommendation {
  id: string;
  type?: string;
  resource_id?: string;
  title?: string;
  description?: string;
  estimated_savings?: number;
  severity?: string;
  status?: string;
  [key: string]: unknown;
}

export interface Alert {
  id: string;
  type?: string;
  resource_id?: string;
  title?: string;
  description?: string;
  severity?: string;
  created_at?: string;
  [key: string]: unknown;
}

export interface Graph {
  edges?: Record<string, string[]>;
  [key: string]: unknown;
}

export interface DashboardSummary {
  resourceCount: number;
  byType: Record<string, number>;
  totalMonthlyCostProjection: number;
  publicResources: number;
  unusedResources: number;
  recommendationCount: number;
  totalEstimatedSavings: number;
}

export interface MLPrediction {
  resource_id: string;
  predictable: boolean;
  features?: Record<string, number>;
  anomaly?: { score: number; is_anomaly: boolean };
  failure?: { probability: number; is_high_risk: boolean };
  cost_forecast?: {
    usual_daily: number;
    predicted_daily: number;
    predicted_total: number;
    spike: boolean;
  } | null;
}

export interface MLPredictions {
  scored: number;
  total_resources: number;
  anomalies: string[];
  failure_risks: string[];
  items: MLPrediction[];
}

export interface CostPoint {
  date: string;
  total_cost: number;
}

export interface CostBreakdownItem {
  type: string;
  cost: number;
  pct: number;
}

export interface CostBreakdown {
  total: number;
  items: CostBreakdownItem[];
}

export interface ComplianceSummary {
  total?: number;
  score: number;
  violations: number;
  public_resources?: string[];
  unencrypted?: string[];
  no_backup?: string[];
  no_audit_logging?: string[];
  public_iam_roles?: string[];
}

export interface InsightDriver {
  label: string;
  contribution: number;
  reason: string;
}

export interface InsightItem {
  kind: "risk" | "recommendation" | "compliance";
  level: string;
  resource_id: string | null;
  title: string;
  detail: string;
  savings?: number;
  drivers?: InsightDriver[];
  blast_radius?: number;
}

export interface RiskRankingItem {
  resource_id: string;
  risk_score: number;
  risk_level: string;
  reason: string;
  drivers: InsightDriver[];
  anomaly: { score: number; is_anomaly: boolean };
  failure: { probability: number; is_high_risk: boolean };
}

export interface SmartInsights {
  insights: InsightItem[];
  risk_ranking: RiskRankingItem[];
  compliance: ComplianceSummary;
  total_estimated_savings: number;
  high_risk_count: number;
}

export interface MetricPoint {
  resource_id: string;
  timestamp: string;
  cpu_percent_avg: number | null;
  memory_percent: number | null;
  network_out_bytes: number | null;
}

export interface MetricSeries {
  resource_id: string;
  name: string;
  points: { t: string; cpu: number | null; mem: number | null; net: number | null }[];
}

export const api = {
  dashboard: () => get<DashboardSummary>("/api/dashboard"),
  resources: (limit = 100) => get<{ items: Resource[] }>(`/api/resources?limit=${limit}`),
  resourceDetail: (id: string) => get<Resource>(`/api/resources/${encodeURIComponent(id)}`),
  recommendations: () => get<{ items: Recommendation[]; totalEstimatedSavings: number }>("/api/recommendations"),
  alerts: () => get<{ items: Alert[] }>("/api/alerts"),
  graph: () => get<Graph>("/api/graph"),
  predictions: () => get<MLPredictions>("/api/predictions"),
  insights: () => get<SmartInsights>("/api/insights"),
  costTrend: (days = 30) => get<{ items: CostPoint[] }>(`/api/cost-trend?days=${days}`),
  costBreakdown: () => get<CostBreakdown>("/api/cost-breakdown"),
  compliance: () => get<ComplianceSummary>("/api/compliance"),
  metrics: (limit = 200) => get<{ items: MetricPoint[] }>(`/api/metrics?limit=${limit}`),
};

export interface MeResponse {
  email: string;
  name?: string;
  picture?: string;
  sub?: string;
  created_at?: string;
  last_login?: string;
}

export interface UserRecommendation {
  id: string;
  title?: string;
  description?: string;
  type?: string;
  severity?: string;
  estimated_savings?: number;
  resource_id?: string;
  approval?: { status?: string; by?: string; at?: string };
}

export const userApi = {
  me: () => authed<MeResponse>("/api/user/me"),
  recommendations: () => authed<{ items: UserRecommendation[]; user: string }>("/api/user/recommendations"),
  approve: (id: string) => authed(`/api/user/recommendations/${id}/approve`, "POST"),
  reject: (id: string) => authed(`/api/user/recommendations/${id}/reject`, "POST"),
};

// Per-user GCP reads: the user's OWN projects/resources. The user connects
// their own GCP via a service-account key (stored encrypted server-side), so
// no restricted OAuth scope is needed. The id token authorizes the request.
async function gcpUser<T>(path: string, method: string = "GET", body?: unknown): Promise<T> {
  const token = getStoredToken();
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      Accept: "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { "Content-Type": "application/json" } : {}),
    },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 401) throw new Error("unauthorized");
  if (res.status === 400) throw new Error("connect-required");
  if (!res.ok) throw new Error(`GCP API ${path} failed: ${res.status}`);
  return (await res.json()) as T;
}

export interface GcpProject {
  projectId: string;
  name?: string;
  projectNumber?: string;
  state?: string;
}

export interface GcpResource {
  id: string;
  name?: string;
  type?: string;
  project_id?: string;
  region?: string | null;
  status?: string;
  assetType?: string;
}

export const gcpUserApi = {
  status: () => gcpUser<{ connected: boolean }>("/api/user/gcp/status"),
  connect: (serviceAccountJson: string) =>
    gcpUser<{ connected: boolean; project_id?: string; client_email?: string }>(
      "/api/user/gcp/connect",
      "POST",
      { serviceAccountJson }
    ),
  disconnect: () => gcpUser<{ connected: boolean }>("/api/user/gcp/connect", "DELETE"),
  projects: () => gcpUser<{ items: GcpProject[]; user: string; mode: string }>("/api/user/gcp/projects"),
  resources: (projectId: string) =>
    gcpUser<{ items: GcpResource[]; projectId: string; mode: string }>(
      `/api/user/gcp/resources?projectId=${encodeURIComponent(projectId)}`
    ),
  compliance: (projectId: string) =>
    gcpUser<{ project_id: string; score: number; violations: number; public_iam_roles: string[] }>(
      `/api/user/gcp/compliance?projectId=${encodeURIComponent(projectId)}`
    ),
};
