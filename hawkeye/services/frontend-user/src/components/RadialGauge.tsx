// Radial gauge for a 0..1 risk/health score.
export function RadialGauge({
  value,
  label,
  size = 92,
  color = "#2dd4bf",
}: {
  value: number; // 0..1
  label: string;
  size?: number;
  color?: string;
}) {
  const stroke = 8;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value));
  const dash = pct * c;
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#1f2a3d" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${dash} ${c - dash}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text x="50%" y="48%" textAnchor="middle" fill="#e6edf6" fontSize="18" fontWeight="700" className="tnum">
          {Math.round(pct * 100)}
        </text>
        <text x="50%" y="64%" textAnchor="middle" fill="#8b98ad" fontSize="9">
          {label}
        </text>
      </svg>
    </div>
  );
}
