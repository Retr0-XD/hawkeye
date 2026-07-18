import { useMemo, useState } from "react";
import {
  Search,
  MoreHorizontal,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  ShieldAlert,
  Activity,
} from "lucide-react";
import type { Resource, MLPredictions } from "../api";
import { censorId, censorName } from "../lib/censor";
import { consoleUrlForResource } from "../lib/console";
import { Sparkline } from "./charts";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const TYPE_COLORS: Record<string, string> = {
  Container: "bg-primary/15 text-primary",
  Network: "bg-indigo/15 text-indigo",
  Storage: "bg-warn/15 text-warn",
  Database: "bg-good/15 text-good",
  Compute: "bg-bad/15 text-bad",
};

type SortKey = "name" | "type" | "status" | "region" | "cost";

export function ResourceTable({
  resources,
  predByResource,
  loading,
  onOpen,
  metricSeries,
}: {
  resources: Resource[];
  predByResource: Map<string, MLPredictions["items"][number]>;
  loading: boolean;
  onOpen?: (id: string) => void;
  metricSeries?: Record<string, number[]>;
}) {
  const [q, setQ] = useState("");
  const [type, setType] = useState<string>("all");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "name",
    dir: "asc",
  });
  const [page, setPage] = useState(0);
  const PAGE = 8;

  const types = useMemo(
    () => ["all", ...Array.from(new Set(resources.map((r) => r.type ?? "Unknown")))],
    [resources]
  );

  const filtered = useMemo(() => {
    const needle = q.toLowerCase();
    const rows = resources.filter((r) => {
      if (type !== "all" && (r.type ?? "Unknown") !== type) return false;
      if (!needle) return true;
      return (
        (r.name ?? "").toLowerCase().includes(needle) ||
        r.id.toLowerCase().includes(needle) ||
        (r.region ?? "").toLowerCase().includes(needle)
      );
    });
    const dir = sort.dir === "asc" ? 1 : -1;
    rows.sort((a, b) => {
      let av: string | number;
      let bv: string | number;
      if (sort.key === "cost") {
        av = a.monthly_cost_projection ?? 0;
        bv = b.monthly_cost_projection ?? 0;
      } else {
        av = (a[sort.key] ?? "").toString();
        bv = (b[sort.key] ?? "").toString();
      }
      if (typeof av === "number" && typeof bv === "number") {
        return (av - bv) * dir;
      }
      return String(av).localeCompare(String(bv)) * dir;
    });
    return rows;
  }, [resources, q, type, sort]);

  const pageRows = useMemo(
    () => filtered.slice(page * PAGE, page * PAGE + PAGE),
    [filtered, page]
  );
  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE));

  const toggleSort = (key: SortKey) =>
    setSort((s) =>
      s.key === key
        ? { key, dir: s.dir === "asc" ? "desc" : "asc" }
        : { key, dir: "asc" }
    );

  const SortIcon = ({ k }: { k: SortKey }) =>
    sort.key !== k ? (
      <ArrowUpDown className="h-3.5 w-3.5 opacity-50" />
    ) : sort.dir === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5" />
    );

  if (loading && resources.length === 0) {
    return <div className="h-64 rounded-xl border border-border bg-card animate-pulse" />;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-col sm:flex-row gap-2 sm:items-center sm:justify-between">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              setPage(0);
            }}
            placeholder="Search name, id, region…"
            className="pl-8"
          />
        </div>
        <div className="flex flex-wrap gap-1.5">
          {types.map((t) => (
            <button
              key={t}
              onClick={() => {
                setType(t);
                setPage(0);
              }}
              className={`px-2.5 py-1 rounded-md text-xs font-medium border transition ${
                type === t
                  ? "border-primary/40 bg-primary/10 text-primary"
                  : "border-border text-muted-foreground hover:text-foreground"
              }`}
            >
              {t === "all" ? "All" : t}
            </button>
          ))}
        </div>
      </div>

      <div className="rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead>
                <button
                  className="flex items-center gap-1 hover:text-foreground"
                  onClick={() => toggleSort("name")}
                >
                  Resource <SortIcon k="name" />
                </button>
              </TableHead>
              <TableHead>
                <button
                  className="flex items-center gap-1 hover:text-foreground"
                  onClick={() => toggleSort("type")}
                >
                  Type <SortIcon k="type" />
                </button>
              </TableHead>
              <TableHead>
                <button
                  className="flex items-center gap-1 hover:text-foreground"
                  onClick={() => toggleSort("status")}
                >
                  Status <SortIcon k="status" />
                </button>
              </TableHead>
              <TableHead>
                <button
                  className="flex items-center gap-1 hover:text-foreground"
                  onClick={() => toggleSort("region")}
                >
                  Region <SortIcon k="region" />
                </button>
              </TableHead>
              <TableHead className="text-right">
                <button
                  className="flex items-center gap-1 ml-auto hover:text-foreground"
                  onClick={() => toggleSort("cost")}
                >
                  Cost/mo <SortIcon k="cost" />
                </button>
              </TableHead>
              <TableHead>24h CPU</TableHead>
              <TableHead>Risk</TableHead>
              <TableHead className="w-10" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((r) => {
              const pred = predByResource.get(r.id);
              const anomaly = pred?.anomaly?.is_anomaly;
              const risk = pred?.failure?.is_high_risk;
              return (
                <TableRow
                  key={r.id}
                  onClick={() => onOpen?.(r.id)}
                  className="cursor-pointer"
                >
                  <TableCell>
                    <div className="font-medium text-foreground">
                      {censorName(r.name ?? r.id.split("/").pop() ?? r.id)}
                    </div>
                    <div className="text-[11px] font-mono text-muted-foreground truncate max-w-[220px]">
                      {censorId(r.id)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="muted" className={TYPE_COLORS[r.type ?? ""]}>
                      {r.type ?? "—"}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <span className="flex items-center gap-1.5 text-xs">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          r.status === "ACTIVE" ? "bg-good" : "bg-muted-foreground"
                        }`}
                      />
                      {r.status ?? "—"}
                    </span>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {r.region ?? "—"}
                  </TableCell>
                  <TableCell className="text-right tnum">
                    ${(r.monthly_cost_projection ?? 0).toFixed(2)}
                  </TableCell>
                  <TableCell>
                    {metricSeries?.[r.id] ? (
                      <Sparkline values={metricSeries[r.id]} width={84} height={26} />
                    ) : r.cpu_utilization_avg != null ? (
                      <span className="tnum text-xs text-muted-foreground">
                        {r.cpu_utilization_avg.toFixed(0)}%
                      </span>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    {anomaly ? (
                      <Badge variant="danger" className="gap-1">
                        <Activity className="h-3 w-3" /> anomaly
                      </Badge>
                    ) : risk ? (
                      <Badge variant="warning" className="gap-1">
                        <ShieldAlert className="h-3 w-3" /> risk
                      </Badge>
                    ) : r.public_access ? (
                      <Badge variant="warning">public</Badge>
                    ) : (
                      <span className="text-xs text-muted-foreground">—</span>
                    )}
                  </TableCell>
                  <TableCell>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuLabel>Actions</DropdownMenuLabel>
                        <DropdownMenuItem
                          onClick={() =>
                            window.open(
                              consoleUrlForResource(r.id, r.type, r.project_id),
                              "_blank"
                            )
                          }
                        >
                          <ExternalLink className="h-4 w-4" /> Open in Console
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                        <DropdownMenuItem
                          onClick={() => navigator.clipboard?.writeText(r.id)}
                        >
                          Copy resource ID
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              );
            })}
            {pageRows.length === 0 && (
              <TableRow className="hover:bg-transparent">
                <TableCell colSpan={7} className="h-24 text-center text-muted-foreground">
                  No resources match your filter.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div className="tnum">
          {filtered.length} of {resources.length} resources
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            Previous
          </Button>
          <span className="tnum">
            {page + 1} / {pageCount}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}
