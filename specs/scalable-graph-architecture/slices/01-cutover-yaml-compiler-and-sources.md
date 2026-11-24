# Slice 01 — Cutover, Modular YAML Compiler & Source Import

## Contract Unlocked

A human-readable, modular YAML authoring format under `data/` compiles deterministically into the validated canonical graph + guide IR, and `import-source --id <slug>` archives sources directly into `data/sources/<slug>.yaml` + `.materials/blobs/` with slug-immutability protection. All legacy monolithic JSON fixtures, prototype 3D UI, and old tests are removed cleanly.

---

## Scope & Hard Cutover

### Delete Immediately (No Shims, No Migration Scripts)
- `fixtures/building.json`, `fixtures/building.guide.json` (and empty `fixtures/` directory)
- `viewer.html`
- `ui/` (entire directory)
- `tests/test_building_graph.py`
- `building_materials.py` (replaced by the `building_materials/` package)
- Remove all `.materials/sources/` discovery/write logic (keep `.materials/blobs/` untouched!)

### Dependencies (`requirements.txt`)
Add `PyYAML>=6.0,<7` alongside existing `jsonschema>=4.18,<5` and `pypdf>=4,<6`.

---

## API Seams & Ownership

### 1. `building_materials/model.py`
- Constants: `ROOT`, `DEFAULT_DATA = ROOT / "data"`, `DEFAULT_ASSETS = ROOT / ".materials"`, `DEFAULT_DB = DEFAULT_ASSETS / "materials.db"`, `COMPOSITION`, `USED_BY`, `TRACE_FORWARD`, `TRACE_REVERSE`, `LINK_KINDS`, `GAP_TIERS = ("catalog", "assembly", "atomic")`.
- Typed dataclasses:
  - `Provenance(file: str, line: int | None = None, row: int | None = None)`
  - `CompiledBundle(nodes: list[dict], statements: list[dict], guide: dict, provenance: dict[str, Provenance], fingerprint: str)`
- Exceptions: `CompileError(Exception)` (carries `provenance` formatting), `GraphValidationError(Exception)`.

### 2. `building_materials/sources.py`
- `asset_path(assets: Path, digest: str, media_type: str) -> Path` (content-addressed `.materials/blobs/<sha256><ext>`).
- `publish_once(path: Path, data: bytes) -> None` (atomic temp-file write + link/replace, Windows-safe).
- `import_source(location: str, *, slug: str, data_dir: Path, assets: Path, url: str | None = None, title: str | None = None, issuer: str | None = None, revision: str | None = None, expect_sha256: str | None = None) -> dict`:
  - Validates `slug` matches dotted ID pattern (`^[a-z0-9]+([.-][a-z0-9]+)*$`).
  - Fetches HTTP(S) or local file (`--url` required for local), computes SHA-256, verifies `expect_sha256` if provided, publishes immutable blob to `.materials/blobs/<sha256><ext>`.
  - Writes tracked YAML to `data/sources/<slug>.yaml` with node ID `source.<slug>` (or `<slug>` if already prefixed with `source.`).
  - **Immutability Firewall:**
    - If `data/sources/<slug>.yaml` already exists with the same `(origin, sha256)`: idempotent no-op, return existing record.
    - If it exists with a *different* `origin` or `sha256`: raise `ValueError` refusing overwrite and instructing the caller to mint a new versioned slug (e.g. `<slug>-v2`).
    - If *another* file in `data/sources/` already records the same `(origin, sha256)`: return the existing record with a `duplicateOf` notice instead of creating a duplicate manifest.

### 3. `building_materials/compiler.py`
- **Date-Safe YAML Loader:** Subclass `yaml.SafeLoader` stripping implicit timestamp/date resolvers so ISO dates like `2026-01-15` remain `str` (preventing `jsonschema` `format: date` failures).
- **Recursive Discovery:** Walks `data/**/*.yaml` and `data/**/*.yml` in deterministic sorted relative-path order. Computes `data_fingerprint` (SHA-256 over sorted `(relpath, content_bytes)` of all `.yaml`, `.yml`, and referenced `.csv` files).
- **Entity-Centric YAML Authoring Format:**
  - Top-level keys supported per file:
    - `defaults:` (optional file-level defaults for `basis`, `evidence`, `scope`, `method`, `conditions`, `qualifiers`)
    - `entities: [...]` (list of entity blocks) OR a single entity mapping (`id:` at top level, e.g. `data/sources/<slug>.yaml`)
    - `propertyGuides: { <prop>: { title, summary, ... } }` (e.g. `data/guides/properties.yaml`)
  - Each entity block supports:
    - Core node fields: `id`, `kind`, `label`, `description`, `revision`, `scale`, `stage`, `identifiers`, `source`
    - Optional entity-level `defaults:` (overrides file-level `defaults`, deep-merging `evidence[0].locator` when an item specifies a partial `locator` without repeating `source`)
    - `links: [...]` — each lowers to a predicate statement (`subject` auto-filled from entity `id`)
    - `properties: [...]` — each lowers to a property statement (`subject` auto-filled from entity `id`)
    - `guide: {...}` — lowers into `guide["nodes"][entity_id]`
- **Deterministic Statement ID Synthesis:**
  - If `id:` is explicitly provided on a link/property, use it as-is (required when referenced by `derivedFrom`).
  - Otherwise synthesize:
    - Link: `<subject>.<predicate>.<target>` (plus `.<role>` or `.<position>` if present)
    - Property: `<subject>.<property>` (plus `.<scope>` if present)
  - Normalize synthesized slug to `[a-z0-9._-]`. If a synthesized ID collides with an earlier synthesized ID, append `.<sha256_6>` computed from the canonical JSON of `(subject, predicate/property, target, scope, qualifiers, value/quantity/state)`. Explicit `id:` duplicates remain hard errors.
- `compile_dir(data_dir: Path) -> CompiledBundle` (pure function, no DB writes).

### 4. `building_materials/validator.py`
- `validate_bundle(bundle: CompiledBundle) -> CompiledBundle`:
  - Validates `{schemaVersion: 1, nodes, statements}` against `graph.schema.json` and `{schemaVersion: 1, properties, nodes}` against `guide.schema.json` (Draft 2020-12 + `FORMAT_CHECKER`).
  - Enforces unique node/statement IDs, valid `LINK_KINDS` endpoint kinds, acyclic `hasPart` and `derivedFrom` graphs (`graphlib.TopologicalSorter`), `quantity.min <= quantity.max`, PDF `evidence` requires `locator.page`, and `guide["nodes"]` keys exist in `nodes`.
  - Raises `GraphValidationError` with node/statement ID and source file provenance.

### 5. `building_materials/cli.py` & `__main__.py`
- Global flags: `--data <dir>` (default `data/`), `--assets <dir>` (default `.materials/`), `--db <path>` (default `.materials/materials.db`).
- Subcommands wired in Slice 01:
  - `validate` — runs `compile_dir` + `validate_bundle`, prints JSON summary (`valid`, `nodes`, `statements`, `guideNodes`, `guideProperties`, `fingerprint`).
  - `import-source <location> --id <slug> [--url ...] [--title ...] [--issuer ...] [--revision ...] [--expect-sha256 ...]`.

---

## Minimal Source-Backed Window Seed (`data/`)

Seed `data/` with a compact, verified window vertical slice from assembly down to atomic silicate network + value chain, reusing PDFs already archived in `.materials/blobs/`:

| Source ID | Origin URL | Archived SHA-256 (in `.materials/blobs/`) |
| --- | --- | --- |
| `source.ua-window-guidelines` | `https://constructionpublicinfo.ua.edu/wp-content/uploads/Design-Guidelines/Section-III/Division-08-Openings/08-50-00-Windows.pdf` | `3c903c499596b4f5ce083191d16528e43542c6b74bcc86755c32cb287db4c7b0` |
| `source.vitro-solarban-70` | `https://vitroglazings.com/media/0wapqqqk/pds_solarban_70.pdf` | `2eb6adbb1870afdb6b5d2da57a71f9f92b4c6d0af406e8b3c649692f99759dde` |
| `source.flat-glass-structure` | `https://www.mdpi.com/2075-5309/16/3/506` | `f1018bd939279dd276e793f835653c16612617c2a51135795657b168fed5100f` |
| `source.usgs-silica-2025` | `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-sand-industrial.pdf` | `b05ed24cba39da15415a4ec299a2c6002a3895a5d6c8b1ad17c5409cda6d19c9` |
| `source.usgs-soda-ash-2025` | `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-soda-ash.pdf` | `a386ee59806756e28c72f2fde95eaa3b68068e0614f1e0228fd13007be920ff5` |
| `source.usgs-stone-2025` | `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-stone-crushed.pdf` | `44034b1589db025caba3e22788590b4bdbab303903de98d601e9eb552a2d92fc` |
| `source.usgs-silver-2025` | `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-silver.pdf` | `1aa6e68c9700f88e97d4cbf31fc039d45d4b1b738a09f6bfece8edac0ec59b24` |
| `source.usgs-aluminum-2025` | `https://pubs.usgs.gov/periodicals/mcs2025/mcs2025-aluminum.pdf` | `995f59efae5fba7525c967d3b65af886cbba4faaac320cb843de9b6d84722d2b` |

Seed folders:
- `data/sources/*.yaml` (8 files above)
- `data/guides/properties.yaml` (property guides for seeded properties)
- `data/actors/core.yaml` (Vitro, UA, USGS, float-glass/glazing trade actors)
- `data/chemistry/silicate.yaml` (`chem.sio2`, `chem.na2o`, `chem.cao`, `chem.si`, `chem.o`, `chem.na-ion`, `chem.ca-ion`, `chem.ag`, `chem.al`, `chem.n2`, `chem.ar`, `structure.amorphous-silicate-network`)
- `data/materials/glass.yaml` (silica sand, soda ash, limestone, soda-lime glass with mass-% `qualifiers.quantity`, triple-silver low-e coating, dry air, argon, 6063-T6 aluminum)
- `data/systems/envelope/window.yaml` (`envelope.openings.window` → frame, sash, IGU → outer pane, inner pane, cavity, spacer, seal + minimal value-chain processes across extraction, fabrication, distribution, installation)

---

## Playable Checkpoint & Verification

1. Verify deleted legacy paths (`fixtures/`, `viewer.html`, `ui/`, `tests/test_building_graph.py`, `building_materials.py`) are gone.
2. Run:
   ```text
   python -m building_materials validate
   ```
   Confirm exit `0` and JSON output showing non-zero `nodes`, `statements`, `guideNodes`, `guideProperties`, and a deterministic `fingerprint`.
3. Smoke-test `import-source` in a temporary directory:
   - Import a local PDF with `--id demo-doc --url https://example.com/demo.pdf` → writes `data/sources/demo-doc.yaml` and `.materials/blobs/<sha>.pdf`.
   - Re-import identical bytes with `--id demo-doc` → succeeds idempotently.
   - Re-import modified bytes with `--id demo-doc` → exits non-zero refusing to overwrite.

---

## Delegated Decisions

The implementer may choose:
- Internal helper decomposition inside `compiler.py` and `validator.py`.
- Exact formatting/key ordering of YAML written by `import-source` (as long as it round-trips through `compile_dir` + `validate_bundle`).
- Exact subset of window subparts/processes beyond the required assembly → IGU → glass → atomic silicate network + 4-stage value chain spine.

## What Must Stay Green

- `graph.schema.json` and `guide.schema.json` remain the canonical compiled-IR schemas.
- Every seeded PDF claim cites real page/table/row locators present in the corresponding archived blob in `.materials/blobs/`.
