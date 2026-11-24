import { useEffect, useMemo, useState } from "react";
import {
  api,
  sourcePdfUrl,
  type GraphNode,
  type PropertyGuide,
  type Statement,
  type WalkResponse,
} from "./api/client";
import { PaperGround } from "./components/PaperGround";
import {
  PlotterPlate3D,
  type CameraPreset,
  type MaterialArchetype,
  type PlateMode,
} from "./components/PlotterPlate3D";
import { LocatorDiagram } from "./components/LocatorDiagram";
import { SkuRadarChart, type SkuMetricPoint } from "./components/SkuRadarChart";
import { IndexDrawer } from "./components/IndexDrawer";
import { CompareView } from "./components/CompareView";

type ViewMode = "atlas" | "compare";

const GENERIC_WINDOW_ID = "envelope.openings.window";

const SWATCH_HEX: Record<string, string> = {
  White: "#f4f3ee",
  Sandtone: "#c7bca9",
  Terratone: "#6f6457",
  "Dark Bronze": "#3a322c",
  Black: "#1c1b1a",
};

const ID_LABELS: Record<string, string> = {
  masterformat: "MasterFormat",
  uniformat2: "Uniformat",
  epd: "EPD",
  nfrc: "NFRC",
  cas: "CAS",
  ifc: "IFC",
};

const PROP_ORDER = [
  "uFactor",
  "solarHeatGainCoefficient",
  "visibleLightTransmittance",
  "structuralDesignPressure",
  "airInfiltration",
  "performanceClass",
  "gwp",
];

const PROP_NAMES: Record<string, string> = {
  uFactor: "U-Factor",
  solarHeatGainCoefficient: "SHGC",
  visibleLightTransmittance: "Visible Light",
  structuralDesignPressure: "Design Pressure",
  airInfiltration: "Air Infiltration",
  performanceClass: "Performance Class",
  gwp: "Embodied Carbon",
  installedCostPerArea: "Installed Cost",
  serviceLife: "Service Life",
  correctedEmissivity: "Emissivity",
  thermalConductivity: "Thermal Cond.",
  density: "Density",
};

const SCALE_STOPS = [
  { id: "building", label: "Building", target: "building" },
  { id: "envelope", label: "Envelope", target: "envelope" },
  { id: "window", label: "Window", target: GENERIC_WINDOW_ID },
  { id: "material", label: "Material", target: "material.fibrex-composite" },
  { id: "atomic", label: "Atomic", target: "material.soda-lime-glass" },
];

// Canonical 1-to-1 architectural parts on the Window 3D plate
const WINDOW_SLOTS: {
  partId: string;
  label: string;
  partNodeId: string;
  roleMatchers: string[];
}[] = [
  {
    partId: "frame",
    label: "Frame",
    partNodeId: "envelope.openings.window.frame",
    roleMatchers: ["frame", "cladding", "thermal break"],
  },
  {
    partId: "sash",
    label: "Sash",
    partNodeId: "envelope.openings.window.sash",
    roleMatchers: ["sash", "frame"],
  },
  {
    partId: "outer-pane",
    label: "Outer Pane",
    partNodeId: "envelope.openings.window.outer-pane",
    roleMatchers: ["glazing substrate", "coating", "substrate"],
  },
  {
    partId: "spacer",
    label: "IGU Spacer",
    partNodeId: "envelope.openings.window.spacer",
    roleMatchers: ["spacer", "cavity gas", "primary seal", "secondary seal"],
  },
  {
    partId: "inner-pane",
    label: "Inner Pane",
    partNodeId: "envelope.openings.window.inner-pane",
    roleMatchers: ["glazing substrate", "substrate"],
  },
  {
    partId: "weatherstripping",
    label: "Weatherstrip",
    partNodeId: "envelope.openings.window.weatherstripping",
    roleMatchers: ["weatherstrip"],
  },
  {
    partId: "hardware",
    label: "Hardware",
    partNodeId: "envelope.openings.window.hardware",
    roleMatchers: ["hardware", "lock", "hinge"],
  },
];

const ATOMIC_SLOTS: { partId: string; label: string; nodeId: string }[] = [
  { partId: "chem.si", label: "Silicon (Si)", nodeId: "chem.si" },
  { partId: "chem.o", label: "Bridging Oxygen (O)", nodeId: "chem.o" },
  { partId: "chem.na-ion", label: "Alkali Modifier (Na+)", nodeId: "chem.na-ion" },
  { partId: "chem.ca-ion", label: "Stabilizer (Ca2+)", nodeId: "chem.ca-ion" },
];

const VERIFIED_PLATES: Record<string, { src: string; caption: string }> = {
  "product.andersen.100-series": {
    src: "/plates/andersen-fibrex.png",
    caption: "Fibrex extruded corner cutaway · Andersen 100 Series Guide, p. 6",
  },
  "material.fibrex-composite": {
    src: "/plates/andersen-fibrex.png",
    caption: "Fibrex composite profile · Andersen 100 Series Guide, p. 6",
  },
  "product.vitro.solarban-70": {
    src: "/plates/vitro-solarban70.png",
    caption: "Solarban 70 architectural glazing · Vitro Datasheet, p. 1",
  },
};

function inferMaterialArchetype(nodeId: string): MaterialArchetype {
  if (nodeId.startsWith("product.andersen.100")) return "fibrex";
  if (nodeId.startsWith("product.andersen.400")) return "clad-wood";
  if (nodeId.startsWith("product.winco.")) return "aluminum";
  return "generic";
}

function inferPlateMode(node: GraphNode | null): PlateMode | null {
  if (!node) return null;
  if (
    node.id === "material.soda-lime-glass" ||
    node.id === "structure.amorphous-silicate-network" ||
    node.id === "chem.si" ||
    node.id === "chem.o" ||
    node.id === "chem.na-ion" ||
    node.id === "chem.ca-ion" ||
    node.id === "chem.sio2"
  ) {
    return "atomic";
  }
  if (
    node.id.startsWith(GENERIC_WINDOW_ID) ||
    node.id.startsWith("product.andersen.") ||
    node.id.startsWith("product.winco.")
  ) {
    return "window";
  }
  return null;
}

function inferScaleId(node: GraphNode | null): string {
  if (!node) return "window";
  if (node.id === "building") return "building";
  if (node.id === "envelope" || node.id === "envelope.openings") return "envelope";
  if (
    node.kind === "chemicalEntity" ||
    node.kind === "structureModel" ||
    node.id === "material.soda-lime-glass"
  ) {
    return "atomic";
  }
  if (node.kind === "material") return "material";
  return "window";
}

function formatFactValue(s: Statement): string {
  if (s.state) return "Not published";
  if (s.value !== undefined) return String(s.value);
  if (s.quantity) {
    const q = s.quantity;
    const num = q.value !== undefined ? String(q.value) : `${q.min}–${q.max}`;
    return q.unit === "1" ? num : `${num} ${q.unit}`;
  }
  return "—";
}

interface ResolvedSlot {
  partId: string;
  label: string;
  partNode?: GraphNode;
  materialNode?: GraphNode;
  cas?: string;
  summary: string;
  drillId?: string;
}

export default function App() {
  const [view, setView] = useState<ViewMode>("atlas");
  const [indexOpen, setIndexOpen] = useState(false);

  // Anchor on Generic Window Assembly by default!
  const [activeId, setActiveId] = useState(GENERIC_WINDOW_ID);
  const [node, setNode] = useState<GraphNode | null>(null);
  const [windowProducts, setWindowProducts] = useState<GraphNode[]>([]);
  const [variants, setVariants] = useState<GraphNode[]>([]);
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(null);
  const [facts, setFacts] = useState<Statement[]>([]);
  const [partsWalk, setPartsWalk] = useState<WalkResponse | null>(null);
  const [traceWalk, setTraceWalk] = useState<WalkResponse | null>(null);
  const [manufacturer, setManufacturer] = useState<GraphNode | null>(null);
  const [sourcesMap, setSourcesMap] = useState<Record<string, GraphNode>>({});
  const [skuMetrics, setSkuMetrics] = useState<SkuMetricPoint[]>([]);
  const [propGuides, setPropGuides] = useState<Record<string, PropertyGuide>>({});
  const [hoveredProp, setHoveredProp] = useState<string | null>(null);

  // 3D plate controls — default Explode = 0% (assembled on refresh!)
  const [explode, setExplode] = useState(0);
  const [preset, setPreset] = useState<CameraPreset>("axon");
  const [presetTick, setPresetTick] = useState(0);
  const [selectedPartId, setSelectedPartId] = useState<string | null>("frame");

  // Load source catalog + window product lines once
  useEffect(() => {
    api
      .nodes({ kind: "source", limit: 100 })
      .then((res) => {
        const m: Record<string, GraphNode> = {};
        res.items.forEach((s) => (m[s.id] = s));
        setSourcesMap(m);
      })
      .catch(() => {});

    api
      .statements({ target: GENERIC_WINDOW_ID, predicate: "realizesDesign", limit: 100 })
      .then(async (res) => {
        const ids = Array.from(new Set(res.items.map((s) => s.subject)));
        const loaded = await Promise.all(ids.map((id) => api.node(id)));
        setWindowProducts(loaded.filter((n) => n.kind === "productModel"));
      })
      .catch(() => {});
  }, []);

  // Load active node + parts + trace + child variants
  useEffect(() => {
    let cancelled = false;
    setSelectedVariantId(null);
    setManufacturer(null);
    setVariants([]);

    Promise.all([
      api.node(activeId),
      api.parts(activeId),
      api.trace(activeId),
      api.facts(activeId),
      api.statements({ target: activeId, predicate: "isVariantOf", limit: 50 }),
    ])
      .then(async ([n, p, t, f, varStmts]) => {
        if (cancelled) return;
        setNode(n);
        setPartsWalk(p);
        setTraceWalk(t);
        setFacts(f.statements);

        const nextMode = inferPlateMode(n);
        if (nextMode === "atomic") {
          setSelectedPartId(n.kind === "chemicalEntity" ? n.id : "chem.na-ion");
        } else if (nextMode === "window") {
          setSelectedPartId("frame");
        } else {
          setSelectedPartId(null);
        }

        const mfgStmt = t.statements.find(
          (s) => s.predicate === "manufacturedBy" && s.subject === n.id
        );
        if (mfgStmt?.target) {
          const mNode =
            t.nodes.find((x) => x.id === mfgStmt.target) ?? (await api.node(mfgStmt.target));
          if (!cancelled) setManufacturer(mNode);
        }

        if (varStmts.items.length > 0) {
          const vIds = varStmts.items.map((s) => s.subject).slice(0, 24);
          const [vNodes, vFactsList] = await Promise.all([
            Promise.all(vIds.map((id) => api.node(id))),
            Promise.all(vIds.map((id) => api.facts(id))),
          ]);
          if (!cancelled) {
            setVariants(vNodes);
            setSelectedVariantId(vNodes[0]?.id ?? null);
            const pts: SkuMetricPoint[] = vNodes.map((vn, idx) => {
              const stmts = vFactsList[idx]?.statements ?? [];
              const num = (prop: string) =>
                stmts.find((s) => s.property === prop)?.quantity?.value;
              return {
                id: vn.id,
                label: vn.label,
                uFactor: num("uFactor"),
                shgc: num("solarHeatGainCoefficient"),
                vlt: num("visibleLightTransmittance"),
                dp: num("structuralDesignPressure"),
              };
            });
            setSkuMetrics(pts);
          }
        } else {
          setSkuMetrics([]);
        }
      })
      .catch(() => {});

    return () => {
      cancelled = true;
    };
  }, [activeId]);

  // When a SKU variant is chosen on a productModel, overlay its exact NFRC facts & madeOf materials
  useEffect(() => {
    if (!selectedVariantId) return;
    let cancelled = false;
    Promise.all([api.facts(selectedVariantId), api.parts(selectedVariantId)])
      .then(([f, p]) => {
        if (!cancelled) {
          setFacts(f.statements);
          setPartsWalk(p);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [selectedVariantId]);

  const plateMode = inferPlateMode(node);
  const activeScale = inferScaleId(node);

  // Deduplicated primary source links referenced by facts or node parameters
  const citedSources = useMemo(() => {
    const seen = new Map<string, { source: GraphNode; page?: string | number }>();
    const collect = (ev?: { source: string; locator: Record<string, string | number> }[]) => {
      for (const e of ev ?? []) {
        const sNode = sourcesMap[e.source];
        if (sNode && !seen.has(sNode.id)) {
          seen.set(sNode.id, { source: sNode, page: e.locator?.page });
        }
      }
    };
    facts.forEach((f) => collect(f.evidence));
    partsWalk?.statements.forEach((s) => collect(s.evidence));
    if (node?.parameters) {
      Object.values(node.parameters).forEach((p) => collect(p.evidence));
    }
    return Array.from(seen.values()).slice(0, 4);
  }, [facts, partsWalk, node, sourcesMap]);

  // 1-to-1 resolved slots for the bottom legend AND the in-place component inspector!
  const resolvedSlots: ResolvedSlot[] = useMemo(() => {
    if (!partsWalk) return [];
    const nodeMap = new Map(partsWalk.nodes.map((n) => [n.id, n]));

    if (plateMode === "atomic") {
      return ATOMIC_SLOTS.map((slot) => {
        const chem = nodeMap.get(slot.nodeId);
        const cas = chem?.identifiers?.find((i) => i.namespace === "cas")?.value;
        return {
          partId: slot.partId,
          label: slot.label,
          materialNode: chem,
          cas,
          summary: chem?.guide?.summary ?? "Atomic species in the disordered silicate glass network.",
          drillId: chem?.id,
        };
      });
    }

    if (plateMode === "window") {
      const madeOfStmts = partsWalk.statements.filter((s) => s.predicate === "madeOf" && s.target);
      return WINDOW_SLOTS.map((slot) => {
        const partNode = nodeMap.get(slot.partNodeId);
        // Find the most specific madeOf link matching this part (prefer variant/product subject over generic)
        let matchedStmt: Statement | undefined;
        for (const matcher of slot.roleMatchers) {
          const hits = madeOfStmts.filter((s) => {
            const role = (s.qualifiers?.role ?? "").toLowerCase();
            return s.subject === slot.partNodeId || role.includes(matcher);
          });
          if (hits.length > 0) {
            matchedStmt =
              hits.find((h) => h.subject.startsWith("product.")) ??
              hits.find((h) => h.subject === slot.partNodeId) ??
              hits[0];
            break;
          }
        }
        const mat = matchedStmt?.target ? nodeMap.get(matchedStmt.target) : undefined;
        const cas = mat?.identifiers?.find((i) => i.namespace === "cas")?.value;
        return {
          partId: slot.partId,
          label: slot.label,
          partNode,
          materialNode: mat,
          cas,
          summary:
            mat?.guide?.summary ??
            partNode?.guide?.summary ??
            "Material varies by product archetype; choose a product line above to inspect.",
          drillId: mat?.id,
        };
      });
    }

    return [];
  }, [partsWalk, plateMode]);

  const activeSlot = useMemo(
    () => resolvedSlots.find((s) => s.partId === selectedPartId) ?? null,
    [resolvedSlots, selectedPartId]
  );

  // Hydrate full node guide + chemistry/process detail for the currently selected plate component
  const [selectedDetail, setSelectedDetail] = useState<GraphNode | null>(null);
  const [selectedChems, setSelectedChems] = useState<{ id: string; label: string; cas?: string; share?: string }[]>([]);
  const [selectedProcess, setSelectedProcess] = useState<string | null>(null);

  useEffect(() => {
    const targetId = activeSlot?.materialNode?.id ?? activeSlot?.partNode?.id;
    if (!targetId) {
      setSelectedDetail(null);
      setSelectedChems([]);
      setSelectedProcess(null);
      return;
    }
    let cancelled = false;
    Promise.all([api.node(targetId), api.parts(targetId), api.trace(targetId)])
      .then(([n, p, t]) => {
        if (cancelled) return;
        setSelectedDetail(n);
        const nmap = new Map(p.nodes.map((x) => [x.id, x]));
        const chems: { id: string; label: string; cas?: string; share?: string }[] = [];
        const seen = new Set<string>();
        for (const s of p.statements) {
          if (
            (s.predicate === "hasComposition" || s.predicate === "includesChemical") &&
            s.target &&
            !seen.has(s.target)
          ) {
            const cn = nmap.get(s.target);
            if (!cn) continue;
            seen.add(cn.id);
            const cas = cn.identifiers?.find((i) => i.namespace === "cas")?.value;
            const qty = s.qualifiers?.quantity;
            const share = qty?.value !== undefined ? `${qty.value}${qty.unit}` : undefined;
            chems.push({ id: cn.id, label: cn.label, cas, share });
          }
        }
        setSelectedChems(chems.slice(0, 4));
        const prodProc = t.nodes.find((x) => x.kind === "process" && x.stage === "fabrication");
        setSelectedProcess(prodProc?.label ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [activeSlot?.materialNode?.id, activeSlot?.partNode?.id]);

  // Display facts sorted cleanly
  const displayFacts = useMemo(() => {
    const byProp = new Map<string, Statement>();
    for (const f of facts) {
      if (f.property && !byProp.has(f.property)) byProp.set(f.property, f);
    }
    const ordered: Statement[] = [];
    for (const k of PROP_ORDER) {
      const hit = byProp.get(k);
      if (hit) {
        ordered.push(hit);
        byProp.delete(k);
      }
    }
    for (const rest of byProp.values()) ordered.push(rest);
    return ordered.slice(0, 6);
  }, [facts]);

  const finishColors = (node?.parameters?.finishColor?.values ?? []).map(String);
  const jambDepth = node?.parameters?.jambDepth?.values?.[0];
  const uniformatCode = node?.identifiers?.find((i) => i.namespace === "uniformat2")?.value;
  const visibleIds = (node?.identifiers ?? []).filter((i) => i.namespace !== "uniformat2");

  const ensurePropGuide = (propKey: string) => {
    if (propGuides[propKey]) return;
    api
      .explain(propKey)
      .then((res) => {
        if (res.guide) {
          setPropGuides((prev) => ({ ...prev, [propKey]: res.guide }));
        }
      })
      .catch(() => {});
  };

  const materialArchetype = inferMaterialArchetype(activeId);
  const verifiedPlate = VERIFIED_PLATES[activeId];

  const displayName = useMemo(() => {
    if (!node) return "";
    if (
      manufacturer &&
      node.label.toLowerCase().startsWith(manufacturer.label.split(" ")[0].toLowerCase())
    ) {
      return node.label.slice(manufacturer.label.split(" ")[0].length).trim();
    }
    return node.label;
  }, [node, manufacturer]);

  const processes = useMemo(() => {
    if (!traceWalk) return [];
    return traceWalk.nodes.filter((n) => n.kind === "process");
  }, [traceWalk]);

  return (
    <>
      <PaperGround />
      <div className="app-shell">
        {/* Top Running Folio Bar */}
        <header className="folio-bar">
          <button
            type="button"
            className="folio-brand"
            onClick={() => {
              setView("atlas");
              setActiveId(GENERIC_WINDOW_ID);
            }}
          >
            <span>Anatomy of a Building</span>
          </button>

          <nav className="folio-scale-trail" aria-label="Scale navigation">
            {SCALE_STOPS.map((stop, idx) => (
              <span
                key={stop.id}
                style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}
              >
                {idx > 0 && <span className="scale-dot">·</span>}
                <button
                  type="button"
                  className={`scale-stop${view === "atlas" && activeScale === stop.id ? " active" : ""}`}
                  onClick={() => {
                    setView("atlas");
                    setActiveId(stop.target);
                  }}
                >
                  {stop.label}
                </button>
              </span>
            ))}
          </nav>

          <div className="folio-actions">
            <button type="button" className="folio-link" onClick={() => setIndexOpen(true)}>
              Search
            </button>
            <button
              type="button"
              className={`folio-link${view === "compare" ? " active" : ""}`}
              onClick={() => setView(view === "compare" ? "atlas" : "compare")}
            >
              Compare
            </button>
          </div>
        </header>

        {/* Right Spine-Edge Vertical INDEX Tab */}
        <aside className="spine-rail">
          <button type="button" className="spine-tab-btn" onClick={() => setIndexOpen(true)}>
            <span className="spine-tick" />
            <span>Index</span>
          </button>
        </aside>

        {/* Main Content */}
        {view === "compare" ? (
          <CompareView
            onNavigateNode={(id) => {
              setActiveId(id);
              setView("atlas");
            }}
          />
        ) : (
          <main className="spread-main">
            {/* LEFT COLUMN */}
            <section className="spread-left">
              <div className="title-block">
                <div className="manufacturer-eyebrow">
                  <span className="manufacturer-name">
                    {manufacturer
                      ? manufacturer.label
                      : activeId === GENERIC_WINDOW_ID
                        ? "Generic Reference Assembly"
                        : node?.kind ?? ""}
                  </span>
                  {jambDepth !== undefined && <span>Jamb {jambDepth} in</span>}
                </div>

                <h1 className="display-title">
                  {uniformatCode && <span className="display-title-code">{uniformatCode} /</span>}
                  <span className="display-title-name">{displayName}</span>
                </h1>

                {visibleIds.length > 0 && (
                  <div className="meta-strip">
                    {visibleIds.map((ident) => (
                      <span key={`${ident.namespace}:${ident.value}`}>
                        <span className="meta-item-label">
                          {ID_LABELS[ident.namespace] ?? ident.namespace}
                        </span>
                        {ident.value}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Anchored Generic Window -> Product Line -> SKU Selector */}
              {plateMode === "window" && (
                <div className="sku-strip">
                  <div className={variants.length > 0 ? "selector-grid" : undefined}>
                    <div>
                      <div className="sku-strip-head">
                        <span>Product Line</span>
                      </div>
                      <select
                        className="sku-select"
                        value={
                          windowProducts.some((p) => p.id === activeId)
                            ? activeId
                            : GENERIC_WINDOW_ID
                        }
                        onChange={(e) => setActiveId(e.target.value)}
                      >
                        <option value={GENERIC_WINDOW_ID}>Generic Window Assembly</option>
                        {windowProducts.map((p) => (
                          <option key={p.id} value={p.id}>
                            {p.label}
                          </option>
                        ))}
                      </select>
                    </div>

                    {variants.length > 0 && (
                      <div>
                        <div className="sku-strip-head">
                          <span>SKU ({variants.length})</span>
                        </div>
                        <select
                          className="sku-select"
                          value={selectedVariantId ?? ""}
                          onChange={(e) => setSelectedVariantId(e.target.value)}
                        >
                          {variants.map((v) => (
                            <option key={v.id} value={v.id}>
                              {v.label}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>

                  {finishColors.length > 0 && (
                    <div className="swatch-row">
                      {finishColors.map((c) => (
                        <span key={c} className="swatch-item">
                          <span
                            className="swatch-chip"
                            style={{ backgroundColor: SWATCH_HEX[c] ?? "#d8d3c8" }}
                          />
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Dual-color Editorial Summary + Dotted-Rule Spec Table */}
              <div className="editorial-spec-grid">
                <p className="vermilion-quote">
                  {node?.guide?.tradeoffs ?? node?.guide?.summary ?? node?.description ?? ""}
                </p>

                <table className="spec-table">
                  <tbody>
                    {displayFacts.map((f) => {
                      const uPass =
                        f.property === "uFactor" &&
                        f.quantity?.value !== undefined &&
                        f.quantity.value <= 0.25;
                      const uFail =
                        f.property === "uFactor" &&
                        f.quantity?.value !== undefined &&
                        f.quantity.value > 0.25;
                      const propKey = f.property ?? "";
                      const guide = propGuides[propKey];
                      return (
                        <tr key={f.id}>
                          <th>
                            <span
                              className="prop-tip-wrap"
                              tabIndex={0}
                              onMouseEnter={() => {
                                setHoveredProp(propKey);
                                ensurePropGuide(propKey);
                              }}
                              onMouseLeave={() => setHoveredProp(null)}
                              onFocus={() => {
                                setHoveredProp(propKey);
                                ensurePropGuide(propKey);
                              }}
                              onBlur={() => setHoveredProp(null)}
                            >
                              {PROP_NAMES[propKey] ?? propKey}
                              {hoveredProp === propKey && guide && (
                                <span className="prop-tip-card" role="tooltip">
                                  <div className="prop-tip-title">
                                    {guide.title ?? PROP_NAMES[propKey] ?? propKey}
                                  </div>
                                  <p className="prop-tip-body">{guide.summary}</p>
                                  {guide.betterDirection && (
                                    <p className="prop-tip-dir">{guide.betterDirection}</p>
                                  )}
                                </span>
                              )}
                            </span>
                          </th>
                          <td className={f.state ? "spec-unknown" : undefined}>
                            {formatFactValue(f)}
                            {uPass && <span className="stamp stamp-pass">CZ5 Pass</span>}
                            {uFail && <span className="stamp stamp-fail">CZ5 Fail</span>}
                          </td>
                        </tr>
                      );
                    })}
                    {node?.guide?.chemistry &&
                      Object.entries(node.guide.chemistry).map(([k, v]) => (
                        <tr key={k}>
                          <th>{k}</th>
                          <td>{String(v)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>

              {/* Visual Summary Band: Minimalist SKU Spider Chart + Authentic Extracted PDF Plate */}
              {(skuMetrics.length > 1 || verifiedPlate) && (
                <div className="visual-summary-band">
                  {skuMetrics.length > 1 && (
                    <SkuRadarChart
                      skus={skuMetrics}
                      selectedId={selectedVariantId}
                      onSelectSku={(id) => setSelectedVariantId(id)}
                    />
                  )}
                  {verifiedPlate && (
                    <figure className="verified-plate-figure">
                      <img
                        className="verified-plate-img"
                        src={verifiedPlate.src}
                        alt={verifiedPlate.caption}
                      />
                      <figcaption className="verified-plate-cap">
                        {verifiedPlate.caption}
                      </figcaption>
                    </figure>
                  )}
                </div>
              )}

              {/* Direct Clickable Archived PDF Links */}
              {citedSources.length > 0 && (
                <div className="sources-row">
                  {citedSources.map(({ source, page }) => {
                    const href = sourcePdfUrl(source, page);
                    const label = `${source.label}${page ? ` · p. ${page}` : ""} ↗`;
                    return href ? (
                      <a
                        key={source.id}
                        className="source-link"
                        href={href}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {label}
                      </a>
                    ) : (
                      <span key={source.id} className="source-link">
                        {source.label}
                      </span>
                    );
                  })}
                </div>
              )}

              {/* Bottom-Left Locator Diagram + Breadcrumb */}
              <div className="locator-block">
                <LocatorDiagram
                  mode={plateMode === "atomic" ? "window" : "building"}
                  caption={
                    plateMode === "atomic" ? "Outer pane of window IGU" : "Envelope window opening"
                  }
                />
                <div className="locator-breadcrumb">
                  <button
                    type="button"
                    className="crumb-btn"
                    onClick={() => setActiveId("building")}
                  >
                    Building
                  </button>
                  <span>›</span>
                  <button
                    type="button"
                    className="crumb-btn"
                    onClick={() => setActiveId("envelope")}
                  >
                    Envelope
                  </button>
                  <span>›</span>
                  <button
                    type="button"
                    className="crumb-btn"
                    onClick={() => setActiveId(GENERIC_WINDOW_ID)}
                  >
                    Window
                  </button>
                  {plateMode === "atomic" && (
                    <>
                      <span>›</span>
                      <button
                        type="button"
                        className="crumb-btn"
                        onClick={() => setActiveId("material.soda-lime-glass")}
                      >
                        Soda-Lime Glass
                      </button>
                    </>
                  )}
                </div>
              </div>
            </section>

            {/* RIGHT COLUMN: Hairline-Framed Interactive Plotter Plate */}
            <section className="spread-right">
              <div className="plate-frame">
                <div className="plate-header">
                  {plateMode ? (
                    <>
                      <div className="plate-controls">
                        {(["axon", "section", "plan"] as CameraPreset[]).map((p) => (
                          <button
                            key={p}
                            type="button"
                            className={`plate-ctrl-btn${preset === p ? " active" : ""}`}
                            onClick={() => {
                              setPreset(p);
                              setPresetTick((t) => t + 1);
                            }}
                          >
                            {p === "axon" ? "Axonometric" : p === "section" ? "Section" : "Plan"}
                          </button>
                        ))}
                      </div>
                      <label className="explode-control">
                        <span>Explode</span>
                        <input
                          className="explode-slider"
                          type="range"
                          min={0}
                          max={1}
                          step={0.01}
                          value={explode}
                          onChange={(e) => setExplode(parseFloat(e.target.value))}
                        />
                        <span>{Math.round(explode * 100)}%</span>
                      </label>
                    </>
                  ) : (
                    <span>{node?.kind}</span>
                  )}
                  <span>
                    {plateMode === "atomic"
                      ? "Scale 1 nm"
                      : plateMode === "window"
                        ? "Scale 1:5"
                        : ""}
                  </span>
                </div>

                {plateMode ? (
                  <PlotterPlate3D
                    mode={plateMode}
                    materialArchetype={materialArchetype}
                    selectedPartId={selectedPartId}
                    onSelectPart={(partId) => {
                      // Inspect in-place — never unexpectedly navigate away!
                      setSelectedPartId(partId);
                    }}
                    explode={explode}
                    preset={preset}
                    presetTick={presetTick}
                  />
                ) : (
                  <div className="dossier-plate-body">
                    {node?.guide?.howItWorks && (
                      <div>
                        <h3 className="dossier-section-title">Mechanism</h3>
                        <p style={{ margin: 0, maxWidth: "62ch", color: "var(--ink-mid)" }}>
                          {node.guide.howItWorks}
                        </p>
                      </div>
                    )}
                    {processes.length > 0 && (
                      <div>
                        <h3 className="dossier-section-title">Upstream Value Chain</h3>
                        <div className="chain-list">
                          {processes.map((proc) => (
                            <button
                              key={proc.id}
                              type="button"
                              className="chain-step"
                              onClick={() => setActiveId(proc.id)}
                            >
                              <div className="chain-stage">{proc.stage}</div>
                              <div className="chain-label">{proc.label}</div>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Additive Selected Component Deep-Dive Strip (no duplicate cards — adds chemistry, process, and primary drill-down!) */}
                {activeSlot && (
                  <div className="plate-detail-strip">
                    <div>
                      <div className="plate-detail-eyebrow">{activeSlot.label}</div>
                      <h2 className="plate-detail-title">
                        {activeSlot.materialNode
                          ? activeSlot.materialNode.label
                          : "Varies by product line"}
                      </h2>
                      <p className="plate-detail-summary">
                        {selectedDetail?.guide?.summary ?? activeSlot.summary}
                      </p>
                    </div>

                    <div className="plate-detail-chem">
                      {selectedChems.length > 0 ? (
                        <>
                          <div className="plate-detail-chem-label">Composition &amp; CAS</div>
                          <div className="plate-detail-chem-list">
                            {selectedChems.map((c) => (
                              <span key={c.id}>
                                {c.label}
                                {c.share ? ` (${c.share})` : ""}
                                {c.cas ? ` · ${c.cas}` : ""}
                              </span>
                            ))}
                          </div>
                        </>
                      ) : activeSlot.cas ? (
                        <>
                          <div className="plate-detail-chem-label">Identifier</div>
                          <div className="plate-detail-chem-list">
                            <span>CAS {activeSlot.cas}</span>
                          </div>
                        </>
                      ) : selectedProcess ? (
                        <>
                          <div className="plate-detail-chem-label">Fabrication</div>
                          <div className="plate-detail-chem-list">
                            <span>{selectedProcess}</span>
                          </div>
                        </>
                      ) : (
                        <>
                          <div className="plate-detail-chem-label">Specification</div>
                          <div className="plate-detail-chem-list">
                            <span>Select a product line on the left to resolve material &amp; CAS</span>
                          </div>
                        </>
                      )}
                    </div>

                    <div>
                      {activeSlot.drillId && activeSlot.drillId !== activeId ? (
                        <button
                          type="button"
                          className="plate-drill-btn"
                          onClick={() => setActiveId(activeSlot.drillId!)}
                        >
                          {plateMode === "atomic" ? "Open Species →" : "Inspect Material →"}
                        </button>
                      ) : (
                        <button type="button" className="plate-drill-btn" disabled>
                          Generic Slot
                        </button>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* Plate Footer: Graphic Scale Bar */}
              <div className="plate-footer">
                <span>
                  {plateMode
                    ? "Drag to rotate · Scroll to zoom · Click any layer or card to inspect"
                    : node?.id ?? ""}
                </span>
                {plateMode && (
                  <div className="scale-bar-wrap">
                    <span>{plateMode === "atomic" ? "0 — 1.0 nm" : "1:5 · 0 — 100 mm"}</span>
                    <div className="scale-bar" aria-hidden="true">
                      <span />
                      <span />
                      <span />
                      <span />
                    </div>
                  </div>
                )}
              </div>
            </section>
          </main>
        )}
      </div>

      <IndexDrawer
        open={indexOpen}
        activeId={activeId}
        onClose={() => setIndexOpen(false)}
        onSelect={(id) => {
          setActiveId(id);
          setView("atlas");
        }}
      />
    </>
  );
}
