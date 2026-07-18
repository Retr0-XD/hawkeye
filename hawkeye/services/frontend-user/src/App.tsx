import { useCallback, useEffect, useMemo, useState } from "react";
import { LayoutDashboard, Boxes, Brain, Network, DollarSign, ShieldCheck, Sparkles, CheckCircle2, LogOut } from "lucide-react";
import { userApi, gcpUserApi, type DashboardSummary, type Resource, type Recommendation, type Alert, type MLPredictions, type Graph, type ComplianceSummary, type SmartInsights as Insights, type MeResponse, type UserRecommendation, type CostPoint, type GcpProject, type GcpResource } from "./api";
import { ResourceTable } from "./components/ResourceTable";
import { RecommendationsPanel } from "./components/RecommendationsPanel";
import { AlertsPanel } from "./components/AlertsPanel";
import { DependencyGraph } from "./components/DependencyGraph";
import { MLPanel } from "./components/MLPanel";
import { DonutChart } from "./components/DonutChart";
import { PipelineStatus } from "./components/PipelineStatus";
import { ActivityTimeline } from "./components/ActivityTimeline";
import { SmartInsights } from "./components/SmartInsights";
import { ResourceDetail } from "./components/ResourceDetail";
import { RiskDistribution, RecommendationBreakdown, ComplianceMiniCard } from "./components/RiskDistribution";
import { FleetHealth } from "./components/FleetHealth";
import { SmartNarratives } from "./components/SmartNarratives";
import { CostRanking } from "./components/CostRanking";
import { CostHeatmap } from "./components/CostHeatmap";
import { Button } from "@/components/ui/button";
import { LoginBackground } from "./components/LoginBackground";
import { getStoredToken, setStoredToken, clearToken, handleRedirect, signIn } from "./auth";

type Tab = "overview" | "resources" | "insights" | "cost" | "ml" | "graph" | "compliance" | "approvals" | "admin";

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
  { id: "approvals", label: "Approvals", icon: <CheckCircle2 className="h-4 w-4" /> },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("overview");
  const [resources, setResources] = useState<Resource[]>([]);
  const [recommendations] = useState<Recommendation[]>([]);
  const [alerts] = useState<Alert[]>([]);
  const [predictions] = useState<MLPredictions | null>(null);
  const [graph] = useState<Graph | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [compliance, setCompliance] = useState<ComplianceSummary | null>(null);
  const [insights] = useState<Insights | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [costTrend] = useState<CostPoint[]>([]);

  // Per-user GCP (multi-tenant): each logged-in user sees THEIR OWN projects.
  const [gcpProjects, setGcpProjects] = useState<GcpProject[]>([]);
  const [activeProject, setActiveProject] = useState<string | null>(null);

  // Auth state
  const [token, setToken] = useState<string | null>(() => getStoredToken());
  const [me, setMe] = useState<MeResponse | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [authBusy, setAuthBusy] = useState(false);

  // Approvals state
  const [userRecs, setUserRecs] = useState<UserRecommendation[]>([]);
  const [approvalsLoading, setApprovalsLoading] = useState(false);

  // Bring-your-own-cloud: whether the user has connected their GCP SA.
  const [gcpConnected, setGcpConnected] = useState<boolean | null>(null);
  const [connectOpen, setConnectOpen] = useState(false);
  const [connectBusy, setConnectBusy] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  // Load the logged-in user's OWN GCP data (never the owner's shared dataset).
  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const proj = await gcpUserApi.projects();
      setGcpProjects(proj.items);
      const projectId = proj.items[0]?.projectId ?? null;
      setActiveProject(projectId);
      if (!projectId) {
        setResources([]);
        setCompliance(null);
        setLastUpdated(new Date());
        return;
      }
      const [res, comp] = await Promise.all([
        gcpUserApi.resources(projectId),
        gcpUserApi.compliance(projectId),
      ]);
      // Map GCP resources into the shared Resource shape used by the UI.
      const mapped: Resource[] = res.items.map((r: GcpResource) => ({
        id: r.id,
        name: r.name,
        type: r.type,
        status: r.status,
        region: r.region ?? undefined,
        project_id: r.project_id,
      }));
      setResources(mapped);
      setCompliance({
        score: comp.score,
        violations: comp.violations,
        public_iam_roles: comp.public_iam_roles,
      });
      setLastUpdated(new Date());
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg === "connect-required") {
        setGcpConnected(false);
        setConnectOpen(true);
        setError(null);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const loadApprovals = useCallback(async () => {
    if (!token) return;
    setApprovalsLoading(true);
    try {
      const data = await userApi.recommendations();
      setUserRecs(data.items);
    } catch {
      /* non-fatal */
    } finally {
      setApprovalsLoading(false);
    }
  }, [token]);

  // Handle OAuth redirect (capture ?code, exchange for token) on first load.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const t = await handleRedirect();
        if (t && !cancelled) {
          setToken(t);
          setStoredToken(t);
        }
      } catch (e) {
        if (!cancelled) setAuthError(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Fetch profile + dashboard once we have a token.
  useEffect(() => {
    if (!token) return;
    (async () => {
      try {
        const m = await userApi.me();
        setMe(m);
      } catch {
        setAuthError("Session expired or unauthorized. Please sign in again.");
        clearToken();
        setToken(null);
      }
    })();
    (async () => {
      try {
        const s = await gcpUserApi.status();
        setGcpConnected(s.connected);
        if (!s.connected) setConnectOpen(true);
      } catch {
        setGcpConnected(false);
        setConnectOpen(true);
      }
    })();
    void load();
    void loadApprovals();
    const id = setInterval(() => {
      void load();
      void loadApprovals();
    }, 60_000);
    return () => clearInterval(id);
  }, [token, load, loadApprovals]);

  const predByResource = useMemo(() => {
    const m = new Map<string, MLPredictions["items"][number]>();
    predictions?.items.forEach((it) => m.set(it.resource_id, it));
    return m;
  }, [predictions]);

  // Derive a summary from the user's OWN resources so the overview stays
  // meaningful without the owner's shared dataset.
  const derivedSummary = useMemo<DashboardSummary>(() => {
    const byType: Record<string, number> = {};
    let publicResources = 0;
    for (const r of resources) {
      const t = r.type ?? "Other";
      byType[t] = (byType[t] ?? 0) + 1;
      if (r.status === "public") publicResources += 1;
    }
    return {
      resourceCount: resources.length,
      byType,
      totalMonthlyCostProjection: 0,
      publicResources,
      unusedResources: 0,
      recommendationCount: recommendations.length,
      totalEstimatedSavings: 0,
    };
  }, [resources, recommendations]);

  const donutData = useMemo(() => {
    const byType = derivedSummary.byType ?? {};
    return Object.entries(byType).map(([label, value]) => ({
      label,
      value,
      color: TYPE_COLORS[label] ?? "#8b98ad",
    }));
  }, [derivedSummary]);

  const anomalies = predictions?.anomalies.length ?? 0;
  const failures = predictions?.failure_risks.length ?? 0;

  const signOut = () => {
    clearToken();
    setToken(null);
    setMe(null);
    window.location.href = window.location.pathname;
  };

  const handleConnect = async (json: string) => {
    setConnectBusy(true);
    setConnectError(null);
    try {
      await gcpUserApi.connect(json);
      setGcpConnected(true);
      setConnectOpen(false);
      await load();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setConnectError(msg.includes("400") ? "That doesn't look like a valid service-account key." : msg);
    } finally {
      setConnectBusy(false);
    }
  };

  // ---- Login screen ----
  if (!token) {
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center px-6 overflow-hidden bg-background">
        <LoginBackground />
        <div className="absolute inset-0 bg-background/40" />
        <div className="relative w-full max-w-sm rounded-2xl border border-border bg-card/90 p-8 text-center elevate">
          <img src="/hawkeye-logo.png" alt="Hawkeye" className="h-14 w-14 mx-auto rounded-xl object-contain" />
          <h1 className="mt-4 text-2xl font-bold tracking-tight">Hawkeye</h1>
          <p className="text-sm text-muted-foreground mt-1">Resource Intelligence for your GCP project</p>
          {authError && (
            <div className="mt-4 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive text-left">
              {authError}
            </div>
          )}
          <Button
            className="mt-6 w-full"
            disabled={authBusy}
            onClick={() => {
              setAuthBusy(true);
              void signIn().catch((e) => {
                setAuthError(e instanceof Error ? e.message : String(e));
                setAuthBusy(false);
              });
            }}
          >
            <svg className="mr-2 h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M21.35 11.1H12v2.99h5.35c-.23 1.4-1.62 4.1-5.35 4.1-3.22 0-5.85-2.67-5.85-5.95S8.43 6.3 11.65 6.3c1.83 0 3.06.78 3.76 1.45l2.56-2.47C16.4 3.5 14.2 2.5 11.65 2.5 6.9 2.5 3 6.4 3 11.15S6.9 19.8 11.65 19.8c5.4 0 8.98-3.79 8.98-9.14 0-.61-.06-1.07-.28-1.56z" />
            </svg>
            Sign in with Google
          </Button>
          <p className="mt-4 text-[11px] text-muted-foreground">
            Restricted to authorized users. Your Google account must be granted access.
          </p>
          <a
            className="mt-3 inline-block text-[11px] text-primary hover:underline"
            href="https://hawkeye-frontend-demo-78803747777.us-central1.run.app"
            target="_blank"
            rel="noreferrer"
          >
            View the public demo →
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-full flex app-bg">
      {/* Sidebar */}
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-card/60 backdrop-blur sticky top-0 h-screen">
        <div className="px-5 py-5 flex items-center gap-3 border-b border-border">
          <img src="/hawkeye-logo.png" alt="Hawkeye" className="h-9 w-9 rounded-lg object-contain" />
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
                tab === n.id ? "bg-primary/10 text-primary" : "text-muted-foreground hover:text-foreground hover:bg-accent"
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
          {me?.email && <div className="truncate text-foreground/80" title={me.email}>{me.email}</div>}
          <a
            className="block text-primary hover:underline pt-1"
            href="https://hawkeye-frontend-demo-78803747777.us-central1.run.app"
            target="_blank"
            rel="noreferrer"
          >
            → Public Demo
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
                {tab === "insights" && "Explainable, driver-level smart insights"}
                {tab === "cost" && "Spend breakdown, trend & budget guard"}
                {tab === "ml" && "Anomaly, failure & cost predictions"}
                {tab === "graph" && "Resource dependency topology"}
                {tab === "compliance" && "Security posture & compliance score"}
                {tab === "approvals" && "Review & action your recommendations"}
              </p>
            </div>
            <div className="flex items-center gap-3">
              {gcpConnected === false && (
                <Button variant="outline" size="sm" onClick={() => setConnectOpen(true)}>
                  + Connect GCP
                </Button>
              )}
              {gcpConnected === true && (
                <span className="hidden sm:flex items-center gap-1.5 text-xs text-good">
                  <span className="h-2 w-2 rounded-full bg-good" /> your cloud
                </span>
              )}
              {gcpProjects.length > 1 && (
                <select
                  value={activeProject ?? ""}
                  onChange={(e) => {
                    const pid = e.target.value;
                    setActiveProject(pid);
                    void (async () => {
                      setLoading(true);
                      try {
                        const [res, comp] = await Promise.all([
                          gcpUserApi.resources(pid),
                          gcpUserApi.compliance(pid),
                        ]);
                        setResources(
                          res.items.map((r: GcpResource) => ({
                            id: r.id,
                            name: r.name,
                            type: r.type,
                            status: r.status,
                            region: r.region ?? undefined,
                            project_id: r.project_id,
                          }))
                        );
                        setCompliance({
                          score: comp.score,
                          violations: comp.violations,
                          public_iam_roles: comp.public_iam_roles,
                        });
                        setLastUpdated(new Date());
                      } catch (err) {
                        setError(err instanceof Error ? err.message : String(err));
                      } finally {
                        setLoading(false);
                      }
                    })();
                  }}
                  className="rounded-md border border-border bg-background px-2 py-1 text-xs"
                  title="Switch GCP project"
                >
                  {gcpProjects.map((p) => (
                    <option key={p.projectId} value={p.projectId}>
                      {p.name || p.projectId}
                    </option>
                  ))}
                </select>
              )}
              <span className="hidden sm:flex items-center gap-1.5 text-xs text-good">
                <span className="h-2 w-2 rounded-full bg-good live-dot" /> live
              </span>
              <Button variant="outline" size="sm" onClick={() => void load()}>
                {loading ? "Refreshing…" : "↻ Refresh"}
              </Button>
              <Button variant="ghost" size="sm" onClick={signOut}>
                <LogOut className="h-4 w-4" /> Sign out
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
          {error && (
            <div className="mb-4 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
              Failed to load data: {error}
            </div>
          )}

          {tab === "overview" && (
            <div className="space-y-6">
              <FleetHealth summary={derivedSummary} predictions={predictions} />

              <SmartNarratives
                summary={derivedSummary}
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
                  <div className="rounded-xl border border-border bg-card p-5 h-full">
                    <h2 className="text-sm font-semibold text-foreground mb-3">Your GCP Resources</h2>
                    <p className="text-sm text-muted-foreground">
                      Showing resources from <span className="font-medium text-foreground">{activeProject ?? "your project"}</span>.
                      Switch projects from the header. Cost & live metrics for your own projects are coming soon.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <CostRanking resources={resources} />
                <CostHeatmap trend={costTrend} />
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

              <PipelineStatus />

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="lg:col-span-2">
                  <ResourceTable
                    resources={resources}
                    predByResource={predByResource}
                    loading={loading}
                    onOpen={setDetailId}
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

          {tab === "insights" && <SmartInsights insights={insights} loading={loading} onOpen={setDetailId} />}

          {tab === "cost" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <CostRanking resources={resources} />
                <CostHeatmap trend={costTrend} />
              </div>
              <div className="rounded-xl border border-border bg-card p-5">
                <h2 className="text-sm font-semibold text-foreground mb-2">Cost for {activeProject ?? "your project"}</h2>
                <p className="text-sm text-muted-foreground">
                  Per-resource billing for your own GCP project is being wired up. The ranking above reflects
                  resources discovered in your project.
                </p>
              </div>
            </div>
          )}

          {tab === "ml" && <MLPanel predictions={predictions} loading={loading} />}

          {tab === "graph" && <DependencyGraph graph={graph} loading={loading} />}

          {tab === "compliance" && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <div className="rounded-xl border border-border bg-card p-5">
                  <h2 className="text-sm font-semibold text-foreground mb-2">Compliance Score</h2>
                  <div className="text-3xl font-bold tnum">
                    {compliance ? `${compliance.score}/100` : "—"}
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {compliance?.violations ?? 0} public-IAM finding(s) in {activeProject ?? "your project"}
                  </p>
                </div>
                <div className="lg:col-span-2 rounded-xl border border-border bg-card p-5">
                  <h2 className="text-sm font-semibold text-foreground mb-3">Public IAM Roles</h2>
                  {compliance && (compliance.public_iam_roles ?? []).length > 0 ? (
                    <ul className="space-y-1.5 text-sm">
                      {(compliance.public_iam_roles ?? []).map((r) => (
                        <li key={r} className="text-bad">{r}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted-foreground">No publicly exposed IAM roles detected.</p>
                  )}
                </div>
              </div>
            </div>
          )}

          {tab === "approvals" && (
            <ApprovalsPanel
              recs={userRecs}
              loading={approvalsLoading}
              onApprove={async (id) => {
                await userApi.approve(id);
                await loadApprovals();
              }}
              onReject={async (id) => {
                await userApi.reject(id);
                await loadApprovals();
              }}
              onSessionExpired={() => {
                clearToken();
                setToken(null);
                setAuthError("Session expired. Please sign in again.");
              }}
            />
          )}
        </main>
      </div>

      {detailId && (
        <ResourceDetail
          resourceId={detailId}
          onClose={() => setDetailId(null)}
          predByResource={predByResource}
          localResource={resources.find((r) => r.id === detailId) ?? null}
        />
      )}

      {connectOpen && (
        <ConnectGcpModal
          busy={connectBusy}
          error={connectError}
          onConnect={handleConnect}
          onClose={() => {
            if (gcpConnected) setConnectOpen(false);
          }}
        />
      )}
    </div>
  );
}

function ConnectGcpModal({
  busy,
  error,
  onConnect,
  onClose,
}: {
  busy: boolean;
  error: string | null;
  onConnect: (json: string) => void;
  onClose: () => void;
}) {
  const [json, setJson] = useState("");
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div
        className="w-full max-w-lg rounded-2xl border border-border bg-card p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-lg font-semibold text-foreground">Connect your GCP</h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Hawkeye reads <span className="font-medium text-foreground">only your own</span> GCP projects.
          Paste a service-account key (Viewer role) from your Google Cloud project. Your key is encrypted
          and stored per-account — it is never shown back and never shared with anyone else.
        </p>
        <ol className="mt-3 list-decimal list-inside text-xs text-muted-foreground space-y-1">
          <li>Go to IAM &amp; Admin → Service Accounts → Create service account</li>
          <li>Grant role <code className="text-foreground">Viewer</code> (read-only)</li>
          <li>Create a JSON key and paste it below</li>
        </ol>
        <textarea
          value={json}
          onChange={(e) => setJson(e.target.value)}
          placeholder='{ "type": "service_account", "project_id": "...", ... }'
          className="mt-4 h-40 w-full rounded-lg border border-border bg-background p-3 font-mono text-xs"
        />
        {error && <div className="mt-2 text-xs text-destructive">{error}</div>}
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button size="sm" onClick={() => onConnect(json)} disabled={busy || !json.trim()}>
            {busy ? "Connecting…" : "Connect"}
          </Button>
        </div>
      </div>
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
      <button onClick={onOpen} className="mt-auto pt-4 text-xs text-primary hover:underline text-left">
        View security posture →
      </button>
    </div>
  );
}

function ApprovalsPanel({
  recs,
  loading,
  onApprove,
  onReject,
  onSessionExpired,
}: {
  recs: UserRecommendation[];
  loading: boolean;
  onApprove: (id: string) => Promise<void> | void;
  onReject: (id: string) => Promise<void> | void;
  onSessionExpired: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const run = async (fn: (id: string) => Promise<void> | void, id: string) => {
    setBusy(id);
    setErr(null);
    try {
      await fn(id);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/401|unauthorized/i.test(msg)) {
        onSessionExpired();
      } else {
        setErr("Action failed — please retry.");
      }
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="rounded-xl border border-border bg-card p-5 elevate">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Your Recommendations</h2>
        <span className="text-xs text-muted-foreground tnum">{recs.length} total</span>
      </div>
      {err && (
        <div className="mb-3 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {err}
        </div>
      )}
      {loading && recs.length === 0 ? (
        <div className="h-24 animate-pulse rounded bg-muted" />
      ) : recs.length === 0 ? (
        <p className="text-sm text-muted-foreground">No recommendations pending your review.</p>
      ) : (
        <div className="space-y-3">
          {recs.map((r) => {
            const status = r.approval?.status ?? "pending";
            const isBusy = busy === r.id;
            return (
              <div key={r.id} className="rounded-lg border border-border bg-background/40 p-4">
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-sm truncate">{r.title ?? r.id}</span>
                      {r.severity && (
                        <span className="rounded px-1.5 py-0.5 text-[10px] uppercase bg-muted text-muted-foreground">
                          {r.severity}
                        </span>
                      )}
                    </div>
                    {r.description && (
                      <p className="text-xs text-muted-foreground mt-1">{r.description}</p>
                    )}
                    {typeof r.estimated_savings === "number" && r.estimated_savings > 0 && (
                      <p className="text-xs text-good mt-1 tnum">
                        est. savings ${r.estimated_savings.toLocaleString()}
                      </p>
                    )}
                  </div>
                  <div className="shrink-0 flex flex-col items-end gap-2">
                    {status === "pending" ? (
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant="default"
                          disabled={isBusy}
                          onClick={() => run(onApprove, r.id)}
                        >
                          {isBusy ? "…" : "Approve"}
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isBusy}
                          onClick={() => run(onReject, r.id)}
                        >
                          {isBusy ? "…" : "Reject"}
                        </Button>
                      </div>
                    ) : (
                      <span
                        className={`text-xs px-2 py-1 rounded ${
                          status === "approved" ? "bg-good/15 text-good" : "bg-destructive/15 text-destructive"
                        }`}
                      >
                        {status}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
