// Lightweight, dependency-free SVG charts for Hawkeye dashboards.
// Keeps the bundle small and the theme consistent (CSS variables).

type Series = { label: string; values: (number | null)[]; color: string };

/** Horizontal bar chart (good for categorical breakdowns). */
export function BarChart({
  data,
  height = 200,
  unit = "",
  color = "#2dd4bf",
}: {
  data: { label: string; value: number }[];
  height?: number;
  unit?: string;
  color?: string;
}) {
  if (data.length === 0) return <div className="text-sm text-muted-foreground">No data</div>;
  const max = Math.max(...data.map((d) => d.value), 1);
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  return (
    <div style={{ height }} className="space-y-2 overflow-auto pr-1">
      {data.map((d, i) => {
        const pct = (d.value / max) * 100;
        const share = Math.round((d.value / total) * 100);
        return (
          <div key={i} className="flex items-center gap-3 text-sm">
            <div className="w-[120px] shrink-0 truncate text-muted-foreground" title={d.label}>
              {d.label}
            </div>
            <div className="flex-1 h-5 rounded bg-muted/50 overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{ width: `${pct}%`, background: color }}
              />
            </div>
            <div className="w-20 shrink-0 text-right tnum text-foreground">
              {d.value.toFixed(d.value % 1 === 0 ? 0 : 2)}
              {unit}
            </div>
            <div className="w-10 shrink-0 text-right tnum text-muted-foreground text-xs">{share}%</div>
          </div>
        );
      })}
    </div>
  );
}

/** Multi-series line chart (good for time-series / trends). */
export function LineChart({
  series,
  height = 220,
  xLabels,
  emptyText = "No time-series data yet",
}: {
  series: Series[];
  height?: number;
  xLabels?: string[];
  emptyText?: string;
}) {
  const W = 560;
  const H = height;
  const padL = 40;
  const padR = 12;
  const padT = 12;
  const padB = 24;
  const allVals = series.flatMap((s) => s.values).filter((v) => v != null);
  if (allVals.length === 0) {
    return (
      <div className="h-[220px] grid place-items-center text-sm text-muted-foreground rounded-lg border border-dashed border-border">
        {emptyText}
      </div>
    );
  }
  const max = Math.max(...allVals, 1);
  const n = Math.max(...series.map((s) => s.values.length), 1);
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;
  const x = (i: number) => padL + (n <= 1 ? innerW / 2 : (i / (n - 1)) * innerW);
  const y = (v: number) => padT + innerH - (v / max) * innerH;

  const gridLines = 4;
  return (
    <div className="w-full overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ minWidth: 480 }}>
        {Array.from({ length: gridLines + 1 }).map((_, i) => {
          const gy = padT + (i / gridLines) * innerH;
          const val = max - (i / gridLines) * max;
          return (
            <g key={i}>
              <line x1={padL} y1={gy} x2={W - padR} y2={gy} stroke="hsl(var(--border))" strokeWidth={1} />
              <text x={padL - 6} y={gy + 3} textAnchor="end" fontSize="9" fill="hsl(var(--muted-foreground))">
                {val.toFixed(val < 10 ? 1 : 0)}
              </text>
            </g>
          );
        })}
        {series.map((s, si) => {
          const pts = s.values
            .map((v, i) => (v == null ? "" : `${x(i)},${y(v)}`))
            .filter(Boolean)
            .join(" ");
          return (
            <g key={si}>
              <polyline points={pts} fill="none" stroke={s.color} strokeWidth={2} strokeLinejoin="round" />
              {s.values.map((v, i) =>
                v == null ? null : <circle key={i} cx={x(i)} cy={y(v)} r={2.5} fill={s.color} />
              )}
            </g>
          );
        })}
        {xLabels &&
          xLabels.map((lab, i) => (
            <text
              key={i}
              x={x(i)}
              y={H - 6}
              textAnchor="middle"
              fontSize="9"
              fill="hsl(var(--muted-foreground))"
            >
              {lab}
            </text>
          ))}
      </svg>
      <div className="flex flex-wrap gap-3 mt-1 px-2">
        {series.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className="h-2 w-2 rounded-full" style={{ background: s.color }} />
            {s.label}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Stacked/segmented bar for a single 100% distribution (e.g. risk levels). */
export function DistributionBar({
  segments,
}: {
  segments: { label: string; value: number; color: string }[];
}) {
  const total = segments.reduce((s, x) => s + x.value, 0) || 1;
  return (
    <div>
      <div className="flex h-3 w-full rounded-full overflow-hidden bg-muted">
        {segments.map((s, i) => (
          <div key={i} style={{ width: `${(s.value / total) * 100}%`, background: s.color }} title={`${s.label}: ${s.value}`} />
        ))}
      </div>
      <div className="flex flex-wrap gap-3 mt-2 text-xs">
        {segments.map((s, i) => (
          <div key={i} className="flex items-center gap-1.5 text-muted-foreground">
            <span className="h-2 w-2 rounded-sm" style={{ background: s.color }} />
            {s.label} <span className="tnum text-foreground">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/** Tiny inline sparkline for table rows / KPI cards. */
export function Sparkline({
  values,
  width = 96,
  height = 28,
  color = "#2dd4bf",
  fill = true,
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
  color?: string;
  fill?: boolean;
}) {
  const vals = values.filter((v): v is number => v != null);
  if (vals.length < 2) {
    return <div style={{ width, height }} className="grid place-items-center text-[9px] text-muted-foreground">—</div>;
  }
  const max = Math.max(...vals, 1);
  const min = Math.min(...vals, 0);
  const range = max - min || 1;
  const n = vals.length;
  const x = (i: number) => (i / (n - 1)) * width;
  const y = (v: number) => height - ((v - min) / range) * (height - 4) - 2;
  const pts = vals.map((v, i) => `${x(i)},${y(v)}`).join(" ");
  const area = `${x(0)},${height} ${pts} ${x(n - 1)},${height}`;
  const last = vals[n - 1];
  const first = vals[0];
  const trendUp = last >= first;
  const stroke = color || (trendUp ? "#f87171" : "#2dd4bf");
  return (
    <svg width={width} height={height} className="overflow-visible">
      {fill && <polygon points={area} fill={stroke} opacity={0.12} />}
      <polyline points={pts} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={x(n - 1)} cy={y(last)} r={2} fill={stroke} />
    </svg>
  );
}

/** Radial gauge for a 0-100 score (e.g. fleet health / compliance). */
export function RadialGauge({
  value,
  size = 120,
  label,
  sublabel,
  color = "#2dd4bf",
}: {
  value: number;
  size?: number;
  label?: string;
  sublabel?: string;
  color?: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  const r = size / 2 - 10;
  const c = 2 * Math.PI * r;
  const dash = (v / 100) * c;
  const cx = size / 2;
  const cy = size / 2;
  return (
    <div className="relative grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="hsl(var(--muted))" strokeWidth={9} />
        <circle
          cx={cx}
          cy={cy}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={9}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
        />
      </svg>
      <div className="absolute text-center">
        <div className="tnum text-2xl font-semibold leading-none">{Math.round(v)}</div>
        {label && <div className="text-[10px] uppercase tracking-wide text-muted-foreground mt-0.5">{label}</div>}
        {sublabel && <div className="text-[10px] text-muted-foreground">{sublabel}</div>}
      </div>
    </div>
  );
}

/** Heatmap grid (e.g. cost by day x service). */
export function Heatmap({
  rows,
  cols,
  values,
  color = "#2dd4bf",
}: {
  rows: string[];
  cols: string[];
  values: number[][];
  color?: string;
}) {
  const max = Math.max(...values.flat(), 1);
  return (
    <div className="overflow-x-auto">
      <div className="inline-grid gap-1" style={{ gridTemplateColumns: `auto repeat(${cols.length}, 14px)` }}>
        <div />
        {cols.map((c, i) => (
          <div key={i} className="text-[8px] text-muted-foreground text-center">{c}</div>
        ))}
        {rows.map((r, ri) => (
          <FragmentRow key={ri} label={r} cols={cols} vals={values[ri]} max={max} color={color} />
        ))}
      </div>
    </div>
  );
}

function FragmentRow({
  label,
  cols,
  vals,
  max,
  color,
}: {
  label: string;
  cols: string[];
  vals: number[];
  max: number;
  color: string;
}) {
  return (
    <>
      <div className="text-[8px] text-muted-foreground pr-1 truncate max-w-[60px]">{label}</div>
      {cols.map((_, ci) => {
        const v = vals[ci] ?? 0;
        const op = 0.12 + (v / max) * 0.88;
        return <div key={ci} className="h-3.5 w-3.5 rounded-sm" style={{ background: color, opacity: op }} title={`${label} ${cols[ci]}: ${v}`} />;
      })}
    </>
  );
}
