"""CLI entrypoint for building_materials."""

import argparse
import json
from pathlib import Path
import sys

from .audit import run_audit
from .compiler import compile_dir
from .model import (
    CompileError,
    DEFAULT_ASSETS,
    DEFAULT_DATA,
    DEFAULT_DB,
    GAP_TIERS,
    GraphValidationError,
)
from .server import make_server
from .sources import import_source
from .store import MaterialStore, build_db, ensure_db
from .validator import validate_bundle


def build_parser() -> argparse.ArgumentParser:
    cli = argparse.ArgumentParser(
        prog="python -m building_materials",
        description="Compile, validate, audit, and query the building materials graph.",
    )
    cli.add_argument("--data", type=Path, default=DEFAULT_DATA, help="Authoring data directory (default: data/)")
    cli.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help="Source blob directory (default: .materials/)")
    cli.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite runtime database path")
    cli.add_argument("--no-rebuild", action="store_true", help="Do not auto-rebuild SQLite DB when data/ changes")

    commands = cli.add_subparsers(dest="command", required=True)

    b_cmd = commands.add_parser("build", help="Compile data/ YAML+CSV, validate, and materialize SQLite DB")
    b_cmd.add_argument("--force", action="store_true", help="Force rebuild even if fingerprint matches")

    commands.add_parser("validate", help="Compile data/ YAML+CSV and validate schemas and graph invariants")
    commands.add_parser("audit", help="Verify archived PDF hashes/pages/locators and graph conventions over SQLite")

    n_cmd = commands.add_parser("nodes", help="List and filter nodes from SQLite")
    n_cmd.add_argument("--kind")
    n_cmd.add_argument("--prefix")
    n_cmd.add_argument("--namespace")
    n_cmd.add_argument("--identifier")
    n_cmd.add_argument("--q")
    n_cmd.add_argument("--limit", type=int, default=50)
    n_cmd.add_argument("--offset", type=int, default=0)

    s_cmd = commands.add_parser("search", help="Full-text search nodes via SQLite FTS5")
    s_cmd.add_argument("query")
    s_cmd.add_argument("--kind")
    s_cmd.add_argument("--limit", type=int, default=50)
    s_cmd.add_argument("--offset", type=int, default=0)

    for cmd_name, help_text in [
        ("parts", "Walk physical composition from a design, product variant, or material"),
        ("trace", "Walk the value chain from a design, product, or process"),
        ("used-by", "Find where a product model, variant, material, or part is used"),
    ]:
        commands.add_parser(cmd_name, help=help_text).add_argument("node_id")

    f_cmd = commands.add_parser("facts", help="List property claims on a node")
    f_cmd.add_argument("node_id")
    f_cmd.add_argument("--direct-only", action="store_true", help="Exclude claims inherited from productModel")

    cmp_cmd = commands.add_parser("compare", help="Compare facts, bands, medians, parameters, compatibility, materials, parts, and processes")
    cmp_cmd.add_argument("left_id")
    cmp_cmd.add_argument("right_id")
    cmp_cmd.add_argument("--profile", dest="profile_id", help="Optional requirement node ID (e.g. req.iecc.cz5.fenestration) to evaluate pass/fail")

    g_cmd = commands.add_parser("gaps", help="Report composition, value-chain, property, and evidence gaps")
    g_cmd.add_argument("node_id", nargs="?", default=None)
    g_cmd.add_argument("--tier", choices=GAP_TIERS, default="assembly", help="Completeness tier (default: assembly)")
    g_cmd.add_argument("--category", choices=("composition", "valueChain", "properties", "evidence"))

    commands.add_parser("explain", help="Show plain-English educational guide for a node or property").add_argument("key")
    commands.add_parser("cite", help="Resolve a statement to its source and exact locator").add_argument("statement_id")

    src = commands.add_parser("import-source", help="Archive a local file or public URL into .materials/blobs/ and data/sources/")
    src.add_argument("location", help="Local file path or public HTTP(S) URL")
    src.add_argument("--id", required=True, dest="slug", help="Canonical source slug (dots map to subfolders under data/sources/)")
    src.add_argument("--url", help="Original HTTP(S) source URL (required for local files)")
    src.add_argument("--title", help="Human-readable source title")
    src.add_argument("--issuer", help="Publishing organization or manufacturer")
    src.add_argument("--revision", help="Document revision or edition string")
    src.add_argument("--expect-sha256", help="Verify exact SHA-256 before archiving")

    srv = commands.add_parser("serve", help="Run the headless JSON HTTP API backed by SQLite")
    srv.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    srv.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")

    return cli


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import-source":
            result = import_source(
                args.location,
                slug=args.slug,
                data_dir=args.data,
                assets=args.assets,
                url=args.url,
                title=args.title,
                issuer=args.issuer,
                revision=args.revision,
                expect_sha256=args.expect_sha256,
            )
        elif args.command == "validate":
            bundle = validate_bundle(compile_dir(args.data))
            result = {
                "valid": True,
                "nodes": len(bundle.nodes),
                "statements": len(bundle.statements),
                "guideNodes": len(bundle.guide["nodes"]),
                "guideProperties": len(bundle.guide["properties"]),
                "fingerprint": bundle.fingerprint,
            }
        elif args.command == "build":
            bundle = validate_bundle(compile_dir(args.data))
            result = build_db(bundle, args.db)
        elif args.command == "serve":
            db_path = ensure_db(args.data, args.db, auto_rebuild=not args.no_rebuild)
            server = make_server(db_path, args.assets, host=args.host, port=args.port)
            print(f"Serving Building Materials JSON API at http://{args.host}:{server.server_port}/api/health", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.server_close()
            return 0
        else:
            db_path = ensure_db(args.data, args.db, auto_rebuild=not args.no_rebuild)
            with MaterialStore(db_path) as store:
                if args.command == "audit":
                    result = run_audit(store, args.assets)
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                    return 0 if result["ok"] else 1
                elif args.command == "nodes":
                    result = store.list_nodes(
                        kind=args.kind,
                        prefix=args.prefix,
                        namespace=args.namespace,
                        identifier=args.identifier,
                        q=args.q,
                        limit=args.limit,
                        offset=args.offset,
                    )
                elif args.command == "search":
                    result = store.search(args.query, kind=args.kind, limit=args.limit, offset=args.offset)
                elif args.command == "parts":
                    result = store.walk(args.node_id, trace=False)
                elif args.command == "trace":
                    result = store.walk(args.node_id, trace=True)
                elif args.command == "used-by":
                    result = store.used_by(args.node_id)
                elif args.command == "facts":
                    result = store.facts(args.node_id, include_inherited=not args.direct_only)
                elif args.command == "compare":
                    result = store.compare(args.left_id, args.right_id, profile_id=args.profile_id)
                elif args.command == "gaps":
                    result = store.gaps(args.assets, args.node_id, tier=args.tier, category=args.category)
                elif args.command == "explain":
                    result = store.explain(args.key)
                elif args.command == "cite":
                    result = store.cite(args.statement_id, args.assets)
                else:
                    raise ValueError(f"Unknown command: {args.command}")
    except (CompileError, GraphValidationError, OSError, ValueError) as exc:
        print(exc, file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0
