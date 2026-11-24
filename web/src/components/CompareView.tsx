import { useEffect, useState } from "react";
import { api, type CompareResponse, type GraphNode, type Statement } from "../api/client";

interface CompareViewProps {
  onNavigateNode: (id: string) => void;
}

const PROP_LABELS: Record<string, string> = {
  uFactor: "U-Factor",
  solarHeatGainCoefficient: "Solar Heat Gain (SHGC)",
  visibleLightTransmittance: "Visible Light Transmittance",
  structuralDesignPressure: "Design Pressure",
  airInfiltration: "Air Infiltration",
  performanceClass: "Performance Class",
  gwp: "Embodied Carbon (A1–A3)",
  installedCostPerArea: "Installed Cost",
  serviceLife: "Service Life",
};

function formatStmt(s: Statement | null): string {
  if (!s) return "—";
  if (s.state) return "Not published";
  if (s.value !== undefined) return String(s.value);
  if (s.quantity) {
    const q = s.quantity;
    const val = q.value !== undefined ? String(q.value) : `${q.min}–${q.max}`;
    return q.unit === "1" ? val : `${val} ${q.unit}`;
  }
  return "—";
}

function RangeDotPlot({
  val,
  stats,
  status,
}: {
  val?: number;
  stats: { min: number; median: number; max: number } | null;
  status?: string;
}) {
  if (val === undefined || !stats || stats.max <= stats.min) return null;
  const pct = (n: number) => Math.max(4, Math.min(96, ((n - stats.min) / (stats.max - stats.min)) * 100));
  return (
    <span className="range-track" title={`Catalog range ${stats.min.toFixed(2)}–${stats.max.toFixed(2)}, median ${stats.median.toFixed(2)}`}>
      <span className="range-line" />
      <span className="range-median" style={{ left: `${pct(stats.median)}%` }} />
      <span
        className={`range-dot${status === "pass" ? " pass" : status === "fail" ? " fail" : ""}`}
        style={{ left: `${pct(val)}%` }}
      />
    </span>
  );
}

export function CompareView({ onNavigateNode }: CompareViewProps) {
  const [variants, setVariants] = useState<GraphNode[]>([]);
  const [profiles, setProfiles] = useState<GraphNode[]>([]);
  const [leftId, setLeftId] = useState("product.andersen.100.single-hung-smartsun");
  const [rightId, setRightId] = useState("product.andersen.400.casement-certified-sample");
  const [profileId, setProfileId] = useState("req.iecc.cz5.fenestration");
  const [data, setData] = useState<CompareResponse | null>(null);

  useEffect(() => {
    Promise.all([
      api.nodes({ kind: "productVariant", limit: 100 }),
      api.nodes({ kind: "requirement", limit: 50 }),
    ]).then(([v, p]) => {
      const windowVars = v.items.filter(
        (n) => n.id.startsWith("product.andersen.") || n.id.startsWith("product.winco.")
      );
      setVariants(windowVars);
      setProfiles(p.items);
    });
  }, []);

  useEffect(() => {
    if (!leftId || !rightId) return;
    api.compare(leftId, rightId, profileId || undefined).then(setData).catch(() => {});
  }, [leftId, rightId, profileId]);

  const statusFor = (side: "left" | "right", prop: string) =>
    data?.profileCheck?.[side].find((e) => e.property === prop)?.status;

  return (
    <main className="compare-main">
      <div className="compare-controls">
        <div>
          <div className="compare-col-label">Left Specification</div>
          <select className="sku-select" value={leftId} onChange={(e) => setLeftId(e.target.value)}>
            {variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="compare-col-label">Right Specification</div>
          <select className="sku-select" value={rightId} onChange={(e) => setRightId(e.target.value)}>
            {variants.map((v) => (
              <option key={v.id} value={v.id}>
                {v.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <div className="compare-col-label">Climate Requirement Profile</div>
          <select className="sku-select" value={profileId} onChange={(e) => setProfileId(e.target.value)}>
            <option value="">None</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {data && (
        <>
          <table className="compare-table">
            <thead>
              <tr>
                <th style={{ width: "24%" }}>Property</th>
                <th style={{ width: "38%" }}>{data.left.label}</th>
                <th style={{ width: "38%" }}>{data.right.label}</th>
              </tr>
            </thead>
            <tbody>
              {data.facts.map((row) => {
                const lStatus = statusFor("left", row.property);
                const rStatus = statusFor("right", row.property);
                return (
                  <tr key={`${row.property}-${row.scope ?? ""}`}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "11px" }}>
                      {PROP_LABELS[row.property] ?? row.property}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "11.5px" }}>
                      <span className={row.left?.state ? "spec-unknown" : undefined}>
                        {formatStmt(row.left)}
                      </span>
                      <RangeDotPlot
                        val={row.left?.siQuantity?.value}
                        stats={row.catalogStats}
                        status={lStatus}
                      />
                      {lStatus === "pass" && <span className="stamp stamp-pass">Pass</span>}
                      {lStatus === "fail" && <span className="stamp stamp-fail">Fail</span>}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "11.5px" }}>
                      <span className={row.right?.state ? "spec-unknown" : undefined}>
                        {formatStmt(row.right)}
                      </span>
                      <RangeDotPlot
                        val={row.right?.siQuantity?.value}
                        stats={row.catalogStats}
                        status={rStatus}
                      />
                      {rStatus === "pass" && <span className="stamp stamp-pass">Pass</span>}
                      {rStatus === "fail" && <span className="stamp stamp-fail">Fail</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="diff-grid">
            <div>
              <h3 className="dossier-section-title">Unique to {data.left.label}</h3>
              <div className="diff-tag-row">
                {data.materials.onlyLeft.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className="diff-item"
                    onClick={() => onNavigateNode(m.id)}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <h3 className="dossier-section-title">Unique to {data.right.label}</h3>
              <div className="diff-tag-row">
                {data.materials.onlyRight.map((m) => (
                  <button
                    key={m.id}
                    type="button"
                    className="diff-item"
                    onClick={() => onNavigateNode(m.id)}
                  >
                    {m.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div>
            <h3 className="dossier-section-title">Shared Materials</h3>
            <div className="diff-tag-row">
              {data.materials.shared.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  className="diff-item"
                  onClick={() => onNavigateNode(m.id)}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </main>
  );
}
