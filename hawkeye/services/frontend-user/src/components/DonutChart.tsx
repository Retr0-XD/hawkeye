// Lightweight SVG donut chart (no external chart lib).
export function DonutChart({
  data,
  size = 180,
  thickness = 22,
}: {
  data: { label: string; value: number; color: string }[];
  size?: number;
  thickness?: number;
}) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const radius = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * radius;

  let offset = 0;
  const segments = data.map((d) => {
    const frac = d.value / total;
    const len = frac * circ;
    const seg = {
      color: d.color,
      dash: `${len} ${circ - len}`,
      offset: -offset,
      label: d.label,
      value: d.value,
      pct: Math.round(frac * 100),
    };
    offset += len;
    return seg;
  });

  return (
    <div className="flex items-center gap-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="shrink-0">
        <circle cx={cx} cy={cy} r={radius} fill="none" stroke="hsl(var(--border))" strokeWidth={thickness} />
        {segments.map((s, i) => (
          <circle
            key={i}
            cx={cx}
            cy={cy}
            r={radius}
            fill="none"
            stroke={s.color}
            strokeWidth={thickness}
            strokeDasharray={s.dash}
            strokeDashoffset={s.offset}
            transform={`rotate(-90 ${cx} ${cy})`}
            strokeLinecap="butt"
          />
        ))}
        <text x={cx} y={cy - 4} textAnchor="middle" fill="hsl(var(--foreground))" fontSize="20" fontWeight="600">
          {total}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" fill="hsl(var(--muted-foreground))" fontSize="10">
          resources
        </text>
      </svg>
      <div className="space-y-1.5 text-sm">
        {segments.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />
            <span className="text-foreground">{s.label}</span>
            <span className="text-muted-foreground ml-auto tnum">{s.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
