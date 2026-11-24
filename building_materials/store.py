"""SQLite v2 primary runtime store: atomic build, staleness guard, FTS5 search, and queries."""

from collections import defaultdict, deque
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import statistics
from tempfile import NamedTemporaryFile
from urllib.parse import urlsplit, urlunsplit

from .compiler import compile_dir, compute_data_fingerprint
from .model import (
    COMPOSITION,
    CompiledBundle,
    GAP_TIERS,
    ROOT,
    TRACE_FORWARD,
    TRACE_REVERSE,
    USED_BY,
)
from .sources import asset_path
from .validator import validate_bundle

FTS_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def build_db(bundle: CompiledBundle, db_path: Path) -> dict:
    """Materialize a validated CompiledBundle atomically into a SQLite v2 database."""
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    schema_sql = (ROOT / "schema.sql").read_text(encoding="utf-8")

    with NamedTemporaryFile(dir=target.parent, suffix=".tmp.db", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    conn = sqlite3.connect(tmp_path)
    try:
        conn.executescript(schema_sql)
        citation_count = 0
        guide_nodes = bundle.guide.get("nodes") or {}
        guide_props = bundle.guide.get("properties") or {}
        guide_params = bundle.guide.get("parameters") or {}
        guide_ifaces = bundle.guide.get("interfaces") or {}

        with conn:
            for node in bundle.nodes:
                nid = node["id"]
                prov = bundle.provenance.get(nid)
                conn.execute(
                    """INSERT INTO nodes (
                           id, kind, label, description, revision, scale, stage,
                           parameters_json, expected_profile_json, source_file
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        nid,
                        node["kind"],
                        node["label"],
                        node.get("description"),
                        node.get("revision"),
                        node.get("scale"),
                        node.get("stage"),
                        json.dumps(node["parameters"]) if "parameters" in node else None,
                        json.dumps(node["expectedProfile"]) if "expectedProfile" in node else None,
                        prov.file if prov else None,
                    ),
                )
                if src := node.get("source"):
                    conn.execute(
                        """INSERT INTO sources (
                               node_id, origin, media_type, issuer, issued_on,
                               retrieved_at, retrieved_on, valid_until, sha256
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            nid,
                            src["origin"],
                            src["mediaType"],
                            src.get("issuer"),
                            src.get("issuedOn"),
                            src.get("retrievedAt"),
                            src.get("retrievedOn"),
                            src.get("validUntil"),
                            src.get("sha256"),
                        ),
                    )
                ident_tokens = []
                for ident in node.get("identifiers", ()):
                    conn.execute(
                        "INSERT INTO node_identifiers (node_id, namespace, value) VALUES (?, ?, ?)",
                        (nid, ident["namespace"], ident["value"]),
                    )
                    ident_tokens.append(f"{ident['namespace']} {ident['value']}")

                g_summary = ""
                if g := guide_nodes.get(nid):
                    g_summary = g["summary"]
                    conn.execute(
                        """INSERT INTO node_guides (
                               node_id, summary, how_it_works, why_it_matters,
                               tradeoffs, steps_json, chemistry_json, firm_json
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            nid,
                            g["summary"],
                            g.get("howItWorks"),
                            g.get("whyItMatters"),
                            g.get("tradeoffs"),
                            json.dumps(g["steps"]) if "steps" in g else None,
                            json.dumps(g["chemistry"]) if "chemistry" in g else None,
                            json.dumps(g["firm"]) if "firm" in g else None,
                        ),
                    )

                conn.execute(
                    "INSERT INTO nodes_fts (node_id, label, description, identifiers, guide_summary) VALUES (?, ?, ?, ?, ?)",
                    (
                        nid,
                        node["label"],
                        node.get("description") or "",
                        " ".join(ident_tokens),
                        g_summary,
                    ),
                )

            for prop_key, pg in guide_props.items():
                conn.execute(
                    """INSERT INTO property_guides (
                           property, title, summary, better_direction,
                           typical_range, why_it_matters, ucum_unit, external_refs_json, bands_json
                       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        prop_key,
                        pg["title"],
                        pg["summary"],
                        pg.get("betterDirection"),
                        pg.get("typicalRange"),
                        pg.get("whyItMatters"),
                        pg.get("ucumUnit"),
                        json.dumps(pg["externalRefs"]) if "externalRefs" in pg else None,
                        json.dumps(pg["bands"]) if "bands" in pg else None,
                    ),
                )

            for param_key, pmg in guide_params.items():
                conn.execute(
                    """INSERT INTO parameter_guides (parameter, title, shape, role, unit, summary)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        param_key,
                        pmg.get("title"),
                        pmg["shape"],
                        pmg["role"],
                        pmg.get("unit"),
                        pmg["summary"],
                    ),
                )

            for iface_key, ig in guide_ifaces.items():
                conn.execute(
                    """INSERT INTO interface_guides (interface, title, summary, typical_mates_json)
                       VALUES (?, ?, ?, ?)""",
                    (
                        iface_key,
                        ig.get("title"),
                        ig["summary"],
                        json.dumps(ig["typicalMates"]) if "typicalMates" in ig else None,
                    ),
                )

            for stmt in bundle.statements:
                sid = stmt["id"]
                prov = bundle.provenance.get(sid)
                qty = stmt.get("quantity") or {}
                si = stmt.get("siQuantity") or {}
                qual = stmt.get("qualifiers") or {}
                q_qty = qual.get("quantity") or {}

                val = stmt.get("value")
                if val is None:
                    val_text, val_type = None, None
                elif isinstance(val, bool):
                    val_text, val_type = ("true" if val else "false"), "boolean"
                else:
                    val_text, val_type = str(val), "string"

                conn.execute(
                    """INSERT INTO statements (
                           id, subject_id, predicate, target_id, property,
                           value_text, value_type,
                           quantity_value, quantity_min, quantity_max, quantity_unit, quantity_basis,
                           si_value, si_min, si_max, si_unit,
                           state, scope, method, conditions,
                           geography, pcr, valid_until, plant_actor_id,
                           basis, qual_role, qual_position, qual_interface, qual_sequence,
                           qual_qty_value, qual_qty_min, qual_qty_max, qual_qty_unit, qual_qty_basis,
                           inherited_from, source_file
                       ) VALUES (
                           ?, ?, ?, ?, ?,
                           ?, ?,
                           ?, ?, ?, ?, ?,
                           ?, ?, ?, ?,
                           ?, ?, ?, ?,
                           ?, ?, ?, ?,
                           ?, ?, ?, ?, ?,
                           ?, ?, ?, ?, ?,
                           ?, ?
                       )""",
                    (
                        sid,
                        stmt["subject"],
                        stmt.get("predicate"),
                        stmt.get("target"),
                        stmt.get("property"),
                        val_text,
                        val_type,
                        qty.get("value"),
                        qty.get("min"),
                        qty.get("max"),
                        qty.get("unit"),
                        qty.get("basis"),
                        si.get("value"),
                        si.get("min"),
                        si.get("max"),
                        si.get("unit"),
                        stmt.get("state"),
                        stmt.get("scope"),
                        stmt.get("method"),
                        stmt.get("conditions"),
                        stmt.get("geography"),
                        stmt.get("pcr"),
                        stmt.get("validUntil"),
                        stmt.get("plantActor"),
                        stmt["basis"],
                        qual.get("role"),
                        qual.get("position"),
                        qual.get("interface"),
                        qual.get("sequence"),
                        q_qty.get("value"),
                        q_qty.get("min"),
                        q_qty.get("max"),
                        q_qty.get("unit"),
                        q_qty.get("basis"),
                        stmt.get("inheritedFrom"),
                        prov.file if prov else None,
                    ),
                )
                for ev in stmt["evidence"]:
                    loc = ev["locator"]
                    conn.execute(
                        """INSERT INTO citations (
                               statement_id, source_id, page, section, table_name,
                               row_name, column_name, figure, anchor, quote
                           ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            sid,
                            ev["source"],
                            loc.get("page"),
                            loc.get("section"),
                            loc.get("table"),
                            loc.get("row"),
                            loc.get("column"),
                            loc.get("figure"),
                            loc.get("anchor"),
                            loc.get("quote"),
                        ),
                    )
                    citation_count += 1

            for stmt in bundle.statements:
                for dep in stmt.get("derivedFrom", ()):
                    conn.execute(
                        "INSERT INTO statement_derivations (statement_id, derived_from) VALUES (?, ?)",
                        (stmt["id"], dep),
                    )

            built_at = datetime.now(UTC).isoformat()
            meta_rows = [
                ("schema_version", "2"),
                ("data_fingerprint", bundle.fingerprint),
                ("built_at", built_at),
                ("node_count", str(len(bundle.nodes))),
                ("statement_count", str(len(bundle.statements))),
                ("citation_count", str(citation_count)),
                ("guide_node_count", str(len(guide_nodes))),
                ("guide_property_count", str(len(guide_props))),
            ]
            conn.executemany("INSERT INTO build_meta (key, value) VALUES (?, ?)", meta_rows)
    except BaseException:
        conn.close()
        tmp_path.unlink(missing_ok=True)
        raise
    conn.close()

    os.replace(tmp_path, target)
    return {
        "db": str(target.resolve()),
        "schemaVersion": 2,
        "fingerprint": bundle.fingerprint,
        "builtAt": built_at,
        "nodes": len(bundle.nodes),
        "statements": len(bundle.statements),
        "citations": citation_count,
        "guideNodes": len(guide_nodes),
        "guideProperties": len(guide_props),
    }


def _read_db_fingerprint(db_path: Path) -> str | None:
    if not db_path.is_file():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT value FROM build_meta WHERE key = 'data_fingerprint'"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except sqlite3.Error:
        return None


def ensure_db(
    data_dir: Path,
    db_path: Path,
    *,
    force: bool = False,
    auto_rebuild: bool = True,
) -> Path:
    """Return a fresh SQLite DB path, atomically rebuilding if missing or stale."""
    if not auto_rebuild:
        if not db_path.is_file():
            raise FileNotFoundError(f"Database not found (and --no-rebuild is set): {db_path}")
        return db_path

    current_fp = compute_data_fingerprint(data_dir)
    if not force and _read_db_fingerprint(db_path) == current_fp:
        return db_path

    bundle = validate_bundle(compile_dir(data_dir))
    build_db(bundle, db_path)
    return db_path


def _sanitize_fts_query(raw: str) -> str | None:
    tokens = FTS_TOKEN_RE.findall(raw or "")
    if not tokens:
        return None
    return " AND ".join(f'"{tok}"*' for tok in tokens)


class MaterialStore:
    """Read-only SQLite v2 query engine for the building materials graph."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path).resolve()
        self.conn = sqlite3.connect(
            f"file:{self.db_path.as_posix()}?mode=ro",
            uri=True,
        )
        self.conn.row_factory = sqlite3.Row

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "MaterialStore":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def meta(self) -> dict:
        rows = self.conn.execute("SELECT key, value FROM build_meta").fetchall()
        data = {r["key"]: r["value"] for r in rows}
        return {
            "schemaVersion": int(data.get("schema_version", "2")),
            "fingerprint": data.get("data_fingerprint", ""),
            "builtAt": data.get("built_at", ""),
            "counts": {
                "nodes": int(data.get("node_count", "0")),
                "statements": int(data.get("statement_count", "0")),
                "citations": int(data.get("citation_count", "0")),
                "guideNodes": int(data.get("guide_node_count", "0")),
                "guideProperties": int(data.get("guide_property_count", "0")),
            },
        }

    def _hydrate_nodes(self, rows: list[sqlite3.Row], *, include_guide: bool = False) -> list[dict]:
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        ph = ",".join("?" * len(ids))

        sources_map: dict[str, dict] = {}
        for sr in self.conn.execute(f"SELECT * FROM sources WHERE node_id IN ({ph})", ids):
            src: dict = {"origin": sr["origin"], "mediaType": sr["media_type"]}
            for col, key in (
                ("issuer", "issuer"),
                ("issued_on", "issuedOn"),
                ("retrieved_at", "retrievedAt"),
                ("retrieved_on", "retrievedOn"),
                ("valid_until", "validUntil"),
                ("sha256", "sha256"),
            ):
                if sr[col] is not None:
                    src[key] = sr[col]
            sources_map[sr["node_id"]] = src

        idents_map: dict[str, list[dict]] = defaultdict(list)
        for ir in self.conn.execute(
            f"SELECT node_id, namespace, value FROM node_identifiers WHERE node_id IN ({ph}) ORDER BY namespace, value",
            ids,
        ):
            idents_map[ir["node_id"]].append({"namespace": ir["namespace"], "value": ir["value"]})

        guides_map: dict[str, dict] = {}
        if include_guide:
            for gr in self.conn.execute(f"SELECT * FROM node_guides WHERE node_id IN ({ph})", ids):
                guides_map[gr["node_id"]] = self._row_to_node_guide(gr)

        result = []
        for r in rows:
            nid = r["id"]
            node: dict = {"id": nid, "kind": r["kind"], "label": r["label"]}
            for col in ("description", "revision", "scale", "stage"):
                if r[col] is not None:
                    node[col] = r[col]
            if r["parameters_json"] is not None:
                node["parameters"] = json.loads(r["parameters_json"])
            if r["expected_profile_json"] is not None:
                node["expectedProfile"] = json.loads(r["expected_profile_json"])
            if nid in idents_map:
                node["identifiers"] = idents_map[nid]
            if nid in sources_map:
                node["source"] = sources_map[nid]
            if include_guide and nid in guides_map:
                node["guide"] = guides_map[nid]
            result.append(node)
        return result

    def _row_to_node_guide(self, gr: sqlite3.Row) -> dict:
        g: dict = {"summary": gr["summary"]}
        for col, key in (
            ("how_it_works", "howItWorks"),
            ("why_it_matters", "whyItMatters"),
            ("tradeoffs", "tradeoffs"),
        ):
            if gr[col] is not None:
                g[key] = gr[col]
        for col, key in (
            ("steps_json", "steps"),
            ("chemistry_json", "chemistry"),
            ("firm_json", "firm"),
        ):
            if gr[col] is not None:
                g[key] = json.loads(gr[col])
        return g

    def _row_to_property_guide(self, pr: sqlite3.Row) -> dict:
        g: dict = {"title": pr["title"], "summary": pr["summary"]}
        for col, key in (
            ("better_direction", "betterDirection"),
            ("typical_range", "typicalRange"),
            ("why_it_matters", "whyItMatters"),
            ("ucum_unit", "ucumUnit"),
        ):
            if pr[col] is not None:
                g[key] = pr[col]
        if pr["external_refs_json"] is not None:
            g["externalRefs"] = json.loads(pr["external_refs_json"])
        if pr["bands_json"] is not None:
            g["bands"] = json.loads(pr["bands_json"])
        return g

    def _hydrate_statements(self, rows: list[sqlite3.Row]) -> list[dict]:
        if not rows:
            return []
        ids = [r["id"] for r in rows]
        ph = ",".join("?" * len(ids))

        cites_map: dict[str, list[dict]] = defaultdict(list)
        for cr in self.conn.execute(f"SELECT * FROM citations WHERE statement_id IN ({ph})", ids):
            loc: dict = {}
            for col, key in (
                ("page", "page"),
                ("section", "section"),
                ("table_name", "table"),
                ("row_name", "row"),
                ("column_name", "column"),
                ("figure", "figure"),
                ("anchor", "anchor"),
                ("quote", "quote"),
            ):
                if cr[col] is not None:
                    loc[key] = cr[col]
            cites_map[cr["statement_id"]].append({"source": cr["source_id"], "locator": loc})

        derivs_map: dict[str, list[str]] = defaultdict(list)
        for dr in self.conn.execute(
            f"SELECT statement_id, derived_from FROM statement_derivations WHERE statement_id IN ({ph})",
            ids,
        ):
            derivs_map[dr["statement_id"]].append(dr["derived_from"])

        result = []
        for r in rows:
            sid = r["id"]
            stmt: dict = {"id": sid, "subject": r["subject_id"], "basis": r["basis"]}
            if r["predicate"] is not None:
                stmt["predicate"] = r["predicate"]
                stmt["target"] = r["target_id"]
            else:
                stmt["property"] = r["property"]
                if r["value_text"] is not None:
                    stmt["value"] = (r["value_text"] == "true") if r["value_type"] == "boolean" else r["value_text"]
                elif r["quantity_unit"] is not None:
                    qty: dict = {"unit": r["quantity_unit"]}
                    if r["quantity_value"] is not None:
                        qty["value"] = r["quantity_value"]
                    else:
                        qty["min"] = r["quantity_min"]
                        qty["max"] = r["quantity_max"]
                    if r["quantity_basis"] is not None:
                        qty["basis"] = r["quantity_basis"]
                    stmt["quantity"] = qty
                elif r["state"] is not None:
                    stmt["state"] = r["state"]

            if r["si_unit"] is not None:
                si: dict = {"unit": r["si_unit"]}
                if r["si_value"] is not None:
                    si["value"] = r["si_value"]
                else:
                    si["min"] = r["si_min"]
                    si["max"] = r["si_max"]
                stmt["siQuantity"] = si

            for col, key in (
                ("scope", "scope"),
                ("method", "method"),
                ("conditions", "conditions"),
                ("geography", "geography"),
                ("pcr", "pcr"),
                ("valid_until", "validUntil"),
                ("plant_actor_id", "plantActor"),
                ("inherited_from", "inheritedFrom"),
            ):
                if r[col] is not None:
                    stmt[key] = r[col]

            qual: dict = {}
            if r["qual_role"] is not None:
                qual["role"] = r["qual_role"]
            if r["qual_position"] is not None:
                qual["position"] = r["qual_position"]
            if r["qual_interface"] is not None:
                qual["interface"] = r["qual_interface"]
            if r["qual_sequence"] is not None:
                qual["sequence"] = r["qual_sequence"]
            if r["qual_qty_unit"] is not None:
                q_qty: dict = {"unit": r["qual_qty_unit"]}
                if r["qual_qty_value"] is not None:
                    q_qty["value"] = r["qual_qty_value"]
                else:
                    q_qty["min"] = r["qual_qty_min"]
                    q_qty["max"] = r["qual_qty_max"]
                if r["qual_qty_basis"] is not None:
                    q_qty["basis"] = r["qual_qty_basis"]
                qual["quantity"] = q_qty
            if qual:
                stmt["qualifiers"] = qual

            stmt["evidence"] = cites_map.get(sid, [])
            if sid in derivs_map:
                stmt["derivedFrom"] = derivs_map[sid]
            result.append(stmt)
        return result

    def get_node(self, node_id: str, *, include_guide: bool = True) -> dict:
        row = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown node ID: {node_id}")
        return self._hydrate_nodes([row], include_guide=include_guide)[0]

    def list_nodes(
        self,
        *,
        kind: str | None = None,
        prefix: str | None = None,
        namespace: str | None = None,
        identifier: str | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        clauses = []
        params: list = []
        joins = []

        if kind:
            clauses.append("n.kind = ?")
            params.append(kind)
        if prefix:
            clauses.append("(n.id = ? OR n.id LIKE ?)")
            params.extend([prefix, f"{prefix}.%"])
        if namespace or identifier:
            joins.append("JOIN node_identifiers ni ON ni.node_id = n.id")
            if namespace:
                clauses.append("ni.namespace = ?")
                params.append(namespace)
            if identifier:
                clauses.append("ni.value = ?")
                params.append(identifier)
        if q:
            fts_q = _sanitize_fts_query(q)
            if fts_q is None:
                return {"items": [], "total": 0, "limit": limit, "offset": offset, "hasMore": False}
            joins.append("JOIN nodes_fts fts ON fts.node_id = n.id")
            clauses.append("nodes_fts MATCH ?")
            params.append(fts_q)

        join_sql = " ".join(joins)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = self.conn.execute(
            f"SELECT COUNT(DISTINCT n.id) FROM nodes n {join_sql} {where_sql}", params
        ).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT DISTINCT n.* FROM nodes n {join_sql} {where_sql} ORDER BY n.id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items = self._hydrate_nodes(rows)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": offset + len(items) < total,
        }

    def search(self, query: str, *, kind: str | None = None, limit: int = 50, offset: int = 0) -> dict:
        fts_q = _sanitize_fts_query(query)
        if fts_q is None:
            return {"items": [], "total": 0, "limit": limit, "offset": offset, "hasMore": False}
        clauses = ["nodes_fts MATCH ?"]
        params: list = [fts_q]
        if kind:
            clauses.append("n.kind = ?")
            params.append(kind)
        where_sql = " AND ".join(clauses)
        total = self.conn.execute(
            f"SELECT COUNT(*) FROM nodes_fts fts JOIN nodes n ON n.id = fts.node_id WHERE {where_sql}",
            params,
        ).fetchone()[0]
        rows = self.conn.execute(
            f"""SELECT n.* FROM nodes_fts fts
                JOIN nodes n ON n.id = fts.node_id
                WHERE {where_sql}
                ORDER BY bm25(nodes_fts), n.id
                LIMIT ? OFFSET ?""",
            [*params, limit, offset],
        ).fetchall()
        items = self._hydrate_nodes(rows, include_guide=True)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": offset + len(items) < total,
        }

    def list_statements(
        self,
        *,
        subject: str | None = None,
        target: str | None = None,
        predicate: str | None = None,
        property: str | None = None,
        scope: str | None = None,
        basis: str | None = None,
        state: str | None = None,
        geography: str | None = None,
        active_on: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        clauses = []
        params: list = []
        for col, val in (
            ("subject_id", subject),
            ("target_id", target),
            ("predicate", predicate),
            ("property", property),
            ("scope", scope),
            ("basis", basis),
            ("state", state),
            ("geography", geography),
        ):
            if val is not None:
                clauses.append(f"{col} = ?")
                params.append(val)
        if active_on is not None:
            clauses.append("(valid_until IS NULL OR valid_until >= ?)")
            params.append(active_on)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        total = self.conn.execute(f"SELECT COUNT(*) FROM statements {where_sql}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT * FROM statements {where_sql} ORDER BY id LIMIT ? OFFSET ?",
            [*params, limit, offset],
        ).fetchall()
        items = self._hydrate_statements(rows)
        return {
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "hasMore": offset + len(items) < total,
        }

    def facts(self, node_id: str, *, include_inherited: bool = True) -> dict:
        subject = self.get_node(node_id, include_guide=False)
        sql = "SELECT * FROM statements WHERE subject_id = ? AND property IS NOT NULL"
        if not include_inherited:
            sql += " AND inherited_from IS NULL"
        sql += " ORDER BY id"
        rows = self.conn.execute(sql, (node_id,)).fetchall()
        return {"subject": subject, "statements": self._hydrate_statements(rows)}

    def _all_nodes_by_id(self, ids: set[str]) -> list[dict]:
        if not ids:
            return []
        ordered = sorted(ids)
        ph = ",".join("?" * len(ordered))
        rows = self.conn.execute(f"SELECT * FROM nodes WHERE id IN ({ph}) ORDER BY id", ordered).fetchall()
        return self._hydrate_nodes(rows)

    def _all_statements_by_id(self, ids: set[str]) -> list[dict]:
        if not ids:
            return []
        ordered = sorted(ids)
        ph = ",".join("?" * len(ordered))
        rows = self.conn.execute(f"SELECT * FROM statements WHERE id IN ({ph}) ORDER BY id", ordered).fetchall()
        return self._hydrate_statements(rows)

    def walk(self, node_id: str, *, trace: bool) -> dict:
        self.get_node(node_id, include_guide=False)
        pending = deque([node_id])
        seen: set[str] = set()
        selected: set[str] = set()
        forward = TRACE_FORWARD if trace else COMPOSITION
        reverse = TRACE_REVERSE if trace else set()

        while pending:
            current = pending.popleft()
            if current in seen:
                continue
            seen.add(current)

            for r in self.conn.execute(
                "SELECT id, predicate, target_id, property FROM statements WHERE subject_id = ?",
                (current,),
            ):
                if r["predicate"] in forward:
                    selected.add(r["id"])
                    pending.append(r["target_id"])
                elif r["property"] is not None:
                    selected.add(r["id"])

            if trace:
                for r in self.conn.execute(
                    """SELECT s.id, s.predicate, s.subject_id, n.stage
                       FROM statements s JOIN nodes n ON n.id = s.subject_id
                       WHERE s.target_id = ?""",
                    (current,),
                ):
                    if r["predicate"] in reverse or (
                        r["predicate"] == "uses"
                        and current == node_id
                        and r["stage"] != "fabrication"
                    ):
                        selected.add(r["id"])
                        pending.append(r["subject_id"])

        stmts = self._all_statements_by_id(selected)
        seen.update(ev["source"] for s in stmts for ev in s["evidence"])
        return {"root": node_id, "nodes": self._all_nodes_by_id(seen), "statements": stmts}

    def used_by(self, node_id: str) -> dict:
        self.get_node(node_id, include_guide=False)
        pending = deque([node_id])
        seen: set[str] = set()
        selected: set[str] = set()
        while pending:
            current = pending.popleft()
            if current in seen:
                continue
            seen.add(current)
            for r in self.conn.execute(
                "SELECT id, subject_id, predicate FROM statements WHERE target_id = ?",
                (current,),
            ):
                if r["predicate"] in USED_BY:
                    selected.add(r["id"])
                    pending.append(r["subject_id"])
        stmts = self._all_statements_by_id(selected)
        seen.update(ev["source"] for s in stmts for ev in s["evidence"])
        return {"root": node_id, "nodes": self._all_nodes_by_id(seen), "statements": stmts}

    def classify_band(self, property_name: str, si_value: float | None) -> dict | None:
        if si_value is None:
            return None
        row = self.conn.execute(
            "SELECT bands_json FROM property_guides WHERE property = ?", (property_name,)
        ).fetchone()
        if row is None or row["bands_json"] is None:
            return None
        for band in json.loads(row["bands_json"]):
            low = band.get("min")
            high = band.get("max")
            if (low is None or si_value >= low) and (high is None or si_value < high):
                return {"label": band["label"], "meaning": band["meaning"]}
        return None

    def catalog_stats(self, design_id: str, property_name: str, scope: str | None = None) -> dict | None:
        clauses = [
            "n.kind = 'productVariant'",
            "rd.predicate = 'realizesDesign'",
            "rd.target_id = ?",
            "s.property = ?",
            "s.si_value IS NOT NULL",
        ]
        params: list = [design_id, property_name]
        if scope is not None:
            clauses.append("s.scope = ?")
            params.append(scope)
        else:
            clauses.append("s.scope IS NULL")
        where_sql = " AND ".join(clauses)
        rows = self.conn.execute(
            f"""SELECT s.subject_id, s.si_value, s.si_unit
                FROM statements s
                JOIN nodes n ON n.id = s.subject_id
                JOIN statements rd ON rd.subject_id = n.id
                WHERE {where_sql}
                ORDER BY s.subject_id, s.id""",
            params,
        ).fetchall()
        by_variant: dict[str, tuple[float, str]] = {}
        for r in rows:
            by_variant.setdefault(r["subject_id"], (float(r["si_value"]), r["si_unit"]))
        if len(by_variant) < 2:
            return None
        units = {u for _, u in by_variant.values()}
        if len(units) != 1:
            return None
        vals = sorted(v for v, _ in by_variant.values())
        unit = next(iter(units))
        return {
            "count": len(vals),
            "unit": unit,
            "min": round(min(vals), 6),
            "median": round(float(statistics.median(vals)), 6),
            "max": round(max(vals), 6),
        }

    def _parent_model_id(self, node_id: str) -> str | None:
        row = self.conn.execute(
            "SELECT target_id FROM statements WHERE subject_id = ? AND predicate = 'isVariantOf' LIMIT 1",
            (node_id,),
        ).fetchone()
        return row["target_id"] if row else None

    def _collect_compatibility(self, node_id: str, parts_walk: dict) -> dict:
        model_id = self._parent_model_id(node_id)
        compat_subjects = [node_id] + ([model_id] if model_id else [])
        ph = ",".join("?" * len(compat_subjects))
        compat_rows = self.conn.execute(
            f"SELECT * FROM statements WHERE subject_id IN ({ph}) AND predicate = 'compatibleWith' ORDER BY id",
            compat_subjects,
        ).fetchall()

        mat_ids = [n["id"] for n in parts_walk["nodes"] if n["kind"] == "material"]
        incompat_ids = list(dict.fromkeys([*compat_subjects, *mat_ids]))
        ph2 = ",".join("?" * len(incompat_ids))
        incompat_rows = self.conn.execute(
            f"""SELECT * FROM statements
                WHERE predicate = 'incompatibleWith'
                  AND (subject_id IN ({ph2}) OR target_id IN ({ph2}))
                ORDER BY id""",
            [*incompat_ids, *incompat_ids],
        ).fetchall()
        return {
            "compatibleWith": self._hydrate_statements(compat_rows),
            "incompatibleWith": self._hydrate_statements(incompat_rows),
        }

    def _property_prefers_higher(self, prop: str) -> bool:
        row = self.conn.execute(
            "SELECT better_direction FROM property_guides WHERE property = ?", (prop,)
        ).fetchone()
        if row is None or not row["better_direction"]:
            return False
        return row["better_direction"].strip().lower().startswith("higher")

    def _evaluate_profile(self, profile_id: str, lfacts: dict, rfacts: dict) -> dict:
        profile_node = self.get_node(profile_id, include_guide=True)
        if profile_node["kind"] != "requirement":
            raise ValueError(f"Profile '{profile_id}' must be a requirement node (got {profile_node['kind']})")
        req_stmts = self.facts(profile_id)["statements"]

        def check_side(side_facts: dict) -> list[dict]:
            results = []
            for req in req_stmts:
                prop = req["property"]
                scope = req.get("scope") or ""
                limit_si_obj = req.get("siQuantity") or {}
                limit_si = limit_si_obj.get("value")
                actual_stmt = side_facts.get((prop, scope))
                actual_si = (actual_stmt.get("siQuantity") or {}).get("value") if actual_stmt else None
                if actual_si is None:
                    status = "unknown"
                elif "min" in limit_si_obj and "max" in limit_si_obj:
                    status = "pass" if limit_si_obj["min"] <= actual_si <= limit_si_obj["max"] else "fail"
                elif limit_si is None:
                    status = "unknown"
                elif self._property_prefers_higher(prop):
                    status = "pass" if actual_si >= limit_si else "fail"
                else:
                    status = "pass" if actual_si <= limit_si else "fail"
                results.append({
                    "property": prop,
                    "scope": scope or None,
                    "status": status,
                    "limit": req.get("quantity"),
                    "limitSi": req.get("siQuantity"),
                    "actual": actual_stmt.get("quantity") if actual_stmt else None,
                    "actualSi": actual_stmt.get("siQuantity") if actual_stmt else None,
                })
            return results

        return {
            "profile": profile_node,
            "left": check_side(lfacts),
            "right": check_side(rfacts),
        }

    def compare(self, left_id: str, right_id: str, *, profile_id: str | None = None) -> dict:
        left = self.get_node(left_id, include_guide=False)
        right = self.get_node(right_id, include_guide=False)
        left_parts = self.walk(left_id, trace=False)
        right_parts = self.walk(right_id, trace=False)
        left_trace = self.walk(left_id, trace=True)
        right_trace = self.walk(right_id, trace=True)

        def diff_nodes(lwalk: dict, rwalk: dict, kind: str) -> dict:
            lmap = {n["id"]: n for n in lwalk["nodes"] if n["kind"] == kind}
            rmap = {n["id"]: n for n in rwalk["nodes"] if n["kind"] == kind}
            return {
                "shared": [lmap[nid] for nid in lmap if nid in rmap],
                "onlyLeft": [lmap[nid] for nid in lmap if nid not in rmap],
                "onlyRight": [rmap[nid] for nid in rmap if nid not in lmap],
            }

        def realizes_ids(root_id: str) -> list[str]:
            return [
                r["target_id"]
                for r in self.conn.execute(
                    "SELECT target_id FROM statements WHERE subject_id = ? AND predicate = 'realizesDesign'",
                    (root_id,),
                )
            ]

        l_designs = realizes_ids(left_id)
        r_designs = realizes_ids(right_id)
        shared_design = next((d for d in l_designs if d in r_designs), None)

        def collect_facts(root_id: str, designs: list[str]) -> dict[tuple[str, str], dict]:
            by_key: dict[tuple[str, str], dict] = {}
            for sid in [root_id, *designs]:
                for stmt in self.facts(sid)["statements"]:
                    key = (stmt["property"], stmt.get("scope") or "")
                    by_key.setdefault(key, stmt)
            return by_key

        lfacts = collect_facts(left_id, l_designs)
        rfacts = collect_facts(right_id, r_designs)
        keys = list(dict.fromkeys([*lfacts.keys(), *rfacts.keys()]))
        facts = []
        for prop, scope in keys:
            lf = lfacts.get((prop, scope))
            rf = rfacts.get((prop, scope))
            l_si = (lf.get("siQuantity") or {}).get("value") if lf else None
            r_si = (rf.get("siQuantity") or {}).get("value") if rf else None
            entry: dict = {
                "property": prop,
                "scope": scope or None,
                "left": lf,
                "right": rf,
                "leftBand": self.classify_band(prop, l_si),
                "rightBand": self.classify_band(prop, r_si),
                "catalogStats": self.catalog_stats(shared_design, prop, scope or None) if shared_design else None,
            }
            facts.append(entry)

        part_ids_l = {s["target"] for s in left_parts["statements"] if s.get("predicate") == "hasPart"}
        part_ids_r = {s["target"] for s in right_parts["statements"] if s.get("predicate") == "hasPart"}
        all_part_nodes = {n["id"]: n for n in [*left_parts["nodes"], *right_parts["nodes"]]}
        parts_diff = {
            "shared": [all_part_nodes[nid] for nid in sorted(part_ids_l & part_ids_r)],
            "onlyLeft": [all_part_nodes[nid] for nid in sorted(part_ids_l - part_ids_r)],
            "onlyRight": [all_part_nodes[nid] for nid in sorted(part_ids_r - part_ids_l)],
        }

        def model_params(node: dict) -> dict | None:
            if "parameters" in node:
                return node["parameters"]
            mid = self._parent_model_id(node["id"])
            if mid:
                return self.get_node(mid, include_guide=False).get("parameters")
            return None

        result: dict = {
            "left": left,
            "right": right,
            "facts": facts,
            "parameters": {
                "left": model_params(left),
                "right": model_params(right),
            },
            "compatibility": {
                "left": self._collect_compatibility(left_id, left_parts),
                "right": self._collect_compatibility(right_id, right_parts),
            },
            "materials": diff_nodes(left_parts, right_parts, "material"),
            "parts": parts_diff,
            "processes": diff_nodes(left_trace, right_trace, "process"),
        }
        if profile_id:
            result["profileCheck"] = self._evaluate_profile(profile_id, lfacts, rfacts)
        return result

    def explain(self, key: str) -> dict:
        nr = self.conn.execute("SELECT * FROM node_guides WHERE node_id = ?", (key,)).fetchone()
        if nr is not None:
            return {
                "kind": "node",
                "node": self.get_node(key, include_guide=False),
                "guide": self._row_to_node_guide(nr),
            }
        pr = self.conn.execute("SELECT * FROM property_guides WHERE property = ?", (key,)).fetchone()
        if pr is not None:
            return {
                "kind": "property",
                "property": key,
                "guide": self._row_to_property_guide(pr),
            }
        pmr = self.conn.execute("SELECT * FROM parameter_guides WHERE parameter = ?", (key,)).fetchone()
        if pmr is not None:
            g: dict = {"shape": pmr["shape"], "role": pmr["role"], "summary": pmr["summary"]}
            if pmr["title"] is not None:
                g["title"] = pmr["title"]
            if pmr["unit"] is not None:
                g["unit"] = pmr["unit"]
            return {"kind": "parameter", "parameter": key, "guide": g}
        ir = self.conn.execute("SELECT * FROM interface_guides WHERE interface = ?", (key,)).fetchone()
        if ir is not None:
            g = {"summary": ir["summary"]}
            if ir["title"] is not None:
                g["title"] = ir["title"]
            if ir["typical_mates_json"] is not None:
                g["typicalMates"] = json.loads(ir["typical_mates_json"])
            return {"kind": "interface", "interface": key, "guide": g}
        raise ValueError(f"No guide entry for: {key}")

    def cite(self, statement_id: str, assets: Path) -> dict:
        row = self.conn.execute("SELECT * FROM statements WHERE id = ?", (statement_id,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown statement ID: {statement_id}")
        stmt = self._hydrate_statements([row])[0]
        evidence = []
        for citation in stmt["evidence"]:
            src = self.get_node(citation["source"], include_guide=False)
            meta = src["source"]
            origin = meta["origin"]
            digest = meta.get("sha256")
            snapshot = asset_path(assets, digest, meta["mediaType"]) if digest else None
            captured = snapshot is not None and snapshot.is_file()
            if captured and hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Snapshot hash mismatch for {src['id']}")
            href = snapshot.resolve().as_uri() if captured else origin
            locator = citation["locator"]
            fragment = f"page={locator['page']}" if "page" in locator else locator.get("anchor")
            if fragment:
                href = urlunsplit(urlsplit(href)._replace(fragment=fragment))
            evidence.append({
                "source": src,
                "locator": locator,
                "href": href,
                "capture": "saved" if captured else "link-only",
                **({"savedPath": str(snapshot.resolve())} if captured else {}),
            })
        return {"statement": stmt, "evidence": evidence}

    def gaps(
        self,
        assets: Path,
        node_id: str | None = None,
        *,
        tier: str = "assembly",
        category: str | None = None,
    ) -> dict:
        if tier not in GAP_TIERS:
            raise ValueError(f"Invalid tier '{tier}': expected one of {', '.join(GAP_TIERS)}")

        if node_id is not None:
            self.get_node(node_id, include_guide=False)
            p_nodes = {n["id"] for n in self.walk(node_id, trace=False)["nodes"]}
            t_nodes = {n["id"] for n in self.walk(node_id, trace=True)["nodes"]}
            scope_ids = p_nodes | t_nodes
        else:
            scope_ids = {r["id"] for r in self.conn.execute("SELECT id FROM nodes")}

        all_nodes = {n["id"]: n for n in self._all_nodes_by_id(scope_ids)}
        out_by: dict[str, list[dict]] = defaultdict(list)
        inc_by: dict[str, list[dict]] = defaultdict(list)
        all_stmt_rows = self.conn.execute("SELECT * FROM statements").fetchall()
        for stmt in self._hydrate_statements(all_stmt_rows):
            out_by[stmt["subject"]].append(stmt)
            if "target" in stmt:
                inc_by[stmt["target"]].append(stmt)

        items: list[dict] = []

        def add(cat: str, code: str, message: str, *, node: dict | None = None, statement: dict | None = None):
            if category and cat != category:
                return
            entry: dict = {"category": cat, "code": code, "message": message}
            if node:
                entry["nodeId"] = node["id"]
                entry["label"] = node["label"]
                entry["kind"] = node["kind"]
            if statement:
                entry["statementId"] = statement["id"]
            items.append(entry)

        stages_present: set[str] = set()
        for nid in sorted(scope_ids):
            node = all_nodes[nid]
            kind = node["kind"]
            out = out_by[nid]
            inc = inc_by[nid]

            # Tier 1: catalog checks (always run)
            if kind == "productModel":
                if not any(r.get("predicate") == "manufacturedBy" for r in out):
                    add("valueChain", "model-missing-manufacturer", "productModel has no manufacturedBy actor", node=node)
                for rd_link in out:
                    if rd_link.get("predicate") != "realizesDesign":
                        continue
                    rd = all_nodes.get(rd_link["target"])
                    ep = (rd or {}).get("expectedProfile") or {}
                    model_params = node.get("parameters") or {}
                    for expected_param in ep.get("parameters") or ():
                        if expected_param not in model_params:
                            add(
                                "properties",
                                "profile-missing-parameter",
                                f"productModel is missing expected parameter '{expected_param}' for {rd['id']}",
                                node=node,
                            )
                    if ep.get("properties"):
                        child_variants = [
                            r["subject"] for r in inc if r.get("predicate") == "isVariantOf"
                        ]
                        present_props = {r["property"] for r in out if "property" in r}
                        for cv_id in child_variants:
                            present_props.update(r["property"] for r in out_by[cv_id] if "property" in r)
                        for expected_prop in ep["properties"]:
                            if expected_prop not in present_props:
                                add(
                                    "properties",
                                    "profile-missing-property",
                                    f"productModel is missing expected property '{expected_prop}' for {rd['id']}",
                                    node=node,
                                )
            elif kind == "productVariant":
                if not any(r.get("predicate") == "isVariantOf" for r in out):
                    add("composition", "variant-missing-model", "productVariant has no isVariantOf productModel", node=node)
                if not any(r.get("predicate") == "realizesDesign" for r in out):
                    add("composition", "variant-missing-design", "productVariant has no realizesDesign link", node=node)
            elif kind == "source":
                meta = node["source"]
                digest = meta.get("sha256")
                snapshot = asset_path(assets, digest, meta["mediaType"]) if digest else None
                if not (snapshot and snapshot.is_file()):
                    add("evidence", "source-not-archived", "Source is link-only (no verified local archive)", node=node)

            for row in out:
                if "property" in row and row.get("state") in {"unknown", "withheld"} and not row.get("inheritedFrom"):
                    scope_str = f" ({row['scope']})" if row.get("scope") else ""
                    add(
                        "properties",
                        f"property-{row['state']}",
                        f"{row['property']}{scope_str} is {row['state']}",
                        node=node,
                        statement=row,
                    )

            if kind == "process":
                stages_present.add(node["stage"])

            if tier == "catalog":
                continue

            # Tier 2: assembly checks
            if kind == "referenceDesign":
                is_taxonomy_stub = any(
                    r.get("predicate") == "hasPart"
                    and (r.get("qualifiers") or {}).get("role") == "taxonomy-division"
                    for r in inc
                )
                has_parts = any(r.get("predicate") == "hasPart" for r in out)
                # Material-neutral slots under a realized parent assembly are fulfilled by concrete productVariants.
                realized = any(r.get("predicate") == "realizesDesign" for r in inc)
                if not realized:
                    anc_q = deque(r["subject"] for r in inc if r.get("predicate") == "hasPart")
                    anc_seen: set[str] = set()
                    while anc_q and not realized:
                        aid = anc_q.popleft()
                        if aid in anc_seen:
                            continue
                        anc_seen.add(aid)
                        if any(r.get("predicate") == "realizesDesign" for r in inc_by[aid]):
                            realized = True
                            break
                        for pr in inc_by[aid]:
                            if pr.get("predicate") == "hasPart":
                                anc_q.append(pr["subject"])
                has_mat = any(r.get("predicate") == "madeOf" for r in out)
                if not is_taxonomy_stub and not has_parts and not realized and not has_mat:
                    add("composition", "part-missing-material", "Leaf part has no madeOf material", node=node)
                if not is_taxonomy_stub and not has_parts and not realized and not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "part-missing-process", "Leaf part has no upstream producing process", node=node)
            elif kind == "productModel":
                if not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "product-missing-process", "productModel has no upstream producing process", node=node)
            elif kind == "productVariant":
                parent_models = [r["target"] for r in out if r.get("predicate") == "isVariantOf"]
                parent_produced = any(
                    any(pr.get("predicate") == "produces" for pr in inc_by[mid])
                    for mid in parent_models
                )
                if not any(r.get("predicate") == "produces" for r in inc) and not parent_produced:
                    add("valueChain", "product-missing-process", "productVariant has no upstream producing process", node=node)
            elif kind == "process":
                if not any(r.get("predicate") == "performedBy" for r in out):
                    add("valueChain", "process-missing-actor", "Process has no performedBy actor", node=node)

            if tier == "assembly":
                continue

            # Tier 3: atomic checks
            if kind == "material":
                if not any(r.get("predicate") in {"hasComposition", "hasStructure"} for r in out):
                    add("composition", "material-missing-chemistry", "Material has no composition or structure model", node=node)
                if not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "material-missing-process", "Material has no upstream producing or extraction process", node=node)
            elif kind == "structureModel":
                if not any(r.get("predicate") == "includesChemical" for r in out):
                    add("composition", "structure-missing-chemical", "structureModel has no includesChemical links", node=node)

        if tier == "assembly":
            for stage in ("fabrication", "installation"):
                if stage not in stages_present:
                    add("valueChain", "missing-stage", f"No '{stage}' stage processes represented")
        elif tier == "atomic":
            for stage in ("extraction", "fabrication", "distribution", "installation"):
                if stage not in stages_present:
                    add("valueChain", "missing-stage", f"No '{stage}' stage processes represented")

        counts: dict[str, int] = defaultdict(int)
        for item in items:
            counts[item["category"]] += 1
        return {
            "scope": node_id or "graph",
            "tier": tier,
            "summary": {
                "total": len(items),
                "composition": counts["composition"],
                "valueChain": counts["valueChain"],
                "properties": counts["properties"],
                "evidence": counts["evidence"],
            },
            "gaps": items,
        }
