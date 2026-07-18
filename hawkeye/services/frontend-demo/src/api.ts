// Thin typed client for the Hawkeye REST API.
// Base URL is configurable via VITE_API_BASE (defaults to the deployed demo API).
const API_BASE =
  (import.meta.env.VITE_API_BASE as string | undefined) ||
  "https://hawkeye-api-78803747777.us-central1.run.app";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API ${path} failed: ${res.status} ${res.statusText}`);
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
  total: number;
  score: number;
  violations: number;
  public_resources: string[];
  unencrypted: string[];
  no_backup: string[];
  no_audit_logging: string[];
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
