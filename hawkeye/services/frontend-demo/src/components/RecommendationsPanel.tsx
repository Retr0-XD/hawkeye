import type { Recommendation } from "../api";
import { censorId } from "../lib/censor";

const SEVERITY_COLORS: Record<string, string> = {
  HIGH: "bg-bad/15 text-bad",
  MEDIUM: "bg-warn/15 text-warn",
  LOW: "bg-good/15 text-good",
};

export function RecommendationsPanel({
  recommendations,
  loading,
}: {
  recommendations: Recommendation[];
  loading: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card">
      <div className="px-5 py-4 border-b border-border text-sm font-semibold text-foreground flex items-center justify-between">
        <span>Recommendations</span>
        <span className="text-xs text-muted-foreground tnum">{recommendations.length} items</span>
      </div>
      <div className="p-3 space-y-2 max-h-80 overflow-y-auto">
        {loading && recommendations.length === 0 && <div className="h-40 animate-pulse rounded bg-muted" />}
        {!loading && recommendations.length === 0 && (
          <p className="text-sm text-muted-foreground px-2 py-4">
            No optimization recommendations yet. The Processing service generates these as cost/security signals appear.
          </p>
        )}
        {recommendations.map((rec) => (
          <div key={rec.id} className="rounded-xl border border-border bg-muted/30 p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-medium text-foreground">{rec.title ?? rec.type ?? "Recommendation"}</span>
              {rec.severity && (
                <span className={`text-[11px] rounded px-2 py-0.5 ${SEVERITY_COLORS[rec.severity] ?? "bg-muted text-muted-foreground"}`}>
                  {rec.severity}
                </span>
              )}
            </div>
            {rec.description && <p className="mt-1 text-xs text-muted-foreground">{rec.description}</p>}
            <div className="mt-1 flex items-center justify-between text-xs text-muted-foreground">
              <span className="font-mono truncate max-w-[200px]" title={rec.resource_id ?? ""}>
                {censorId(rec.resource_id ?? "")}
              </span>
              {rec.estimated_savings ? (
                <span className="text-good tnum">${Number(rec.estimated_savings).toFixed(2)}/mo</span>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
