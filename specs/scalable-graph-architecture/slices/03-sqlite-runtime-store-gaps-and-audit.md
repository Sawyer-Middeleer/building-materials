# Slice 03 — Lossless SQLite v2 Runtime Store, Tiered `gaps` & SQLite-Backed `audit`

## Contract Unlocked

SQLite (`.materials/materials.db`) becomes the **primary runtime store** for all CLI queries, `gaps --tier`, and `audit`. Every compiled field—including `qualifiers.quantity`, boolean values, `inheritedFrom`, guides, and FTS5 search text—round-trips losslessly, and stale databases auto-rebuild atomically whenever `data/` changes.

---

## API Seams & Ownership

### 1. Lossless `schema.sql` v2
Upgrade `schema.sql` with:
- **`build_meta`**:
  ```sql
  CREATE TABLE IF NOT EXISTS build_meta (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
  );
  ```
  Stores `schema_version = '2'`, `data_fingerprint`, `built_at`, `node_count`, `statement_count`.
- **`sources` lossless additions**:
  - `valid_until TEXT` (ISO-8601 date for expiring documents/EPDs).
- **`statements` lossless additions**:
  - `value_type TEXT CHECK (value_type IS NULL OR value_type IN ('string', 'boolean'))`
  - `si_value REAL`, `si_min REAL`, `si_max REAL`, `si_unit TEXT` (compile-time normalized SI quantity alongside verbatim source `quantity_*`)
  - `qual_qty_value REAL`, `qual_qty_min REAL`, `qual_qty_max REAL`, `qual_qty_unit TEXT`, `qual_qty_basis TEXT`
  - `geography TEXT`, `pcr TEXT`, `valid_until TEXT`, `plant_actor_id TEXT REFERENCES nodes(id) ON DELETE SET NULL`
  - `inherited_from TEXT REFERENCES statements(id) ON DELETE SET NULL`
  - `source_file TEXT` (and `source_file TEXT` on `nodes` for provenance debugging)
- **Guide tables**:
  - `node_guides (node_id TEXT PRIMARY KEY REFERENCES nodes(id) ON DELETE CASCADE, summary TEXT NOT NULL, how_it_works TEXT, why_it_matters TEXT, tradeoffs TEXT, steps_json TEXT, chemistry_json TEXT, firm_json TEXT)`
  - `property_guides (property TEXT PRIMARY KEY, title TEXT NOT NULL, summary TEXT NOT NULL, better_direction TEXT, typical_range TEXT, why_it_matters TEXT, ucum_unit TEXT, external_refs_json TEXT)`
- **Full-text search (FTS5)**:
  - `CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(node_id UNINDEXED, label, description, identifiers, guide_summary, tokenize='unicode61');`
- **Indexes**:
  - `idx_nodes_kind`, `idx_nodes_label`
  - `idx_identifiers_ns_val ON node_identifiers(namespace, value)`
  - `idx_statements_subject`, `idx_statements_target`, `idx_statements_predicate`, `idx_statements_prop_scope(property, scope)`, `idx_statements_basis`, `idx_statements_state`, `idx_statements_geography(geography)`, `idx_statements_valid_until(valid_until)`
  - `idx_citations_stmt(statement_id)`, `idx_citations_source(source_id)`

### 2. `building_materials/store.py`
- **Build & Staleness Guard:**
  - `build_db(bundle: CompiledBundle, db_path: Path) -> dict`: builds into a temp file in `db_path.parent`, populates all tables + `nodes_fts` + `build_meta`, commits, closes, and atomically swaps via `os.replace()` (safe on Windows when no write lock is held).
  - `ensure_db(data_dir: Path, db_path: Path, *, force: bool = False, auto_rebuild: bool = True) -> Path`: computes fast `data_fingerprint` over `data/`; if `db_path` is missing or `build_meta.data_fingerprint` differs (and `auto_rebuild=True`), calls `compile_dir` → `validate_bundle` → `build_db`.
- **`MaterialStore` (read-only SQLite query engine):**
  - Opens `sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)` with `row_factory = sqlite3.Row`; supports context manager (`with MaterialStore(db_path) as store:`).
  - Reconstructs lossless Python dicts for nodes and statements (restoring `bool` when `value_type == 'boolean'`, `qualifiers.quantity` when `qual_qty_unit IS NOT NULL`, `inheritedFrom` when `inherited_from IS NOT NULL`).
  - Query methods:
    - `meta() -> dict`
    - `list_nodes(*, kind=None, prefix=None, namespace=None, identifier=None, q=None, limit=50, offset=0) -> dict` (returns `{items, total, limit, offset, hasMore}` ordered by `id`)
    - `get_node(node_id: str) -> dict` (node + identifiers + source + colocated guide if present)
    - `list_statements(*, subject=None, target=None, predicate=None, property=None, scope=None, basis=None, state=None, geography=None, active_on=None, limit=50, offset=0) -> dict` (`active_on` filters to rows where `valid_until IS NULL OR valid_until >= active_on`)
    - `search(query: str, *, kind=None, limit=50, offset=0) -> dict` — sanitizes user query tokens before FTS5 `MATCH` so punctuation (`08 50 00`, `Si-O`, `A1-A3`) never throws `sqlite3.OperationalError`.
    - `facts(node_id: str, *, include_inherited: bool = True) -> dict`
    - `walk(node_id: str, *, trace: bool) -> dict` (`parts` / `trace` traversals over indexed SQLite lookups)
    - `used_by(node_id: str) -> dict`
    - `compare(left_id: str, right_id: str) -> dict` (diffs `facts`, `materials`, `parts`, `processes`, surfacing `inheritedFrom` and `siQuantity` alongside verbatim `quantity` so imperial vs. SI sources compare cleanly)
    - `explain(key: str) -> dict` (reads `node_guides` / `property_guides`)
    - `cite(statement_id: str, assets: Path) -> dict` (resolves saved blob vs `link-only`, verifies SHA-256)
    - `gaps(assets: Path, node_id: str | None = None, *, tier: str = "assembly") -> dict`

### 3. Tiered `gaps --tier <catalog|assembly|atomic>` (`store.py`)
- **`catalog`**:
  - Checks `productModel` (`manufacturedBy`), `productVariant` (`isVariantOf` + `realizesDesign`), archived `source` blobs (`source-not-archived`), and `unknown`/`withheld` property claims.
  - Ignores unpopulated taxonomy spine stubs (`qualifiers.role == 'taxonomy-division'`), leaf material breakdowns, and atomic chemistry.
- **`assembly`** *(default)*:
  - Everything in `catalog` + leaf `referenceDesign` (excluding `taxonomy-division` spine stubs) has `madeOf` and upstream `produces`, `productModel`/`productVariant` has upstream `produces`, `process` has `performedBy`, and `fabrication` + `installation` stages are present.
- **`atomic`**:
  - Everything in `assembly` + every `material` has `hasComposition` or `hasStructure` and upstream `produces`, every `structureModel` has `includesChemical`, and all four core stages (`extraction`, `fabrication`, `distribution`, `installation`) are present.

### 4. `building_materials/audit.py`
- `run_audit(store: MaterialStore, assets: Path) -> dict`:
  - Operates purely over `MaterialStore` + `.materials/blobs/` (never parses YAML).
  - Preserves all existing checks: duplicate `(origin, sha256)`, blob SHA-256 mismatch, unused source, orphan node, shared-slot contamination, model missing manufacturer, variant missing design/model, requirement missing target, process missing `qualifiers.role`, property missing guide, numeric property missing scope, `pypdf` page bounds / numeric value / quote / table-figure checks.
  - **Inheritance optimization:** Skips redundant `pypdf` extraction for statements where `inherited_from IS NOT NULL` (the origin statement is already audited).

### 5. CLI Wiring (`cli.py`)
Add/wire all remaining query subcommands against `ensure_db` + `MaterialStore`:
- Global flag: `--no-rebuild` (disables auto-rebuild when pointing at a prebuilt `--db`).
- Commands: `build [--force]`, `audit`, `nodes`, `search`, `parts`, `trace`, `used-by`, `facts`, `compare`, `gaps [node_id] [--tier catalog|assembly|atomic]`, `explain`, `cite`.

---

## Playable Checkpoint & Verification

1. `python -m building_materials build` creates `.materials/materials.db` and reports node/statement/citation counts + fingerprint.
2. `python -m building_materials audit` exits `0` (`"ok": true`, `"errors": 0`) across all seeded + CSV-expanded Vitro Solarban 70 claims against real archived PDFs.
3. `python -m building_materials parts envelope.openings.window` walks from assembly down to `chem.si` / `chem.na-ion`.
4. `python -m building_materials compare product.vitro.solarban-70.solargray-air product.vitro.solarban-70.solargray-argon` (using the exact seeded IDs from Slice 02) shows distinct cavity fill (`air` vs `argon`), U-factor diff, and shared inherited model claims.
5. `python -m building_materials search "08 50 00"` and `search silicate` return ranked FTS5 matches without crashing on punctuation.
6. `python -m building_materials gaps --tier catalog`, `--tier assembly`, and `--tier atomic` produce distinct, expected summaries (and taxonomy spine stubs like `substructure` / `mep` do not flood `gaps`).
7. Editing any YAML file under `data/` and running `facts` triggers automatic atomic rebuild of `.materials/materials.db`.

---

## Delegated Decisions

The implementer may choose:
- Exact FTS5 query tokenization/escaping helper in `store.py`.
- Whether `walk` / `used_by` uses recursive CTEs in SQLite or iterative indexed `SELECT`s (both are fast; choose whichever is clearest and cleanest).
- Exact `build_meta` timestamp format (ISO-8601 UTC).

## What Must Stay Green

- `qualifiers.quantity` (e.g., oxide mass-% ranges on `soda-lime-glass`) and boolean property values round-trip identically from YAML → SQLite → CLI JSON.
- Zero YAML parsing occurs in `store.py` or `audit.py`.
