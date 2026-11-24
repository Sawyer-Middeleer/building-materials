"""SQLite-backed integrity, convention, and archived-PDF citation auditor."""

from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re

try:
    import pypdf
except ImportError:
    pypdf = None

from .sources import asset_path
from .store import MaterialStore

_CORP_SUFFIXES = frozenset({"inc", "corp", "corporation", "llc", "ltd", "co", "company", "group"})
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _normalize_label(label: str) -> str:
    tokens = [t for t in _NON_ALNUM_RE.sub(" ", label.lower()).split() if t not in _CORP_SUFFIXES]
    return " ".join(tokens)


def run_audit(store: MaterialStore, assets: Path) -> dict:
    """Verify blob hashes, PDF page/locator claims, and modeling conventions over SQLite."""
    errors: list[dict] = []
    warnings: list[dict] = []

    def record(bucket: list[dict], code: str, message: str, *, node=None, statement=None, source=None, page=None):
        entry: dict = {"code": code, "message": message}
        if node:
            entry["nodeId"] = node["id"]
            entry["kind"] = node["kind"]
        if statement:
            entry["statementId"] = statement["id"]
        if source:
            entry["sourceId"] = source
        if page is not None:
            entry["page"] = page
        bucket.append(entry)

    all_node_rows = store.conn.execute("SELECT * FROM nodes ORDER BY id").fetchall()
    nodes = {n["id"]: n for n in store._hydrate_nodes(all_node_rows)}
    all_stmt_rows = store.conn.execute("SELECT * FROM statements ORDER BY id").fetchall()
    statements = store._hydrate_statements(all_stmt_rows)
    guide_props = {r["property"] for r in store.conn.execute("SELECT property FROM property_guides")}

    outgoing: dict[str, list[dict]] = defaultdict(list)
    incoming: dict[str, list[dict]] = defaultdict(list)
    cited_sources: set[str] = set()
    for stmt in statements:
        outgoing[stmt["subject"]].append(stmt)
        if "target" in stmt:
            incoming[stmt["target"]].append(stmt)
        for ev in stmt["evidence"]:
            cited_sources.add(ev["source"])

    seen_source_keys: dict[tuple[str, str], str] = {}
    seen_norm_labels: dict[tuple[str, str], str] = {}
    seen_variant_sigs: dict[str, str] = {}
    pdf_readers: dict[str, object] = {}

    for nid in sorted(nodes):
        node = nodes[nid]
        kind = node["kind"]
        out = outgoing[nid]
        inc = incoming[nid]

        if kind != "source":
            norm_lbl = _normalize_label(node["label"])
            if norm_lbl:
                lbl_key = (kind, norm_lbl)
                if lbl_key in seen_norm_labels:
                    record(
                        warnings,
                        "possible-duplicate-label",
                        f"Normalized label collides with '{seen_norm_labels[lbl_key]}'",
                        node=node,
                    )
                else:
                    seen_norm_labels[lbl_key] = nid

        if kind == "source":
            meta = node["source"]
            digest = meta.get("sha256")
            if digest:
                key = (meta["origin"], digest)
                if key in seen_source_keys:
                    record(
                        errors,
                        "duplicate-source-sha",
                        f"Duplicate source manifest for same origin and sha256 (also {seen_source_keys[key]})",
                        node=node,
                    )
                else:
                    seen_source_keys[key] = nid
                snapshot = asset_path(assets, digest, meta["mediaType"])
                if snapshot.is_file():
                    actual = hashlib.sha256(snapshot.read_bytes()).hexdigest()
                    if actual != digest:
                        record(errors, "source-hash-mismatch", "Archived blob sha256 does not match source metadata", node=node)
                    elif meta["mediaType"] == "application/pdf" and pypdf is not None:
                        try:
                            pdf_readers[nid] = pypdf.PdfReader(snapshot)
                        except Exception as exc:
                            record(errors, "pdf-unreadable", f"Archived PDF could not be parsed: {exc}", node=node)
            if nid not in cited_sources:
                record(warnings, "unused-source", "Source node is not cited by any statement", node=node)
            continue

        if not out and not inc:
            record(errors, "orphan-node", "Node has no incoming or outgoing statements", node=node)

        if kind == "referenceDesign":
            has_mat = any(r.get("predicate") == "madeOf" for r in out)
            realized_by_variant = any(
                r.get("predicate") == "realizesDesign" and nodes[r["subject"]]["kind"] == "productVariant"
                for r in inc
            )
            if has_mat and realized_by_variant:
                record(
                    errors,
                    "shared-slot-contamination",
                    "Shared referenceDesign slot carries madeOf directly while realized by productVariants",
                    node=node,
                )
        elif kind == "productModel":
            if not any(r.get("predicate") == "manufacturedBy" for r in out):
                record(errors, "model-missing-manufacturer", "productModel has no manufacturedBy actor", node=node)
        elif kind == "productVariant":
            if not any(r.get("predicate") == "realizesDesign" for r in out):
                record(errors, "variant-missing-design", "productVariant has no realizesDesign link", node=node)
            has_model = any(r.get("predicate") in {"isVariantOf", "usesProduct"} for r in out)
            is_subpart = any(
                r.get("predicate") == "hasPart" and nodes[r["subject"]]["kind"] == "productVariant"
                for r in inc
            )
            if not has_model and not is_subpart:
                record(warnings, "variant-missing-model", "productVariant has no isVariantOf or usesProduct link", node=node)
            parent_models = sorted(r["target"] for r in out if r.get("predicate") == "isVariantOf")
            if parent_models:
                mats = sorted(r["target"] for r in out if r.get("predicate") == "madeOf")
                direct_props = sorted(
                    (
                        r["property"],
                        r.get("scope") or "",
                        json.dumps(r.get("quantity") or r.get("value") or r.get("state"), sort_keys=True),
                    )
                    for r in out
                    if "property" in r and not r.get("inheritedFrom")
                )
                if mats or direct_props:
                    sig = json.dumps({"model": parent_models[0], "mats": mats, "props": direct_props}, sort_keys=True)
                    if sig in seen_variant_sigs:
                        record(
                            warnings,
                            "possible-duplicate-variant",
                            f"Variant has identical materials and properties to '{seen_variant_sigs[sig]}'",
                            node=node,
                        )
                    else:
                        seen_variant_sigs[sig] = nid
        elif kind == "requirement":
            if not any(r.get("predicate") == "appliesTo" for r in out):
                record(errors, "requirement-missing-target", "requirement has no appliesTo target", node=node)

    if pypdf is None and any(
        n["kind"] == "source" and n["source"]["mediaType"] == "application/pdf" for n in nodes.values()
    ):
        record(warnings, "pdf-parser-missing", "Install pypdf to verify PDF page bounds and locators")

    page_text_cache: dict[tuple[str, int], str] = {}
    word_nums = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}

    def get_page_text(sid: str, pg: int) -> str:
        key = (sid, pg)
        if key not in page_text_cache:
            raw = pdf_readers[sid].pages[pg - 1].extract_text() or ""
            norm = " ".join(raw.lower().split())
            page_text_cache[key] = re.sub(r"(\d)\s*\.\s*(\d)", r"\1.\2", norm)
        return page_text_cache[key]

    def number_in_text(val: float, txt: str) -> bool:
        cands = set()
        if float(val).is_integer():
            iv = int(val)
            cands.update([str(iv), f"{iv:,}", f"{val:.1f}", f"{val:.2f}"])
            if iv in word_nums:
                cands.add(word_nums[iv])
        else:
            s = f"{val:g}"
            cands.update([s, f"{val:.1f}", f"{val:.2f}", f"{val:.3f}", f"{val:,.1f}", f"{val:,.2f}"])
            if s.startswith("0."):
                cands.add(s[1:])
        cands.update([f"{val:.2e}".lower(), f"{val:.1e}".lower()])
        return any(c in txt for c in cands)

    checked_props: set[str] = set()
    for row in statements:
        # Inherited statements share origin evidence already audited on their parent productModel.
        if row.get("inheritedFrom"):
            continue

        pred = row.get("predicate")
        if pred in {"uses", "produces", "performedBy"} and not (row.get("qualifiers") or {}).get("role"):
            record(errors, "process-missing-role", f"'{pred}' link is missing qualifiers.role", statement=row)

        if "property" in row:
            prop = row["property"]
            if prop not in guide_props and prop not in checked_props:
                record(errors, "property-missing-guide", f"Property '{prop}' has no companion guide entry", statement=row)
                checked_props.add(prop)
            if "quantity" in row and not row.get("scope"):
                record(warnings, "property-missing-scope", f"Numeric property '{prop}' has no scope", statement=row)

        qty = row.get("quantity") or (row.get("qualifiers") or {}).get("quantity")
        qty_vals = ([qty["value"]] if "value" in qty else [qty["min"], qty["max"]]) if qty else []

        for ev in row["evidence"]:
            sid = ev["source"]
            loc = ev["locator"]
            reader = pdf_readers.get(sid)
            if reader is None or "page" not in loc:
                continue
            pg = loc["page"]
            if pg < 1 or pg > len(reader.pages):
                record(
                    errors,
                    "pdf-page-out-of-bounds",
                    f"Cited page {pg} exceeds PDF length ({len(reader.pages)} pages)",
                    statement=row,
                    source=sid,
                    page=pg,
                )
                continue
            txt = get_page_text(sid, pg)
            for v in qty_vals:
                if not number_in_text(v, txt):
                    record(
                        warnings,
                        "quantity-not-on-page",
                        f"Numeric value {v} not found in extracted text of page {pg}",
                        statement=row,
                        source=sid,
                        page=pg,
                    )
            if "quote" in loc and " ".join(loc["quote"].lower().split()) not in txt:
                record(
                    warnings,
                    "quote-not-on-page",
                    f"Cited quote not found on page {pg}",
                    statement=row,
                    source=sid,
                    page=pg,
                )
            for key in ("table", "figure"):
                if key in loc:
                    tokens = [
                        w.strip('().,:/-"')
                        for w in loc[key].lower().split()
                        if len(w.strip('().,:/-"')) >= 3
                    ]
                    if tokens and not all(
                        any(t in txt for t in (tok, tok.rstrip("s"))) for tok in tokens[:2]
                    ):
                        record(
                            warnings,
                            "locator-not-on-page",
                            f"Cited {key} '{loc[key]}' not found on page {pg}",
                            statement=row,
                            source=sid,
                            page=pg,
                        )

    return {
        "ok": len(errors) == 0,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "pdfsChecked": len(pdf_readers),
            "citedPagesChecked": len(page_text_cache),
        },
        "errors": errors,
        "warnings": warnings,
    }
