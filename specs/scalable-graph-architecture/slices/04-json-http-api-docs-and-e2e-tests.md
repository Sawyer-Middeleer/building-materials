# Slice 04 — Headless JSON HTTP API (`serve`), Docs & Minimal E2E Suite

## Contract Unlocked

The project exposes a clean, thread-safe, filtered and paginated **JSON-only HTTP API** (`serve`) backed directly by SQLite, up-to-date project documentation and agent skill instructions, and a **minimal end-to-end test suite** (`tests/test_e2e.py`) proving the complete pipeline from `import-source` through SQLite and HTTP.

---

## API Seams & Ownership

### 1. `building_materials/server.py`
- Headless `ThreadingHTTPServer` — **no HTML, no `/ui/*`, no `--open` flag**.
- **Concurrency Firewall:** Each HTTP request opens its own read-only `MaterialStore(db_path)` (`file:<db>?mode=ro`) in a `with` block and closes it before returning—never shares a `sqlite3.Connection` across threads.
- **Uniform Envelopes:**
  - Collection endpoints: `{"items": [...], "total": int, "limit": int, "offset": int, "hasMore": bool}` (`limit` default `50`, max `200`, `offset` default `0`; invalid integers or out-of-range values return `400`).
  - Errors: `{"error": {"code": "bad_request" | "not_found", "message": "..."}}`.
- **Routes:**
  - `GET /api/health` → `build_meta` + table counts (`nodes`, `statements`, `sources`, `guides`).
  - `GET /api/nodes?kind=&prefix=&namespace=&identifier=&q=&limit=&offset=`
  - `GET /api/nodes/<id>` → node + identifiers + source + colocated guide (`404` if unknown).
  - `GET /api/nodes/<id>/facts?inherited=true`
  - `GET /api/nodes/<id>/parts`
  - `GET /api/nodes/<id>/trace`
  - `GET /api/nodes/<id>/used-by`
  - `GET /api/statements?subject=&target=&predicate=&property=&scope=&basis=&state=&geography=&activeOn=&limit=&offset=`
  - `GET /api/statements/<id>/cite` (attaches `webHref: "/assets/<blob>#page=N"` for saved blobs).
  - `GET /api/search?q=&kind=&limit=&offset=` (FTS5).
  - `GET /api/compare?left=<id>&right=<id>` (`400` if missing params, `404` if unknown ID).
  - `GET /api/gaps?node=&tier=assembly&category=` (`400` on invalid `tier`).
  - `GET /api/audit` → live `run_audit(store, assets)` result.
  - `GET /api/explain/<key>`
  - `GET /api/schema` → `{"sql": <schema.sql contents>}`.
  - `GET /assets/<blob>` → serves archived files from `.materials/blobs/` with strict single-filename path-traversal guard (`name == Path(name).name` and `target.parent == blobs_dir`).
  - Any unknown route (including `/` and `/ui/*`) → JSON `404`.
- Wire `serve [--host 127.0.0.1] [--port 8000]` in `cli.py` (runs `ensure_db` once before binding unless `--no-rebuild` is set).

### 2. Documentation & Skill Updates
- Update [README.md](../../../README.md) to reflect the `data/` YAML + CSV layout, `build` / `validate` / `audit` / `search` / `gaps --tier` / `import-source --id` / headless `serve` CLI, and SQLite runtime.
- Update [specs/graph-data-schema.md](../../graph-data-schema.md) to document the modular YAML authoring format, dotted namespaced IDs, 6-domain taxonomy spine, SKU matrices, EN 15804 EPD rules, and tiered `gaps`.
- Update [.agents/skills/add-building-component/SKILL.md](../../../.agents/skills/add-building-component/SKILL.md) to use `import-source --id <slug>` → `data/sources/<slug>.yaml`, modular YAML/CSV authoring under `data/`, `build`, `audit`, and `gaps --tier`.

### 3. Minimal End-to-End Test Suite (`tests/test_e2e.py`)
Honor `AGENTS.md` ("Keep tests minimal. Test end-to-end paths only.") — **3 E2E tests in one file, zero unit tests of internal helpers**:
1. **`test_real_corpus_build_audit_and_cli_queries`**:
   - Runs against the real `data/` directory and `.materials/blobs/` into a temp `--db` path.
   - Verifies `build`, `validate`, `audit` (`ok: true`, `errors: 0`), `parts envelope.openings.window` (reaches atomic `chem.*`), `trace`, `used-by`, `compare` across two CSV-expanded Vitro Solarban 70 variants, `search` (including punctuated query like `"08 50 00"`), `explain`, `cite`, and `gaps --tier catalog|assembly|atomic`.
2. **`test_authoring_roundtrip_and_negative_contracts`**:
   - In an isolated `TemporaryDirectory`, creates a minimal valid PDF, runs `import-source --id demo-doc --url https://example.com/demo.pdf`, verifies slug-immutability rejection on modified bytes.
   - Authors an entity YAML (with block defaults, `qualifiers.quantity`, boolean property, `productModel` + `variantDefaults`, EN 15804 `gwp` claim with `geography`/`pcr`/`validUntil`/`plantActor`, and imperial `uFactor` verifying auto-computed `siQuantity`) + 2-row CSV SKU matrix, compiles via `build`, verifies lossless SQLite readback + inheritance (`inheritedFrom`) + `geography`/`activeOn` filtering + auto-rebuild after editing a YAML file.
   - Verifies non-zero exit on negative contracts: invalid EPD scope, `gwp` quantity missing `basis`, `hasPart` cycle, and malformed CSV numeric cell.
3. **`test_headless_json_http_api`**:
   - Boots `make_server` on `127.0.0.1:0` against the built temp DB.
   - Verifies `GET /api/health`, filtered & paginated `/api/nodes?kind=productVariant&limit=2&offset=0`, `/api/statements?property=uFactor&limit=5`, `/api/search?q=silicate`, `/api/nodes/<id>/facts`, `/api/compare?left=...&right=...`, `/api/gaps?tier=catalog`, `/api/statements/<id>/cite`, `/assets/<blob>`, `400` on invalid `limit`/`tier`, and `404` on `/` and `/assets/../secret`.

---

## Playable Checkpoint & Verification

1. Run `python -m unittest discover -s tests -v` → all 3 E2E tests pass in < 10 seconds.
2. Start `python -m building_materials serve --port 8000` and verify:
   - `GET http://127.0.0.1:8000/api/health` returns `200` with `schema_version: "2"` and counts.
   - `GET http://127.0.0.1:8000/api/nodes?namespace=uniformat2&identifier=B2020` returns the window opening design.
   - `GET http://127.0.0.1:8000/` returns JSON `404`.

---

## Delegated Decisions

The implementer may choose:
- Exact HTTP header choices (`Cache-Control: no-store`, `Content-Type: application/json; charset=utf-8`).
- Exact helper construction of the minimal synthetic PDF in test #2 (e.g. minimal valid `%PDF-1.4` bytes with a single text stream so `pypdf` can parse page 1).

## What Must Stay Green

- `python -m building_materials validate` and `python -m building_materials audit` exit `0` on the repo's real `data/`.
- `python -m unittest discover -s tests -v` passes cleanly with zero skipped tests.
- Zero references to `fixtures/building.json`, `viewer.html`, `ui/`, or `.materials/sources/` remain anywhere in code or docs.
