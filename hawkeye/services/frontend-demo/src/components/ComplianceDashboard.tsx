import { useEffect, useState } from "react";
import { api, type ComplianceSummary } from "../api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

function shortId(id: string) {
  return id.split("/").pop() ?? id;
}

export function ComplianceDashboard() {
  const [data, setData] = useState<ComplianceSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .compliance()
      .then((d) => active && setData(d))
      .catch(() => {})
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const score = data?.score ?? 100;
  const scoreColor =
    score >= 90 ? "text-good" : score >= 70 ? "text-warn" : "text-bad";

  const checks = [
    { label: "Publicly accessible", items: data?.public_resources ?? [], tone: "danger" as const },
    { label: "Unencrypted at rest", items: data?.unencrypted ?? [], tone: "danger" as const },
    { label: "Backups disabled", items: data?.no_backup ?? [], tone: "warning" as const },
    { label: "Audit logging off", items: data?.no_audit_logging ?? [], tone: "warning" as const },
  ];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Compliance Score</CardTitle>
          </CardHeader>
          <CardContent>
            <div className={`text-4xl font-bold tnum ${scoreColor}`}>{score}</div>
            <p className="text-xs text-muted-foreground mt-1">out of 100</p>
            <Progress
              value={score}
              className="mt-4"
              indicatorClassName={
                score >= 90 ? "bg-good" : score >= 70 ? "bg-warn" : "bg-bad"
              }
            />
            <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>{data?.total ?? 0} resources</span>
              <span>{data?.violations ?? 0} violations</span>
            </div>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-sm">Security Posture</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {checks.map((c) => (
              <div key={c.label}>
                <div className="flex items-center justify-between text-sm mb-1.5">
                  <span className="text-muted-foreground">{c.label}</span>
                  <Badge variant={c.items.length ? c.tone : "success"}>
                    {c.items.length ? `${c.items.length} found` : "none"}
                  </Badge>
                </div>
                {c.items.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {c.items.slice(0, 12).map((id) => (
                      <span
                        key={id}
                        className="text-[11px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground"
                      >
                        {shortId(id)}
                      </span>
                    ))}
                    {c.items.length > 12 && (
                      <span className="text-[11px] text-muted-foreground">
                        +{c.items.length - 12} more
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
            {loading && !data && <div className="h-32 animate-pulse rounded bg-muted" />}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
