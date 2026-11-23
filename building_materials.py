"""Validate and explore the building materials graph."""

import argparse
from collections import defaultdict, deque
from datetime import UTC, datetime
import graphlib
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import sqlite3
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
import webbrowser

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parent
DEFAULT_GRAPH = ROOT / "fixtures" / "window.json"
DEFAULT_ASSETS = ROOT / ".materials"
MAX_ASSET_BYTES = 32 * 1024 * 1024
COMPOSITION = {
    "hasPart", "madeOf", "hasComposition", "hasStructure", "includesChemical",
    "realizesDesign", "usesConfiguration",
}
USED_BY = {
    "hasPart", "madeOf", "hasComposition", "hasStructure", "includesChemical",
    "realizesDesign", "isVariantOf", "usesConfiguration", "usesProduct", "uses",
}
TRACE_FORWARD = {
    "hasPart", "realizesDesign", "isVariantOf", "usesConfiguration", "usesProduct",
    "manufacturedBy", "uses", "produces", "performedBy", "supersedes",
}
TRACE_REVERSE = {"produces", "appliesTo"}
LINK_KINDS = {
    "hasPart": ({"referenceDesign", "productVariant"}, {"referenceDesign", "productVariant"}),
    "madeOf": ({"referenceDesign", "productVariant"}, {"material"}),
    "hasStructure": ({"material"}, {"structureModel"}),
    "hasComposition": ({"material"}, {"material", "chemicalEntity"}),
    "includesChemical": ({"structureModel"}, {"chemicalEntity"}),
    "realizesDesign": ({"productModel", "productVariant"}, {"referenceDesign"}),
    "isVariantOf": ({"productVariant"}, {"productModel"}),
    "usesConfiguration": ({"referenceDesign", "productVariant"}, {"referenceDesign", "productVariant"}),
    "usesProduct": ({"referenceDesign", "productVariant"}, {"productModel"}),
    "manufacturedBy": ({"productModel"}, {"actor"}),
    "uses": ({"process"}, None),
    "produces": ({"process"}, None),
    "performedBy": ({"process"}, {"actor"}),
    "appliesTo": ({"requirement"}, {"referenceDesign", "productModel", "productVariant"}),
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Graph:
    def __init__(self, path, assets):
        data = read_json(path)
        validator = Draft202012Validator(
            read_json(ROOT / "graph.schema.json"),
            format_checker=Draft202012Validator.FORMAT_CHECKER,
        )
        validator.validate(data)
        nodes = list(data["nodes"])
        for manifest in sorted((assets / "sources").glob("*.json")):
            node = read_json(manifest)
            validator.evolve(schema={"$ref": "#/$defs/node"}).validate(node)
            if node["kind"] != "source":
                raise ValueError(f"Source manifest must contain a source node: {manifest}")
            nodes.append(node)
        self.nodes = {node["id"]: node for node in nodes}
        self.statements = {row["id"]: row for row in data["statements"]}
        if len(self.nodes) != len(nodes):
            raise ValueError("Duplicate node ID")
        if len(self.statements) != len(data["statements"]):
            raise ValueError("Duplicate statement ID")

        self.outgoing = defaultdict(list)
        self.incoming = defaultdict(list)
        parts = graphlib.TopologicalSorter()
        derivations = graphlib.TopologicalSorter()
        for row in self.statements.values():
            subject = self.node(row["subject"])
            self.outgoing[subject["id"]].append(row)
            if target_id := row.get("target"):
                target = self.node(target_id)
                self.incoming[target_id].append(row)
                kinds = LINK_KINDS.get(row["predicate"])
                if kinds and (
                    subject["kind"] not in kinds[0]
                    or (kinds[1] is not None and target["kind"] not in kinds[1])
                ):
                    raise ValueError(f"{row['id']}: invalid endpoint kinds for {row['predicate']}")
                if row["predicate"] == "hasPart":
                    parts.add(subject["id"], target_id)
            for quantity in (row.get("quantity"), row.get("qualifiers", {}).get("quantity")):
                if quantity and "min" in quantity and quantity["min"] > quantity["max"]:
                    raise ValueError(f"{row['id']}: quantity minimum exceeds maximum")
            for citation in row["evidence"]:
                source = self.node(citation["source"])
                if source["kind"] != "source":
                    raise ValueError(f"{row['id']}: evidence must cite a source")
                if source["source"]["mediaType"] == "application/pdf" and "page" not in citation["locator"]:
                    raise ValueError(f"{row['id']}: PDF evidence requires a page")
            for dependency in row.get("derivedFrom", ()):
                if dependency not in self.statements:
                    raise ValueError(f"{row['id']}: unknown derived-from statement {dependency}")
                derivations.add(row["id"], dependency)
        for sorter, name in [(parts, "composition"), (derivations, "claim derivation")]:
            try:
                tuple(sorter.static_order())
            except graphlib.CycleError as error:
                raise ValueError(f"Cycle in {name}: {' -> '.join(error.args[1])}") from error

    def node(self, node_id):
        if node_id not in self.nodes:
            raise ValueError(f"Unknown node ID: {node_id}")
        return self.nodes[node_id]

    def facts(self, node_id):
        return {
            "subject": self.node(node_id),
            "statements": [row for row in self.outgoing[node_id] if "property" in row],
        }

    def walk(self, node_id, *, trace):
        self.node(node_id)
        pending = deque([node_id])
        seen = set()
        selected = set()
        forward = TRACE_FORWARD if trace else COMPOSITION
        reverse = TRACE_REVERSE if trace else set()
        while pending:
            current = pending.popleft()
            if current in seen:
                continue
            seen.add(current)
            for row in self.outgoing[current]:
                if row.get("predicate") in forward:
                    selected.add(row["id"])
                    pending.append(row["target"])
                elif "property" in row:
                    selected.add(row["id"])
            for row in self.incoming[current]:
                if row["predicate"] in reverse or (
                    trace and row["predicate"] == "uses" and current == node_id
                ):
                    selected.add(row["id"])
                    pending.append(row["subject"])

        statements = [row for row_id, row in self.statements.items() if row_id in selected]
        seen.update(evidence["source"] for row in statements for evidence in row["evidence"])
        return {"root": node_id, "nodes": [node for nid, node in self.nodes.items() if nid in seen],
                "statements": statements}

    def compare(self, left_id, right_id):
        left = self.node(left_id)
        right = self.node(right_id)
        left_parts = self.walk(left_id, trace=False)
        right_parts = self.walk(right_id, trace=False)
        left_trace = self.walk(left_id, trace=True)
        right_trace = self.walk(right_id, trace=True)

        def diff_nodes(left_walk, right_walk, predicate_fn):
            lmap = {n["id"]: n for n in left_walk["nodes"] if predicate_fn(n)}
            rmap = {n["id"]: n for n in right_walk["nodes"] if predicate_fn(n)}
            return {
                "shared": [lmap[nid] for nid in lmap if nid in rmap],
                "onlyLeft": [lmap[nid] for nid in lmap if nid not in rmap],
                "onlyRight": [rmap[nid] for nid in rmap if nid not in lmap],
            }

        def collect_facts(root_id):
            subjects = [root_id] + [
                row["target"] for row in self.outgoing[root_id] if row.get("predicate") == "realizesDesign"
            ]
            by_key = {}
            for sid in subjects:
                for row in self.outgoing[sid]:
                    if "property" in row:
                        key = (row["property"], row.get("scope") or "")
                        by_key.setdefault(key, row)
            return by_key

        lfacts = collect_facts(left_id)
        rfacts = collect_facts(right_id)
        fact_keys = list(dict.fromkeys([*lfacts.keys(), *rfacts.keys()]))
        facts = [
            {"property": prop, "scope": scope or None, "left": lfacts.get((prop, scope)), "right": rfacts.get((prop, scope))}
            for prop, scope in fact_keys
        ]
        part_ids_l = {s["target"] for s in left_parts["statements"] if s.get("predicate") == "hasPart"}
        part_ids_r = {s["target"] for s in right_parts["statements"] if s.get("predicate") == "hasPart"}
        parts_diff = {
            "shared": [self.nodes[nid] for nid in part_ids_l if nid in part_ids_r],
            "onlyLeft": [self.nodes[nid] for nid in part_ids_l if nid not in part_ids_r],
            "onlyRight": [self.nodes[nid] for nid in part_ids_r if nid not in part_ids_l],
        }
        return {
            "left": left,
            "right": right,
            "facts": facts,
            "materials": diff_nodes(left_parts, right_parts, lambda n: n["kind"] == "material"),
            "parts": parts_diff,
            "processes": diff_nodes(left_trace, right_trace, lambda n: n["kind"] == "process"),
        }

    def gaps(self, assets, node_id=None):
        if node_id is not None:
            self.node(node_id)
            p_nodes = {n["id"] for n in self.walk(node_id, trace=False)["nodes"]}
            t_nodes = {n["id"] for n in self.walk(node_id, trace=True)["nodes"]}
            scope_ids = p_nodes | t_nodes
        else:
            scope_ids = set(self.nodes)

        items = []

        def add(category, code, message, node=None, statement=None):
            entry = {"category": category, "code": code, "message": message}
            if node:
                entry["nodeId"] = node["id"]
                entry["label"] = node["label"]
                entry["kind"] = node["kind"]
            if statement:
                entry["statementId"] = statement["id"]
            items.append(entry)

        stages_present = set()
        for nid in sorted(scope_ids):
            node = self.nodes[nid]
            out = self.outgoing[nid]
            inc = self.incoming[nid]
            kind = node["kind"]

            if kind == "referenceDesign":
                has_parts = any(r.get("predicate") == "hasPart" for r in out)
                realized = any(r.get("predicate") == "realizesDesign" for r in inc)
                has_mat = any(r.get("predicate") == "madeOf" for r in out)
                if not has_parts and not realized and not has_mat:
                    add("composition", "part-missing-material", "Leaf part has no madeOf material", node=node)
                if not has_parts and not realized and not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "part-missing-process", "Leaf part has no upstream producing process", node=node)
            elif kind == "material":
                if not any(r.get("predicate") in {"hasComposition", "hasStructure"} for r in out):
                    add("composition", "material-missing-chemistry", "Material has no composition or structure model", node=node)
                if not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "material-missing-process", "Material has no upstream producing or extraction process", node=node)
            elif kind in {"productModel", "productVariant"}:
                if not any(r.get("predicate") == "produces" for r in inc):
                    add("valueChain", "product-missing-process", "Product has no upstream producing process", node=node)
            elif kind == "process":
                stages_present.add(node["stage"])
                if not any(r.get("predicate") == "performedBy" for r in out):
                    add("valueChain", "process-missing-actor", "Process has no performedBy actor", node=node)
            elif kind == "source":
                meta = node["source"]
                digest = meta.get("sha256")
                snapshot = asset_path(assets, digest, meta["mediaType"]) if digest else None
                if not (snapshot and snapshot.is_file()):
                    add("evidence", "source-not-archived", "Source is link-only (no verified local archive)", node=node)

            for row in out:
                if "property" in row and row.get("state") in {"unknown", "withheld"}:
                    scope_str = f" ({row['scope']})" if row.get("scope") else ""
                    add(
                        "properties",
                        f"property-{row['state']}",
                        f"{row['property']}{scope_str} is {row['state']}",
                        node=node,
                        statement=row,
                    )

        for stage in ("extraction", "fabrication", "distribution", "installation"):
            if stage not in stages_present:
                add("valueChain", "missing-stage", f"No '{stage}' stage processes represented")

        counts = defaultdict(int)
        for item in items:
            counts[item["category"]] += 1
        return {
            "scope": node_id or "graph",
            "summary": {
                "total": len(items),
                "composition": counts["composition"],
                "valueChain": counts["valueChain"],
                "properties": counts["properties"],
                "evidence": counts["evidence"],
            },
            "gaps": items,
        }

    def export_db(self, db_path):
        target = Path(db_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            target.unlink()
        schema_sql = (ROOT / "schema.sql").read_text(encoding="utf-8")
        conn = sqlite3.connect(target)
        try:
            conn.executescript(schema_sql)
            citation_count = 0
            with conn:
                for node in self.nodes.values():
                    conn.execute(
                        "INSERT INTO nodes (id, kind, label, description, revision, scale, stage) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (node["id"], node["kind"], node["label"], node.get("description"),
                         node.get("revision"), node.get("scale"), node.get("stage")),
                    )
                    if src := node.get("source"):
                        conn.execute(
                            "INSERT INTO sources (node_id, origin, media_type, issuer, issued_on, retrieved_at, retrieved_on, sha256) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                            (node["id"], src["origin"], src["mediaType"], src.get("issuer"),
                             src.get("issuedOn"), src.get("retrievedAt"), src.get("retrievedOn"), src.get("sha256")),
                        )
                    for ident in node.get("identifiers", ()):
                        conn.execute(
                            "INSERT INTO node_identifiers (node_id, namespace, value) VALUES (?, ?, ?)",
                            (node["id"], ident["namespace"], ident["value"]),
                        )
                for row in self.statements.values():
                    qty = row.get("quantity") or {}
                    qual = row.get("qualifiers") or {}
                    val = row.get("value")
                    conn.execute(
                        """INSERT INTO statements (
                            id, subject_id, predicate, target_id, property, value_text,
                            quantity_value, quantity_min, quantity_max, quantity_unit, quantity_basis,
                            state, scope, method, conditions, basis, qual_role, qual_position, qual_sequence
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            row["id"], row["subject"], row.get("predicate"), row.get("target"),
                            row.get("property"), None if val is None else str(val),
                            qty.get("value"), qty.get("min"), qty.get("max"), qty.get("unit"), qty.get("basis"),
                            row.get("state"), row.get("scope"), row.get("method"), row.get("conditions"),
                            row["basis"], qual.get("role"), qual.get("position"), qual.get("sequence"),
                        ),
                    )
                    for ev in row["evidence"]:
                        loc = ev["locator"]
                        conn.execute(
                            """INSERT INTO citations (
                                statement_id, source_id, page, section, table_name,
                                row_name, column_name, figure, anchor, quote
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (
                                row["id"], ev["source"], loc.get("page"), loc.get("section"),
                                loc.get("table"), loc.get("row"), loc.get("column"),
                                loc.get("figure"), loc.get("anchor"), loc.get("quote"),
                            ),
                        )
                        citation_count += 1
                for row in self.statements.values():
                    for dep in row.get("derivedFrom", ()):
                        conn.execute(
                            "INSERT INTO statement_derivations (statement_id, derived_from) VALUES (?, ?)",
                            (row["id"], dep),
                        )
            return {
                "db": str(target.resolve()),
                "nodes": len(self.nodes),
                "statements": len(self.statements),
                "citations": citation_count,
            }
        finally:
            conn.close()

    def used_by(self, node_id):
        self.node(node_id)
        pending = deque([node_id])
        seen = set()
        selected = set()
        while pending:
            current = pending.popleft()
            if current in seen:
                continue
            seen.add(current)
            for row in self.incoming[current]:
                if row["predicate"] in USED_BY:
                    selected.add(row["id"])
                    pending.append(row["subject"])
        statements = [row for row_id, row in self.statements.items() if row_id in selected]
        seen.update(evidence["source"] for row in statements for evidence in row["evidence"])
        return {"root": node_id, "nodes": [node for nid, node in self.nodes.items() if nid in seen],
                "statements": statements}

    def cite(self, statement_id, assets):
        if statement_id not in self.statements:
            raise ValueError(f"Unknown statement ID: {statement_id}")
        row = self.statements[statement_id]
        evidence = []
        for citation in row["evidence"]:
            source = self.nodes[citation["source"]]
            metadata = source["source"]
            origin = metadata["origin"]
            digest = metadata.get("sha256")
            snapshot = asset_path(assets, digest, metadata["mediaType"]) if digest else None
            captured = snapshot is not None and snapshot.is_file()
            if captured and hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Snapshot hash mismatch for {source['id']}")
            href = snapshot.resolve().as_uri() if captured else origin
            locator = citation["locator"]
            fragment = f"page={locator['page']}" if "page" in locator else locator.get("anchor")
            if fragment:
                href = urlunsplit(urlsplit(href)._replace(fragment=fragment))
            evidence.append({
                "source": source, "locator": locator, "href": href,
                "capture": "saved" if captured else "link-only",
                **({"savedPath": str(snapshot.resolve())} if captured else {}),
            })
        return {"statement": row, "evidence": evidence}


def asset_path(assets, digest, media_type):
    known = {
        "application/pdf": ".pdf",
        "text/html": ".html",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "application/json": ".json",
    }
    suffix = known.get(media_type) or mimetypes.guess_extension(media_type) or ""
    return assets / "blobs" / f"{digest}{suffix}"


def source_url(value):
    parsed = urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None):
        raise ValueError("Source URL must be HTTP(S) without embedded credentials")
    return parsed.geturl()


def read_asset(location):
    url = urlsplit(location)
    if url.scheme in {"http", "https"}:
        request = Request(source_url(location), headers={"User-Agent": "BuildingMaterials/1.0"})
        with urlopen(request, timeout=20) as response:
            data = response.read(MAX_ASSET_BYTES + 1)
            media_type = response.headers.get_content_type()
        name = unquote(Path(url.path).name) or url.hostname
    elif url.scheme and not Path(location).drive:
        raise ValueError("Source must be a local file or a public HTTP(S) URL")
    else:
        path = Path(location).resolve(strict=True)
        if not path.is_file():
            raise ValueError("Source path must point to a file")
        with path.open("rb") as file:
            data = file.read(MAX_ASSET_BYTES + 1)
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        name = path.name

    if not data or len(data) > MAX_ASSET_BYTES:
        raise ValueError(f"Source must contain 1 to {MAX_ASSET_BYTES} bytes")
    if data.startswith(b"%PDF-"):
        media_type = "application/pdf"
    elif media_type == "application/pdf" or name.lower().endswith(".pdf"):
        raise ValueError("Expected a PDF but received different content")
    elif data.lstrip()[:20].lower().startswith((b"<!doctype html", b"<html")):
        media_type = "text/html"
    return data, media_type, name


def publish_once(path, data):
    """Write a complete immutable file before exposing it at its final path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    with NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
        temporary_path = Path(temporary.name)
        try:
            temporary.write(data)
        except BaseException:
            temporary.close()
            temporary_path.unlink(missing_ok=True)
            raise
    try:
        os.link(temporary_path, path)
    except FileExistsError:
        pass
    finally:
        temporary_path.unlink(missing_ok=True)


def import_source(args):
    if args.url is None and urlsplit(args.location).scheme not in {"http", "https"}:
        raise ValueError("Local source files require --url with their original HTTP(S) URL")
    origin = source_url(args.url if args.url is not None else args.location)
    data, media_type, title = read_asset(args.location)
    digest = hashlib.sha256(data).hexdigest()
    if args.expect_sha256 and digest != args.expect_sha256.lower():
        raise ValueError(f"Expected SHA-256 {args.expect_sha256}, received {digest}")
    snapshot = asset_path(args.assets, digest, media_type)
    publish_once(snapshot, data)
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != digest:
        raise ValueError(f"Snapshot hash mismatch for {snapshot}")
    if args.graph.is_file():
        for node in read_json(args.graph)["nodes"]:
            source = node.get("source", {})
            if source.get("origin") == origin and source.get("sha256") == digest:
                return {"source": node, "savedPath": str(snapshot.resolve())}

    source_key = hashlib.sha256(f"{origin}\0{digest}".encode()).hexdigest()
    source_id = f"source-{source_key}"
    manifest = args.assets / "sources" / f"{source_id}.json"

    record = {
        "id": source_id,
        "kind": "source",
        "label": args.title or title,
        "source": {
            "origin": origin,
            "mediaType": media_type,
            "sha256": digest,
            "retrievedAt": datetime.now(UTC).isoformat(),
        },
    }
    if args.issuer:
        record["source"]["issuer"] = args.issuer
    if args.revision:
        record["revision"] = args.revision
    publish_once(manifest, (json.dumps(record, indent=2) + "\n").encode())
    return {"source": read_json(manifest), "savedPath": str(snapshot.resolve())}


def make_server(graph, assets, host="127.0.0.1", port=8000):
    blobs_dir = (assets / "blobs").resolve()
    viewer_path = ROOT / "viewer.html"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status, body, content_type):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status, payload):
            self._send(status, json.dumps(payload).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            if path in {"/", "/index.html"}:
                if not viewer_path.is_file():
                    self._send(404, b"viewer.html not found", "text/plain; charset=utf-8")
                    return
                self._send(200, viewer_path.read_bytes(), "text/html; charset=utf-8")
                return
            if path == "/api/graph":
                self._json(200, {
                    "nodes": list(graph.nodes.values()),
                    "statements": list(graph.statements.values()),
                })
                return
            if path == "/api/gaps":
                self._json(200, graph.gaps(assets))
                return
            if path == "/api/schema":
                schema_path = ROOT / "schema.sql"
                text = schema_path.read_text(encoding="utf-8") if schema_path.is_file() else ""
                self._json(200, {"sql": text})
                return
            if path.startswith("/assets/"):
                name = path[len("/assets/"):]
                if not name or "/" in name or "\\" in name or name != Path(name).name:
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                    return
                target = (blobs_dir / name).resolve()
                if target.parent != blobs_dir or not target.is_file():
                    self._send(404, b"Not found", "text/plain; charset=utf-8")
                    return
                mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self._send(200, target.read_bytes(), mime)
                return
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "compare":
                try:
                    self._json(200, graph.compare(parts[2], parts[3]))
                except ValueError as error:
                    self._json(404, {"error": str(error)})
                return
            if len(parts) == 3 and parts[0] == "api":
                kind, item_id = parts[1], parts[2]
                try:
                    if kind == "parts":
                        self._json(200, graph.walk(item_id, trace=False))
                    elif kind == "trace":
                        self._json(200, graph.walk(item_id, trace=True))
                    elif kind == "used-by":
                        self._json(200, graph.used_by(item_id))
                    elif kind == "facts":
                        self._json(200, graph.facts(item_id))
                    elif kind == "gaps":
                        self._json(200, graph.gaps(assets, item_id))
                    elif kind == "cite":
                        cited = graph.cite(item_id, assets)
                        for entry in cited["evidence"]:
                            if entry["capture"] == "saved":
                                frag = urlsplit(entry["href"]).fragment
                                web = f"/assets/{Path(entry['savedPath']).name}"
                                entry["webHref"] = f"{web}#{frag}" if frag else web
                            else:
                                entry["webHref"] = entry["href"]
                        self._json(200, cited)
                    else:
                        self._json(404, {"error": f"Unknown endpoint: {path}"})
                except ValueError as error:
                    self._json(404, {"error": str(error)})
                return
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--graph", type=Path, default=DEFAULT_GRAPH, help="Graph JSON, defaults to the window fixture")
    cli.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help="Source asset directory")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Check the graph and source manifests")
    for command, help_text in [
        ("parts", "Walk composition from a design, product variant, or material"),
        ("trace", "Walk the value chain from a design, product, or process"),
        ("used-by", "Find where a product model, variant, material, or part is used"),
        ("facts", "List claims made directly about a node"),
    ]:
        commands.add_parser(command, help=help_text).add_argument("node_id")
    cmp_cmd = commands.add_parser("compare", help="Compare composition, properties, and value chains of two nodes")
    cmp_cmd.add_argument("left_id")
    cmp_cmd.add_argument("right_id")
    gaps_cmd = commands.add_parser("gaps", help="Report composition, value-chain, property, and evidence gaps")
    gaps_cmd.add_argument("node_id", nargs="?", default=None)
    db_cmd = commands.add_parser("export-db", help="Materialize the graph into a SQLite database using schema.sql")
    db_cmd.add_argument("output", type=Path, nargs="?", default=DEFAULT_ASSETS / "materials.db")
    commands.add_parser("cite", help="Resolve a statement to its source and exact locator").add_argument("statement_id")
    source = commands.add_parser("import-source", help="Archive a local file or public PDF/web URL")
    source.add_argument("location")
    source.add_argument("--url", help="Original HTTP(S) source URL, required for local files")
    source.add_argument("--title")
    source.add_argument("--issuer")
    source.add_argument("--revision")
    source.add_argument("--expect-sha256", help="Archive only if the content matches this SHA-256")
    serve = commands.add_parser("serve", help="Run a local web UI to explore the graph")
    serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    serve.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    serve.add_argument("--open", action="store_true", help="Open the UI in the default browser")
    return cli


def main():
    args = parser().parse_args()
    try:
        if args.command == "import-source":
            result = import_source(args)
        else:
            graph = Graph(args.graph, args.assets)
            if args.command == "serve":
                server = make_server(graph, args.assets, host=args.host, port=args.port)
                url = f"http://{args.host}:{server.server_port}/"
                print(f"Serving Building Materials UI at {url}", flush=True)
                if args.open:
                    webbrowser.open(url)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
                finally:
                    server.server_close()
                return 0
            if args.command == "validate":
                result = {"valid": True, "nodes": len(graph.nodes), "statements": len(graph.statements)}
            elif args.command == "facts":
                result = graph.facts(args.node_id)
            elif args.command == "used-by":
                result = graph.used_by(args.node_id)
            elif args.command == "compare":
                result = graph.compare(args.left_id, args.right_id)
            elif args.command == "gaps":
                result = graph.gaps(args.assets, args.node_id)
            elif args.command == "export-db":
                result = graph.export_db(args.output)
            elif args.command == "cite":
                result = graph.cite(args.statement_id, args.assets)
            else:
                result = graph.walk(args.node_id, trace=args.command == "trace")
    except ValidationError as error:
        location = "/".join(map(str, error.absolute_path))
        print(f"Invalid graph at /{location}: {error.message}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
