// Visualizes the Hawkeye data pipeline as a connected stage strip.
const STAGES = [
  { name: "Ingestion", sub: "Cloud Run" },
  { name: "Processing", sub: "Correlate" },
  { name: "Storage", sub: "Firestore · BQ" },
  { name: "API", sub: "REST" },
  { name: "ML", sub: "Predict" },
  { name: "Automation", sub: "Remediate" },
];

export function PipelineStatus() {
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-sm font-semibold text-foreground">Data Pipeline</h2>
        <span className="text-[11px] text-good flex items-center gap-1.5">
          <span className="h-2 w-2 rounded-full bg-good live-dot" /> operational
        </span>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto">
        {STAGES.map((s, i) => (
          <div key={s.name} className="flex items-center gap-1 shrink-0">
            <div className="flex flex-col items-center text-center px-2">
              <div className="h-9 w-9 rounded-xl bg-muted border border-border grid place-items-center text-primary text-sm">
                {i + 1}
              </div>
              <div className="text-[11px] text-foreground font-medium mt-1.5 whitespace-nowrap">{s.name}</div>
              <div className="text-[10px] text-muted-foreground whitespace-nowrap">{s.sub}</div>
            </div>
            {i < STAGES.length - 1 && (
              <div className="h-px w-6 bg-gradient-to-r from-primary/50 to-border mb-5" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
