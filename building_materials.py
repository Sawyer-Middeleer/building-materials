"""Validate and explore the building materials graph."""

import argparse
from collections import defaultdict, deque
from datetime import UTC, datetime
import graphlib
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, ValidationError


ROOT = Path(__file__).resolve().parent
DEFAULT_GRAPH = ROOT / "fixtures" / "window.json"
DEFAULT_ASSETS = ROOT / ".materials"
MAX_ASSET_BYTES = 32 * 1024 * 1024
COMPOSITION = {"hasPart", "madeOf", "hasComposition", "hasStructure", "includesChemical"}
TRACE_FORWARD = {
    "hasPart", "fillsOpening", "specifies", "isInstanceOf", "isVariantOf", "realizesDesign",
    "usesConfiguration", "usesProduct", "uses", "produces", "performedBy", "selects",
    "evaluates", "followsProcess", "informedBy", "supersedes",
}
TRACE_REVERSE = {"produces", "appliesTo", "fillsOpening"}
LINK_KINDS = {
    "madeOf": ({"physicalItem", "referenceDesign"}, {"material"}),
    "hasStructure": ({"material"}, {"structureModel"}),
    "hasComposition": ({"material"}, {"material", "chemicalEntity"}),
    "includesChemical": ({"structureModel"}, {"chemicalEntity"}),
    "realizesDesign": ({"productVariant"}, {"referenceDesign"}),
    "isVariantOf": ({"productVariant"}, {"productModel"}),
    "isInstanceOf": ({"physicalItem"}, {"productVariant", "referenceDesign"}),
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
        placements = []
        derivations = graphlib.TopologicalSorter()
        for row in self.statements.values():
            subject = self.node(row["subject"])
            self.outgoing[subject["id"]].append(row)
            if target_id := row.get("target"):
                target = self.node(target_id)
                self.incoming[target_id].append(row)
                kinds = LINK_KINDS.get(row["predicate"])
                if kinds and (subject["kind"] not in kinds[0] or target["kind"] not in kinds[1]):
                    raise ValueError(f"{row['id']}: invalid endpoint kinds for {row['predicate']}")
                if row["predicate"] == "hasPart":
                    if subject["kind"] != target["kind"] or subject["kind"] not in {
                        "physicalItem", "referenceDesign"
                    }:
                        raise ValueError(f"{row['id']}: hasPart must connect items or designs of the same kind")
                    parts.add(subject["id"], target_id)
                if row["predicate"] == "fillsOpening":
                    installation = self.node(row.get("qualifiers", {}).get("activity"))
                    if (subject["kind"] != "physicalItem" or target["kind"] != "physicalItem"
                            or installation.get("stage") != "installation"):
                        raise ValueError(f"{row['id']}: fillsOpening requires physical items and an installation activity")
                    placements.append(row)
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
        for row in placements:
            activity = row["qualifiers"]["activity"]
            installation_inputs = {
                link["target"] for link in self.outgoing[activity] if link.get("predicate") == "uses"
            }
            if not {row["subject"], row["target"]} <= installation_inputs:
                raise ValueError(f"{row['id']}: installation must identify the window and its opening")
        for sorter, name in [(parts, "physical composition"), (derivations, "claim derivation")]:
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

    def _physical_scope(self, node_id):
        scope = set()
        pending = [node_id]
        while pending:
            current = pending.pop()
            if current in scope or self.nodes[current]["kind"] != "physicalItem":
                continue
            scope.add(current)
            incoming = self.incoming[current]
            installed = [edge["subject"] for edge in incoming if edge["predicate"] == "fillsOpening"]
            pending.extend(installed)
            # The opening is the installation boundary. Its host wall isn't part of the window trace.
            if not installed:
                pending.extend(edge["subject"] for edge in incoming if edge["predicate"] == "hasPart")
            pending.extend(edge["target"] for edge in self.outgoing[current]
                           if edge.get("predicate") in {"hasPart", "fillsOpening"})
        return scope

    def walk(self, node_id, *, trace):
        self.node(node_id)
        downstream = self._physical_scope(node_id) if trace else set()
        pending = deque([node_id])
        seen = set()
        selected = set()
        forward = TRACE_FORWARD if trace else COMPOSITION
        reverse = TRACE_REVERSE if trace else {"fillsOpening"}
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
                    row["predicate"] == "uses" and current in downstream
                ):
                    selected.add(row["id"])
                    pending.append(row["subject"])

        statements = [row for row_id, row in self.statements.items() if row_id in selected]
        seen.update(evidence["source"] for row in statements for evidence in row["evidence"])
        return {"root": node_id, "nodes": [node for node_id, node in self.nodes.items() if node_id in seen],
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
    suffix = {"application/pdf": ".pdf", "text/html": ".html"}.get(media_type, "")
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


def parser():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--graph", type=Path, default=DEFAULT_GRAPH, help="Graph JSON, defaults to the window fixture")
    cli.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help="Source asset directory")
    commands = cli.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Check the graph and source manifests")
    for command, help_text in [
        ("parts", "Walk composition from an opening or component"),
        ("trace", "Walk the value chain from an opening, component, or activity"),
        ("facts", "List claims made directly about a node"),
    ]:
        commands.add_parser(command, help=help_text).add_argument("node_id")
    commands.add_parser("cite", help="Resolve a statement to its source and exact locator").add_argument("statement_id")
    source = commands.add_parser("import-source", help="Archive a local file or public PDF/web URL")
    source.add_argument("location")
    source.add_argument("--url", help="Original HTTP(S) source URL, required for local files")
    source.add_argument("--title")
    source.add_argument("--issuer")
    source.add_argument("--revision")
    source.add_argument("--expect-sha256", help="Archive only if the content matches this SHA-256")
    return cli


def main():
    args = parser().parse_args()
    try:
        if args.command == "import-source":
            result = import_source(args)
        else:
            graph = Graph(args.graph, args.assets)
            if args.command == "validate":
                result = {"valid": True, "nodes": len(graph.nodes), "statements": len(graph.statements)}
            elif args.command == "facts":
                result = graph.facts(args.node_id)
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
