import { useEffect, useState } from "react";
import { api, type GraphNode } from "../api/client";

interface IndexDrawerProps {
  open: boolean;
  activeId: string;
  onClose: () => void;
  onSelect: (nodeId: string) => void;
}

const KINDS: { key: string; label: string }[] = [
  { key: "", label: "All" },
  { key: "referenceDesign", label: "Assemblies" },
  { key: "productModel", label: "Products" },
  { key: "material", label: "Materials" },
  { key: "chemicalEntity", label: "Chemistry" },
  { key: "process", label: "Processes" },
];

export function IndexDrawer({ open, activeId, onClose, onSelect }: IndexDrawerProps) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [items, setItems] = useState<GraphNode[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .nodes({
          q: query.trim() || undefined,
          kind: kind || undefined,
          limit: 120,
        })
        .then((res) => {
          if (!cancelled) {
            setItems(res.items.filter((n) => n.kind !== "source" && n.kind !== "actor"));
            setTotal(res.total);
          }
        })
        .catch(() => {});
    }, 120);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [open, query, kind]);

  if (!open) return null;

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="index-drawer" aria-label="Graph Index">
        <div className="drawer-header">
          <span>Index ({total})</span>
          <button type="button" className="folio-link" onClick={onClose}>
            Close ×
          </button>
        </div>

        <input
          className="drawer-search"
          type="search"
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter assemblies, products, materials, CAS..."
        />

        <div className="drawer-filters">
          {KINDS.map((k) => (
            <button
              key={k.key || "all"}
              type="button"
              className={`plate-ctrl-btn${kind === k.key ? " active" : ""}`}
              onClick={() => setKind(k.key)}
            >
              {k.label}
            </button>
          ))}
        </div>

        <div className="drawer-list">
          {items.map((node) => (
            <button
              key={node.id}
              type="button"
              className={`drawer-row${node.id === activeId ? " active" : ""}`}
              onClick={() => {
                onSelect(node.id);
                onClose();
              }}
            >
              <span className="drawer-row-label">{node.label}</span>
              <span className="drawer-row-kind">{node.kind}</span>
            </button>
          ))}
        </div>
      </aside>
    </>
  );
}
