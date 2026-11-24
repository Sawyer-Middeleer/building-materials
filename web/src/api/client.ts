export interface Identifier {
  namespace: string;
  value: string;
}

export interface EvidenceRef {
  source: string;
  locator: Record<string, string | number>;
}

export interface Quantity {
  value?: number;
  min?: number;
  max?: number;
  unit: string;
  basis?: string;
}

export interface Statement {
  id: string;
  subject: string;
  basis: string;
  predicate?: string;
  target?: string;
  property?: string;
  value?: string | boolean;
  quantity?: Quantity;
  siQuantity?: Quantity;
  state?: "unknown" | "withheld";
  scope?: string;
  method?: string;
  conditions?: string;
  geography?: string;
  pcr?: string;
  validUntil?: string;
  plantActor?: string;
  inheritedFrom?: string;
  qualifiers?: {
    role?: string;
    position?: string;
    interface?: string;
    sequence?: number;
    quantity?: Quantity;
  };
  evidence: EvidenceRef[];
}

export interface NodeGuide {
  summary: string;
  howItWorks?: string;
  tradeoffs?: string;
  chemistry?: Record<string, string | number>;
  firm?: Record<string, string>;
}

export interface GraphNode {
  id: string;
  kind:
    | "referenceDesign"
    | "productModel"
    | "productVariant"
    | "material"
    | "structureModel"
    | "chemicalEntity"
    | "process"
    | "requirement"
    | "actor"
    | "source";
  label: string;
  description?: string;
  revision?: string;
  scale?: string;
  stage?: string;
  identifiers?: Identifier[];
  parameters?: Record<
    string,
    {
      values?: (string | number)[];
      min?: number;
      max?: number;
      step?: number;
      unit?: string;
      evidence: EvidenceRef[];
    }
  >;
  source?: {
    origin: string;
    mediaType: string;
    issuer?: string;
    sha256?: string;
    retrievedAt?: string;
  };
  guide?: NodeGuide;
}

export interface NodesResponse {
  total: number;
  limit: number;
  offset: number;
  items: GraphNode[];
}

export interface WalkResponse {
  root: GraphNode;
  nodes: GraphNode[];
  statements: Statement[];
}

export interface FactsResponse {
  node: GraphNode;
  statements: Statement[];
}

export interface CompareFactRow {
  property: string;
  scope: string | null;
  left: Statement | null;
  right: Statement | null;
  leftBand: { label: string; meaning: string } | null;
  rightBand: { label: string; meaning: string } | null;
  catalogStats: {
    count: number;
    unit: string;
    min: number;
    median: number;
    max: number;
  } | null;
}

export interface ProfileCheckEntry {
  property: string;
  scope: string | null;
  status: "pass" | "fail" | "unknown" | "missing";
  limit?: Quantity;
  actual?: Quantity;
}

export interface CompareResponse {
  left: GraphNode;
  right: GraphNode;
  facts: CompareFactRow[];
  materials: { shared: GraphNode[]; onlyLeft: GraphNode[]; onlyRight: GraphNode[] };
  parts: { shared: GraphNode[]; onlyLeft: GraphNode[]; onlyRight: GraphNode[] };
  processes: { shared: GraphNode[]; onlyLeft: GraphNode[]; onlyRight: GraphNode[] };
  profileCheck?: {
    profile: GraphNode;
    left: ProfileCheckEntry[];
    right: ProfileCheckEntry[];
  };
}

export interface HealthResponse {
  ok: boolean;
  nodes: number;
  statements: number;
  citations: number;
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export interface PropertyGuide {
  title?: string;
  summary: string;
  betterDirection?: string;
  whyItMatters?: string;
  typicalRange?: string;
}

export interface ExplainResponse {
  kind: string;
  property?: string;
  guide: PropertyGuide;
}

export const api = {
  health: () => fetchJson<HealthResponse>("/api/health"),
  explain: (key: string) => fetchJson<ExplainResponse>(`/api/explain/${encodeURIComponent(key)}`),
  nodes: (params: Record<string, string | number | undefined> = {}) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    }
    const query = qs.toString();
    return fetchJson<NodesResponse>(`/api/nodes${query ? `?${query}` : ""}`);
  },
  node: (id: string) => fetchJson<GraphNode>(`/api/nodes/${encodeURIComponent(id)}`),
  parts: (id: string) => fetchJson<WalkResponse>(`/api/nodes/${encodeURIComponent(id)}/parts`),
  trace: (id: string) => fetchJson<WalkResponse>(`/api/nodes/${encodeURIComponent(id)}/trace`),
  facts: (id: string) => fetchJson<FactsResponse>(`/api/nodes/${encodeURIComponent(id)}/facts`),
  statements: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== "") qs.set(k, String(v));
    }
    return fetchJson<{ total: number; items: Statement[] }>(`/api/statements?${qs.toString()}`);
  },
  compare: (left: string, right: string, profile?: string) => {
    const qs = new URLSearchParams({ left, right });
    if (profile) qs.set("profile", profile);
    return fetchJson<CompareResponse>(`/api/compare?${qs.toString()}`);
  },
};

export function sourcePdfUrl(sourceNode: GraphNode | undefined, page?: string | number): string | null {
  if (!sourceNode?.source) return null;
  const { sha256, mediaType, origin } = sourceNode.source;
  const ext = mediaType === "application/pdf" ? ".pdf" : "";
  const base = sha256 && ext ? `/assets/${sha256}${ext}` : origin;
  return page ? `${base}#page=${page}` : base;
}
