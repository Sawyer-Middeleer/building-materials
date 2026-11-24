export interface SkuMetricPoint {
  id: string;
  label: string;
  uFactor?: number; // lower is better (0.15..0.55)
  shgc?: number; // lower blocks more heat (0.15..0.55)
  vlt?: number; // higher admits more daylight (0.25..0.75)
  dp?: number; // higher resists more wind (20..70)
}

interface SkuRadarChartProps {
  skus: SkuMetricPoint[];
  selectedId: string | null;
  onSelectSku: (id: string) => void;
}

const AXES = [
  {
    key: "insulation",
    label: "Insulation",
    sub: "1 / U-Factor",
    angle: -Math.PI / 2,
    score: (p: SkuMetricPoint) =>
      p.uFactor !== undefined ? clamp((0.55 - p.uFactor) / (0.55 - 0.16)) : 0.4,
  },
  {
    key: "daylight",
    label: "Daylight",
    sub: "VLT",
    angle: 0,
    score: (p: SkuMetricPoint) =>
      p.vlt !== undefined ? clamp((p.vlt - 0.2) / (0.65 - 0.2)) : 0.4,
  },
  {
    key: "solar",
    label: "Solar Control",
    sub: "1 − SHGC",
    angle: Math.PI / 2,
    score: (p: SkuMetricPoint) =>
      p.shgc !== undefined ? clamp((0.5 - p.shgc) / (0.5 - 0.14)) : 0.4,
  },
  {
    key: "wind",
    label: "Wind Load",
    sub: "DP (psf)",
    angle: Math.PI,
    score: (p: SkuMetricPoint) =>
      p.dp !== undefined ? clamp((p.dp - 15) / (70 - 15)) : 0.32,
  },
];

function clamp(v: number): number {
  return Math.max(0.12, Math.min(1, v));
}

export function SkuRadarChart({ skus, selectedId, onSelectSku }: SkuRadarChartProps) {
  if (skus.length === 0) return null;

  const cx = 112;
  const cy = 94;
  const radius = 58;
  const rings = [0.33, 0.66, 1];

  const polyPoints = (p: SkuMetricPoint) =>
    AXES.map((ax) => {
      const r = ax.score(p) * radius;
      return `${(cx + Math.cos(ax.angle) * r).toFixed(1)},${(cy + Math.sin(ax.angle) * r).toFixed(1)}`;
    }).join(" ");

  const active = skus.find((s) => s.id === selectedId) ?? skus[0];

  return (
    <div className="radar-wrap">
      <div className="radar-caption">SKU Envelope ({skus.length} configs)</div>
      <svg width="224" height="186" viewBox="0 0 224 186" aria-label="SKU performance radar chart">
        {/* Concentric hairline polygon rings */}
        {rings.map((lvl) => {
          const pts = AXES.map(
            (ax) =>
              `${(cx + Math.cos(ax.angle) * radius * lvl).toFixed(1)},${(
                cy +
                Math.sin(ax.angle) * radius * lvl
              ).toFixed(1)}`
          ).join(" ");
          return (
            <polygon
              key={lvl}
              points={pts}
              fill="none"
              stroke="#cfc9bc"
              strokeWidth={lvl === 1 ? 0.9 : 0.6}
              strokeDasharray={lvl === 1 ? undefined : "2 2"}
            />
          );
        })}

        {/* Axis spokes */}
        {AXES.map((ax) => (
          <line
            key={ax.key}
            x1={cx}
            y1={cy}
            x2={cx + Math.cos(ax.angle) * radius}
            y2={cy + Math.sin(ax.angle) * radius}
            stroke="#cfc9bc"
            strokeWidth="0.7"
          />
        ))}

        {/* All sibling SKUs as delicate clickable hairlines */}
        {skus
          .filter((s) => s.id !== active.id)
          .map((s) => (
            <polygon
              key={s.id}
              points={polyPoints(s)}
              fill="none"
              stroke="rgba(24, 23, 21, 0.22)"
              strokeWidth="0.9"
              style={{ cursor: "pointer" }}
              onClick={() => onSelectSku(s.id)}
            >
              <title>{s.label}</title>
            </polygon>
          ))}

        {/* Active SKU highlighted in surgical vermilion */}
        <polygon
          points={polyPoints(active)}
          fill="rgba(201, 61, 36, 0.14)"
          stroke="#c93d24"
          strokeWidth="1.6"
        />
        {AXES.map((ax) => {
          const r = ax.score(active) * radius;
          return (
            <circle
              key={ax.key}
              cx={cx + Math.cos(ax.angle) * r}
              cy={cy + Math.sin(ax.angle) * r}
              r="2.6"
              fill="#c93d24"
            />
          );
        })}

        {/* Axis labels */}
        <text x={cx} y={14} textAnchor="middle" className="radar-label">
          INSULATION
        </text>
        <text x={cx} y={24} textAnchor="middle" className="radar-sub">
          (lower U)
        </text>

        <text x={cx + radius + 8} y={cy - 2} textAnchor="start" className="radar-label">
          DAYLIGHT
        </text>
        <text x={cx + radius + 8} y={cy + 9} textAnchor="start" className="radar-sub">
          VLT
        </text>

        <text x={cx} y={cy + radius + 16} textAnchor="middle" className="radar-label">
          SOLAR CTRL
        </text>
        <text x={cx} y={cy + radius + 26} textAnchor="middle" className="radar-sub">
          (lower SHGC)
        </text>

        <text x={cx - radius - 8} y={cy - 2} textAnchor="end" className="radar-label">
          WIND
        </text>
        <text x={cx - radius - 8} y={cy + 9} textAnchor="end" className="radar-sub">
          DP
        </text>
      </svg>
    </div>
  );
}
