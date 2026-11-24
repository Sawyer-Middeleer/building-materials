"""Headless, thread-safe, filtered/paginated JSON HTTP API backed by SQLite."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .audit import run_audit
from .model import GAP_TIERS, ROOT
from .store import MaterialStore


def _parse_int_param(qs: dict[str, list[str]], name: str, default: int, *, min_val: int, max_val: int | None = None) -> int:
    raw = qs.get(name, [None])[0]
    if raw is None or raw == "":
        return default
    try:
        val = int(raw)
    except ValueError as exc:
        raise ValueError(f"Query parameter '{name}' must be an integer") from exc
    if val < min_val or (max_val is not None and val > max_val):
        bound = f"{min_val}..{max_val}" if max_val is not None else f">= {min_val}"
        raise ValueError(f"Query parameter '{name}' must be in range {bound}")
    return val


def _first(qs: dict[str, list[str]], name: str) -> str | None:
    vals = qs.get(name)
    if not vals:
        return None
    v = vals[0].strip()
    return v or None


def make_server(
    db_path: Path,
    assets: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> ThreadingHTTPServer:
    """Create a JSON-only ThreadingHTTPServer with per-request read-only SQLite connections."""
    resolved_db = Path(db_path).resolve()
    blobs_dir = (Path(assets) / "blobs").resolve()
    schema_path = ROOT / "schema.sql"

    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, status: int, payload: dict) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _error(self, status: int, code: str, message: str) -> None:
            self._json(status, {"error": {"code": code, "message": message}})

        def do_GET(self) -> None:
            parsed = urlsplit(self.path)
            path = unquote(parsed.path)
            qs = parse_qs(parsed.query, keep_blank_values=False)

            if path.startswith("/assets/"):
                name = path[len("/assets/"):]
                if not name or "/" in name or "\\" in name or name != Path(name).name:
                    self._error(404, "not_found", "Asset not found")
                    return
                target = (blobs_dir / name).resolve()
                if target.parent != blobs_dir or not target.is_file():
                    self._error(404, "not_found", "Asset not found")
                    return
                mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                self._send(200, target.read_bytes(), mime)
                return

            try:
                with MaterialStore(resolved_db) as store:
                    if path == "/api/health":
                        self._json(200, {"ok": True, **store.meta()})
                        return

                    if path == "/api/schema":
                        text = schema_path.read_text(encoding="utf-8") if schema_path.is_file() else ""
                        self._json(200, {"sql": text})
                        return

                    if path == "/api/audit":
                        self._json(200, run_audit(store, assets))
                        return

                    if path == "/api/nodes":
                        limit = _parse_int_param(qs, "limit", 50, min_val=1, max_val=200)
                        offset = _parse_int_param(qs, "offset", 0, min_val=0)
                        self._json(
                            200,
                            store.list_nodes(
                                kind=_first(qs, "kind"),
                                prefix=_first(qs, "prefix"),
                                namespace=_first(qs, "namespace"),
                                identifier=_first(qs, "identifier"),
                                q=_first(qs, "q"),
                                limit=limit,
                                offset=offset,
                            ),
                        )
                        return

                    if path == "/api/statements":
                        limit = _parse_int_param(qs, "limit", 50, min_val=1, max_val=200)
                        offset = _parse_int_param(qs, "offset", 0, min_val=0)
                        self._json(
                            200,
                            store.list_statements(
                                subject=_first(qs, "subject"),
                                target=_first(qs, "target"),
                                predicate=_first(qs, "predicate"),
                                property=_first(qs, "property"),
                                scope=_first(qs, "scope"),
                                basis=_first(qs, "basis"),
                                state=_first(qs, "state"),
                                geography=_first(qs, "geography"),
                                active_on=_first(qs, "activeOn"),
                                limit=limit,
                                offset=offset,
                            ),
                        )
                        return

                    if path == "/api/search":
                        q = _first(qs, "q")
                        if not q:
                            self._error(400, "bad_request", "Query parameter 'q' is required")
                            return
                        limit = _parse_int_param(qs, "limit", 50, min_val=1, max_val=200)
                        offset = _parse_int_param(qs, "offset", 0, min_val=0)
                        self._json(200, store.search(q, kind=_first(qs, "kind"), limit=limit, offset=offset))
                        return

                    if path == "/api/compare":
                        left = _first(qs, "left")
                        right = _first(qs, "right")
                        if not left or not right:
                            self._error(400, "bad_request", "Query parameters 'left' and 'right' are required")
                            return
                        self._json(200, store.compare(left, right))
                        return

                    if path == "/api/gaps":
                        tier = _first(qs, "tier") or "assembly"
                        if tier not in GAP_TIERS:
                            self._error(400, "bad_request", f"Invalid tier '{tier}': expected one of {', '.join(GAP_TIERS)}")
                            return
                        self._json(
                            200,
                            store.gaps(
                                assets,
                                _first(qs, "node"),
                                tier=tier,
                                category=_first(qs, "category"),
                            ),
                        )
                        return

                    parts = [p for p in path.strip("/").split("/") if p]

                    if len(parts) == 3 and parts[0] == "api" and parts[1] == "nodes":
                        self._json(200, store.get_node(parts[2], include_guide=True))
                        return

                    if len(parts) == 4 and parts[0] == "api" and parts[1] == "nodes":
                        node_id, sub = parts[2], parts[3]
                        if sub == "facts":
                            inh = (_first(qs, "inherited") or "true").lower() not in {"false", "0", "no"}
                            self._json(200, store.facts(node_id, include_inherited=inh))
                            return
                        if sub == "parts":
                            self._json(200, store.walk(node_id, trace=False))
                            return
                        if sub == "trace":
                            self._json(200, store.walk(node_id, trace=True))
                            return
                        if sub == "used-by":
                            self._json(200, store.used_by(node_id))
                            return

                    if len(parts) == 4 and parts[0] == "api" and parts[1] == "statements" and parts[3] == "cite":
                        cited = store.cite(parts[2], assets)
                        for entry in cited["evidence"]:
                            if entry["capture"] == "saved":
                                frag = urlsplit(entry["href"]).fragment
                                web = f"/assets/{Path(entry['savedPath']).name}"
                                entry["webHref"] = f"{web}#{frag}" if frag else web
                            else:
                                entry["webHref"] = entry["href"]
                        self._json(200, cited)
                        return

                    if len(parts) == 3 and parts[0] == "api" and parts[1] == "explain":
                        self._json(200, store.explain(parts[2]))
                        return

                    self._error(404, "not_found", f"Unknown endpoint: {path}")
            except ValueError as exc:
                msg = str(exc)
                if msg.startswith("Query parameter") or msg.startswith("Invalid tier"):
                    self._error(400, "bad_request", msg)
                else:
                    self._error(404, "not_found", msg)

        def log_message(self, format: str, *args) -> None:
            pass

    return ThreadingHTTPServer((host, port), Handler)
