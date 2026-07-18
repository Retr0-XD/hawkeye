import { useCallback, useEffect, useMemo, useState } from "react";
import { LayoutDashboard, Boxes, Brain, Network, DollarSign, ShieldCheck, Settings2, Sparkles, Activity } from "lucide-react";
import { api, type DashboardSummary, type Resource, type Recommendation, type Alert, type MLPredictions, type Graph, type ComplianceSummary, type SmartInsights as Insights } from "./api";
import { ResourceTable } from "./components/ResourceTable";
import { RecommendationsPanel } from "./components/RecommendationsPanel";
import { AlertsPanel } from "./components/AlertsPanel";
import { DependencyGraph } from "./components/DependencyGraph";
import { MLPanel } from "./components/MLPanel";
import { CostTrend } from "./components/CostTrend";
import { DonutChart } from "./components/DonutChart";
import { PipelineStatus } from "./components/PipelineStatus";
import { ActivityTimeline } from "./components/ActivityTimeline";
import { CostDashboard } from "./components/CostDashboard";
import { ComplianceDashboard } from "./components/ComplianceDashboard";
import { AdminPanel } from "./components/AdminPanel";
import { SmartInsights } from "./components/SmartInsights";
import { ResourceDetail } from "./components/ResourceDetail";
import { MetricsExplorer } from "./components/MetricsExplorer";
import { RiskDistribution, RecommendationBreakdown, ComplianceMiniCard } from "./components/RiskDistribution";
import { FleetHealth } from "./components/FleetHealth";
import { SmartNarratives } from "./components/SmartNarratives";
import { CostRanking } from "./components/CostRanking";
import { CostHeatmap } from "./components/CostHeatmap";
import { Button } from "@/components/ui/button";
import { DEMO_STUB, stubSummary, stubResources, stubRecommendations, stubAlerts, stubPredictions, stubGraph, stubCompliance, stubInsights, stubResourceMetrics, stubCostHeatmap } from "./lib/demoData";

type Tab = "overview" | "resources" | "cost" | "ml" | "graph" | "compliance" | "admin" | "insights";

const TYPE_COLORS: Record<string, string> = {
  Container: "#2dd4bf",
  Network: "#7c8cf8",
  Storage: "#f5b14c",
  Database: "#3ddc97",
  Compute: "#ff6b81",
};

const NAV: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "overview", label: "Overview", icon: <LayoutDashboard className="h-4 w-4" /> },
  { id: "resources", label: "Resources", icon: <Boxes className="h-4 w-4" /> },
  { id: "insights", label: "Smart Insights", icon: <Sparkles className="h-4 w-4" /> },
  { id: "cost", label: "Cost", icon: <DollarSign className="h-4 w-4" /> },
  { id: "ml", label: "ML Insights", icon: <Brain className="h-4 w-4" /> },
  { id: "graph", label: "Topology", icon: <Network className="h-4 w-4" /> },
  { id: "compliance", label: "Compliance", icon: <ShieldCheck className="h-4 w-4" /> },
  { id: "admin", label: "Admin", icon: <Settings2 className="h-4 w-4" /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [resources, setResources] = useState<Resource[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [predictions, setPredictions] = useState<MLPredictions | null>(null);
  const [graph, setGraph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      if (DEMO_STUB) {
        // Public demo mode: render synthetic, non-revealing SAMPLE DATA so the
        // shared URL never leaks real GCP resource names / ids / project info.
        await new Promise((r) => setTimeout(r, 300));
        setSummary(stubSummary);
        setResources(stubResources);
        setRecommendations(stubRecommendations);
        setAlerts(stubAlerts);
        setPredictions(stubPredictions);
        setGraph(stubGraph);
        setCompliance(stubCompliance);
        setInsights(stubInsights);
        setLastUpdated(new Date());
        return;
      }
      const [s, r, rec, a, p, g, c, ins] = await Promise.all([
        api.dashboard(),
        api.resources(200),
        api.recommendations(),
        api.alerts(),
        api.predictions(),
        api.graph(),
        api.compliance(),
        api.insights(),
      ]);
      setSummary(s);
      setResources(r.items);
      setRecommendations(rec.items);
      setAlerts(a.items);
      setPredictions(p);
      setGraph(g);
      setCompliance(c);
      setInsights(ins);
      setLastUpdated(new Date());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 60_000);
    return () => clearInterval(id);
  }, [load]);

  const predByResource = useMemo(() => {
    const m = new Map<string, MLPredictions["items"][number]>();
    predictions?.items.forEach((it) => m.set(it.resource_id, it));
    return m;
  }, [predictions]);

  const donutData = useMemo(() => {
    const byType = summary?.byType ?? {};
    return Object.entries(byType).map(([label, value]) => ({
      label,
      value,
      color: TYPE_COLORS[label] ?? "#8b98ad",
    }));
  }, [summary]);

  const anomalies = predictions?.anomalies.length ?? 0;
  const failures = predictions?.failure_risks.length ?? 0;

  return (
    <div className="min-h-full flex app-bg">
      {/* Sidebar */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-card/60 backdrop-blur sticky top-0 h-screen">
        <div className="px-5 py-5 flex items-center gap-3 border-b border-border">
          <img
            src="/hawkeye-logo.png"
            alt="Hawkeye"
            className="h-9 w-9 rounded-lg object-contain"
          />
          <div>
            <div className="font-bold tracking-tight leading-none">Hawkeye</div>
            <div className="text-[10px] text-muted-foreground mt-0.5">Resource Intelligence</div>
          </div>
        </div>
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map((n) => (
            <button
              key={n.id}
              onClick={() => setTab(n.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition ${
                tab === n.id
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent"
              }`}
            >
              <span className="w-5 grid place-items-center">{n.icon}</span>
              {n.label}
            </button>
          ))}
        </nav>
        <div className="px-4 py-4 border-t border-border text-[11px] text-muted-foreground space-y-1">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-good live-dot" /> pipeline live
          </div>
          <div className="tnum">{lastUpdated ? `synced ${lastUpdated.toLocaleTimeString()}` : "syncing…"}</div>
          <a
            className="block text-primary hover:underline pt-1"
            href="https://hawkeye-frontend-user-78803747777.us-central1.run.app"
          >
            → User Console
          </a>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Command bar */}
        <header className="sticky top-0 z-10 border-b border-border bg-background/80 backdrop-blur">
          <div className="px-5 py-3 flex items-center justify-between gap-4">
            <div>
              <h1 className="text-lg font-bold tracking-tight capitalize">{tab}</h1>
              <p className="text-xs text-muted-foreground">
                {tab === "overview" && "Fleet health, cost & ML signals at a glance"}
                {tab === "resources" && "Inventory across your GCP project"}
                {tab === "cost" && "Spend breakdown, trend & budget guard"}
                {tab === "ml" && "Anomaly, failure & cost predictions"}
                {tab === "graph" && "Resource dependency topology"}
                {tab === "compliance" && "Security posture & compliance score"}
                {tab === "admin" && "Service registry & pipeline status"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <span className="hidden sm:flex items-center gap-1.5 text-xs text-good">
                <span className="h-2 w-2 rounded-full bg-good live-dot" /> live
              </span>
              <Button variant="outline" size="sm" onClick={() => void load()}>
                {loading ? "Refreshing…" : "↻ Refresh"}
              </Button>
            </div>
          </div>
          {/* Mobile nav */}
          <nav className="md:hidden flex gap-1 px-3 pb-2 overflow-x-auto">
            {NAV.map((n) => (
              <button
                key={n.id}
                onClick={() => setTab(n.id)}
                className={`px-3 py-1.5 rounded-lg text-sm whitespace-nowrap flex items-center gap-1.5 ${
                  tab === n.id ? "bg-primary/10 text-primary" : "text-muted-foreground"
                }`}
              >
                {n.icon}
                {n.label}
              </button>
            ))}
          </nav>
        </header>

        <main className="flex-1 px-5 py-6 max-w-[1400px] w-full mx-auto">
          {DEMO_STUB && (
            <div className="mb-4 flex items-center gap-2 rounded-lg border border-warn/40 bg-warn/10 px-4 py-2 text-xs text-warn">
              <span className="font-semibold">SAMPLE DATA</span>
              <span className="text-muted-foreground">
                Demo mode — synthetic, non-real data. No actual GCP resources are shown.
              </span>
            </div>
          )}
          {error && (
            <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              Failed to load data: {error}
            </div>
          )}

          {tab === "overview" && (
            <div className="space-y-6">
              <FleetHealth summary={summary} predictions={predictions} />

              <SmartNarratives
                summary={summary}
                predictions={predictions}
                recommendations={recommendations}
                compliance={compliance}
              />

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="rounded-xl border border-border bg-card p-5 elevate">
                  <h2 className="text-sm font-semibold text-foreground mb-4">Resources by Type</h2>
                  {donutData.length > 0 ? (
                    <DonutChart data={donutData} />
                  ) : (
                    <div className="h-40 animate-pulse rounded bg-muted" />
                  )}
                </div>
                <div className="lg:col-span-2">
                  <CostTrend />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <CostRanking resources={resources} />
                <CostHeatmap
                  rows={DEMO_STUB ? stubCostHeatmap.rows : []}
                  cols={DEMO_STUB ? stubCostHeatmap.cols : []}
                  values={DEMO_STUB ? stubCostHeatmap.values : []}
                />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <RiskDistribution predictions={predictions} />
                <RecommendationBreakdown recommendations={recommendations} />
                <ComplianceMiniCard
                  score={compliance?.score ?? null}
                  violations={compliance?.violations ?? 0}
                  total={compliance?.total ?? 0}
                />
              </div>

              <div className="rounded-xl border border-border bg-card p-5 elevate">
                <div className="flex items-center gap-2 mb-4">
                  <Activity className="h-4 w-4 text-primary" />
                  <h2 className="text-sm font-semibold text-foreground">Live Metrics Explorer</h2>
                </div>
                <MetricsExplorer loading={loading} />
              </div>

              <PipelineStatus />

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="lg:col-span-2">
                  <ResourceTable
                    resources={resources}
                    predByResource={predByResource}
                    loading={loading}
                    onOpen={setDetailId}
                    metricSeries={DEMO_STUB ? stubResourceMetrics : undefined}
                  />
                </div>
                <ComplianceMini data={compliance} onOpen={() => setTab("compliance")} />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <RecommendationsPanel recommendations={recommendations} loading={loading} />
                <AlertsPanel alerts={alerts} loading={loading} />
              </div>

              <ActivityTimeline alerts={alerts} recommendations={recommendations} />

              {(anomalies > 0 || failures > 0) && (
                <div className="rounded-xl border border-warn/30 p-5 bg-warn/5">
                  <h2 className="text-sm font-semibold text-warn mb-2">Attention Required</h2>
                  <p className="text-sm text-muted-foreground">
                    ML detected <span className="font-semibold text-bad tnum">{anomalies}</span> anomal
                    {anomalies === 1 ? "y" : "ies"} and{" "}
                    <span className="font-semibold text-warn tnum">{failures}</span> failure risk
                    {failures === 1 ? "" : "s"}. Open the ML Insights tab for detail.
                  </p>
                </div>
              )}
            </div>
          )}

          {tab === "resources" && (
            <ResourceTable resources={resources} predByResource={predByResource} loading={loading} onOpen={setDetailId} />
          )}

          {tab === "cost" && <CostDashboard />}

          {tab === "ml" && <MLPanel predictions={predictions} loading={loading} />}

          {tab === "graph" && <DependencyGraph graph={graph} loading={loading} />}

          {tab === "insights" && (
            <SmartInsights insights={insights} loading={loading} onOpen={setDetailId} />
          )}

          {tab === "compliance" && <ComplianceDashboard />}

          {tab === "admin" && <AdminPanel censored={DEMO_STUB} />}
        </main>
      </div>

      {detailId && (
        <ResourceDetail
          resourceId={detailId}
          onClose={() => setDetailId(null)}
          predByResource={predByResource}
          localResource={DEMO_STUB ? resources.find((r) => r.id === detailId) ?? null : undefined}
        />
      )}
    </div>
  );
}

function ComplianceMini({ data, onOpen }: { data: ComplianceSummary | null; onOpen: () => void }) {
  const score = data?.score ?? 100;
  const color = score >= 90 ? "text-good" : score >= 70 ? "text-warn" : "text-bad";
  const ring = score >= 90 ? "stroke-good" : score >= 70 ? "stroke-warn" : "stroke-bad";
  const R = 34;
  const C = 2 * Math.PI * R;
  return (
    <div className="surface rounded-2xl p-5 flex flex-col">
      <h2 className="text-sm font-semibold text-foreground mb-4">Compliance</h2>
      <div className="flex items-center gap-4">
        <svg width="84" height="84" viewBox="0 0 84 84" className="-rotate-90">
          <circle cx="42" cy="42" r={R} fill="none" stroke="hsl(var(--border))" strokeWidth="7" />
          <circle
            cx="42"
            cy="42"
            r={R}
            fill="none"
            className={ring}
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={C * (1 - score / 100)}
          />
        </svg>
        <div>
          <div className={`text-3xl font-bold tnum ${color}`}>{score}</div>
          <div className="text-[11px] text-muted-foreground">score · {data?.violations ?? 0} issues</div>
        </div>
      </div>
      <button
        onClick={onOpen}
        className="mt-auto pt-4 text-xs text-primary hover:underline text-left"
      >
        View security posture →
      </button>
    </div>
  );
}
