# Scalable Building Materials Graph Architecture

## Next Agent Prompt

You are implementing the **Scalable Building Materials Graph Architecture** spec under `specs/scalable-graph-architecture/`.

- **Status:** All 4 slices complete and verified (last updated 2026-11-24).
- **Next pickup point:** Spec complete—ready for `close-spec` archiving or adding new building systems/product catalogs under `data/`.
- **Active warnings / constraints:**
  - **Hard cutover completed:** Legacy `fixtures/`, `viewer.html`, `ui/`, `tests/test_building_graph.py`, and `building_materials.py` are deleted.
  - **Minimal tests (`AGENTS.md`):** Keep tests minimal—test end-to-end paths only (`tests/test_e2e.py`).
- **Global TODO Checklist:**
  - [x] [Slice 01](slices/01-cutover-yaml-compiler-and-sources.md): Hard cutover, package skeleton (`model`, `sources`, `compiler`, `validator`, `cli`), date-safe entity-centric YAML compiler, `import-source --id <slug>`, minimal window seed.
  - [x] [Slice 02](slices/02-taxonomy-spine-sku-matrix-and-epd.md): 6-domain whole-building taxonomy spine, dotted namespaced IDs, `productModel` → `productVariant` inheritance, CSV/YAML SKU matrix expansion (Vitro Solarban 70 proof), EN 15804 EPD/GWP rules, SI unit normalization, first-class EPD temporal/geo fields.
  - [x] [Slice 03](slices/03-sqlite-runtime-store-gaps-and-audit.md): Lossless `schema.sql` v2, SQLite primary runtime store (`store.py`), FTS5 search, staleness auto-rebuild, tiered `gaps --tier`, SQLite-backed `audit.py`.
  - [x] [Slice 04](slices/04-json-http-api-docs-and-e2e-tests.md): Headless filtered/paginated JSON HTTP API (`server.py`), docs & skill updates, minimal E2E test suite (`tests/test_e2e.py`).
- **Handoff rule:** Before ending your pass, update this **Next Agent Prompt** section (status, date, checked TODO items, next pickup point, and any new findings or blockers).

---

## Goal

Replace the monolithic `fixtures/building.json` + in-memory JSON loader + prototype 3D viewer with a **clean, scalable, source-backed building materials graph architecture** that:

1. **Authors cleanly for humans** in modular, entity-centric YAML (+ tabular CSV SKU matrices) under `data/`.
2. **Covers the entire building** using a 2050 Materials–style multi-axis taxonomy (Building System spine + Product Type/Family + Material Type/Family + standard `identifiers`) and scales to hundreds/thousands of product SKUs via model inheritance, tabular expansion, EN 15804 EPD conventions, and tiered `gaps`.
3. **Queries fast at scale** by promoting SQLite (`schema.sql` v2 + FTS5) to the primary runtime read store behind both the CLI and a headless, filtered/paginated JSON HTTP API (`serve`).

---

## Locked Decisions

| Decision | Choice | Rationale & Alternatives Considered |
| --- | --- | --- |
| **Cutover & legacy data** | **Hard cutover, fresh slate.** Delete `fixtures/`, `viewer.html`, `ui/`, `tests/test_building_graph.py`, and monolithic `building_materials.py`. Seed `data/` with a minimal, source-backed window vertical slice reusing archived PDFs in `.materials/blobs/`. | User explicitly discarded the 3D prototype, old tests, and masonry fixture in favor of a clean slate. No compatibility shims or migration scripts. |
| **Query & review surface** | **CLI + SQLite + headless JSON HTTP API (`serve`).** No HTML frontend. | Keeps this spec focused on data architecture and query contracts; any future UI can consume the paginated JSON API cleanly. |
| **Authoring vs. IR** | Author in modular entity-centric YAML (+ CSV SKU matrices) under `data/`; compile & validate into canonical `nodes + statements + guides` IR, then materialize into SQLite (`.materials/materials.db`). | Solves human readability, git diffs, and repetition without discarding the proven normalized graph model (`graph.schema.json`, `guide.schema.json`). |
| **Taxonomy model** | Multi-axis (reconciling 2050 Materials, ISO 12006-2, IFC/bSDD, openEPD, and HPD): (1) **Element-centric** 6-domain `referenceDesign` building spine (`substructure`, `superstructure`, `envelope`, `interiors`, `mep`, `siteworks`), (2) attachable cross-standard `identifiers` (`uniformat2`, `omniclass`, `uniclass`, `masterformat`, `nrm1`, `icms`, `ifc`, `bsdd`, `etim`, `gtin`, `nfrc`, `openepd`, `hpd`, `cas`), (3) shared `materials/` + `chemistry/` layer. | See **Standards Reconciliation & Architectural Choices** below for what reconciles cleanly vs. where explicit choices are required. |
| **SKU inheritance** | **Compile-time materialization** from `productModel` (`variantDefaults` + model properties) onto `productVariant` with an `inherited_from` provenance column in SQLite. | *Alternative considered:* pure query-time resolution in `store.py`. Compile-time materialization was chosen so direct SQLite queries, `/api/statements` filters, and `compare` all see complete variant claims with one owner, while `inherited_from` preserves provenance and lets `audit` skip duplicate PDF checks. |
| **Deterministic statement IDs** | Human-readable slug (`<subject>.<pred_or_prop>.<target_or_scope>`) when unique, appending `.<sha256_6>` only on collision; explicit `id:` supported (and required for `derivedFrom` targets). | Readable in `cite` output and stable across YAML reorders without silent collisions on dual panes or competing claims. |
| **Source registry** | Single canonical registry in `data/sources/<slug>.yaml`, written directly by `import-source --id <slug>`; `.materials/sources/` eliminated. | Permanently eliminates duplicate source manifests and manual cleanup. |

---

## Standards Reconciliation & Architectural Choices

Outside 2050 Materials, the AEC ecosystem has several major standards that operate at **different layers of the building stack**. Most are **compatible and reconcilable** via attachable `identifiers` and statement conventions; four represent **genuine structural forks** where the graph must make an explicit choice.

### 1. Reconcilable Standards (Attachable Facets — No Conflict)

| Layer | Standards | How They Reconcile in This Graph |
| --- | --- | --- |
| **Building Classification (ISO 12006-2)** | **Uniformat II** (ASTM E1557), **OmniClass** (Tables 21/22/23/41), **Uniclass 2015** (`En`/`Ss`/`Pr`/`Ma`), **CSI MasterFormat**, **RICS NRM 1**, **ICMS** | Attached as multi-valued `node.identifiers` (just like IFC's `IfcRelAssociatesClassification`), so one node can simultaneously carry its Uniformat element code, MasterFormat spec section, Uniclass system/product code, and NRM 1 group. |
| **BIM & Semantic Dictionaries** | **IFC (ISO 16739)** (`IfcWindow`, `IfcWall`, `IfcMaterialLayerSet`), **bSDD** (buildingSMART Data Dictionary, ISO 23386) | IFC class names (`ifc`) and bSDD URIs (`bsdd`) attach as `node.identifiers` on `referenceDesign` / `material` nodes and as optional `externalRefs` (`ifcPset`, `bsdd`, `openepd`, `etim`) on `propertyGuides`. |
| **Product & MEP Catalogs** | **ETIM** (MEP/electrical/HVAC/hardware attributes), **GS1 / GTIN**, **NFRC** | Attached as `identifiers` (`etim`, `gtin`, `nfrc`) on `productModel` and `productVariant` nodes. |
| **Embodied Carbon / LCA** | **openEPD** (Building Transparency / EC3), **EN 15804+A2**, **ISO 21930**, **ILCD+EPD** | Reconciled via `identifiers` (`openepd` UUID) + `statement` conventions (`property: gwp*`, EN 15804 `scope: A1-A3` etc., `quantity.unit` containing `CO2e`, required `quantity.basis` declared unit, `method: EN 15804+A2`). |
| **Material Health & Chemistry** | **HPD Open Standard** (HPDC), **CAS RN** | Reconciles directly with `hasComposition`: `(material) --hasComposition--> (chemicalEntity with cas: <CAS RN>)` carrying `qualifiers.quantity` (`min`/`max`, `%`, `basis: mass`) and `qualifiers.role` (network former, plasticizer, flame retardant). |
| **Units** | **UCUM** | Optional canonical `ucumUnit` metadata on `propertyGuides` enables unit normalization across imperial (NFRC) and SI (ISO/EN/IFC) sources without mangling source-faithful claim quantities. |

### 2. Genuine Structural Forks (Explicit Choices Locked Here)

1. **Primary `hasPart` Spine — Physical Element/Assembly (Uniformat II / IFC) vs. Trade/Spec (MasterFormat) vs. Operational Topology (BOT / Brick):**
   - *Conflict:* A single assembly (e.g. reinforced concrete slab or curtain wall) spans multiple MasterFormat trade divisions, while MEP operational graphs (`AHU feeds VAV feeds Zone`) represent fluid/energy flow rather than physical part containment.
   - *Choice:* Use **physical element/assembly composition (Uniformat II / IFC)** as the sole `hasPart` spine (`building → envelope → openings → window`). Keep MasterFormat / OmniClass / Uniclass / NRM 1 as classification `identifiers`. If MEP operational topology is added later, introduce a dedicated `feeds`/`serves` predicate rather than overloading `hasPart`.
2. **Entry-Point Model — Generic-First (2050 Materials) vs. EPD-First (openEPD) vs. Ingredient-First (HPD):**
   - *Conflict:* Generic-first models lose plant/SKU specificity; EPD-first models lack assembly anatomy; HPD-first models lack structural/thermal performance.
   - *Choice:* Keep the **3-layer bridge** (`referenceDesign` generic slot ↔ `productModel`/`productVariant` SKU/EPD ↔ `material`/`chemicalEntity` HPD-style composition & atomic structure) paired with `--tier catalog|assembly|atomic` in `gaps`. **Concrete products** (`productModel`/`productVariant`) carry primary performance and EPD benchmarks (`measured`, `simulated`, `manufacturer-declared`), while generic `referenceDesign`/`material` nodes may optionally carry `basis: typical-reference` median/range benchmarks (kept strictly distinct via `basis`).
3. **Property Naming & Unit Normalization — Canonical Internal Keys + Verbatim & Auto-Computed SI Quantities (Option C):**
   - *Conflict:* IFC uses `Pset_WindowCommon.ThermalTransmittance` (`W/(m²·K)`), NFRC uses `U-Factor` (`Btu/(h·ft²·°F)`), and openEPD uses `gwp.A1A2A3`. Adopting one raw external naming scheme hurts readability, while storing only raw imperial/SI units breaks cross-region comparison.
   - *Choice:* Keep concise canonical internal property keys (`uFactor`, `gwp`, `density`) in `data/guides/properties.yaml` with optional `externalRefs` (`bsdd`, `ifcPset`, `openepd`, `etim`) + canonical `ucumUnit`. Preserve **verbatim source `quantity`** on every statement (so `audit` verifies exact numbers against archived PDFs) **and** auto-compute normalized **SI quantities (`si_value`, `si_min`, `si_max`, `si_unit`)** at compile time for cross-unit `compare` and SQL range queries.
4. **Temporal, Geographic & Plant Scope of Claims — First-Class EPD Columns (Option B):**
   - *Conflict:* `openEPD` and `HPD` records carry manufacturing plant, geography/grid region, PCR version, and expiration (`validUntil`) dates that timeless physics constants do not.
   - *Choice:* Add first-class optional fields (`validUntil` on `source` and `statement`, plus `geography`, `pcr`, and `plantActor` on `statement`) in `graph.schema.json`, `schema.sql` v2, and `/api/statements` filters so regional, plant-specific, and unexpired-EPD queries work natively from day one.

---

## Single-Owner Architecture & Module Seams

The codebase should read as if designed today—one owner per concept, unidirectional data flow, zero parallel abstractions:

```text
data/**/*.yaml + data/**/*.csv          .materials/blobs/<sha256>.<ext>
            │                                         ▲
            ▼                                         │
  building_materials/compiler.py        building_materials/sources.py
            │                           (blob archive + import-source)
            ▼
  building_materials/validator.py
            │
            ▼
  building_materials/store.py   ──▶  .materials/materials.db (SQLite v2 + FTS5)
       ┌────┴────┬──────────┐
       ▼         ▼          ▼
   cli.py   server.py   audit.py
```

| Module | Single Owner Of | Must NOT Own |
| --- | --- | --- |
| `building_materials/model.py` | Domain constants (`LINK_KINDS`, traversal sets, `TAXONOMY_DOMAINS`, `IDENTIFIER_NAMESPACES`, `EN15804_SCOPE_RE`, `GAP_TIERS`), typed IR bundle dataclasses, custom errors (`CompileError`, `ValidationError`). | I/O, SQLite, HTTP, YAML parsing. |
| `building_materials/sources.py` | Content-addressed `.materials/blobs/` archive, HTTP/local fetching, SHA-256 verification, `publish_once`, `import-source --id <slug>` → `data/sources/<slug>.yaml` with slug-immutability check. | Graph compilation or SQLite writes. |
| `building_materials/compiler.py` | Date-safe PyYAML loading, recursive `data/` scan, block/entity `defaults` deep-merge, `variantDefaults` inheritance, CSV/YAML SKU matrix expansion, deterministic statement IDs, `data_fingerprint` hashing. | SQLite queries, PDF parsing, HTTP. |
| `building_materials/validator.py` | All static invariants: Draft 2020-12 JSON Schema (`graph.schema.json`, `guide.schema.json`), dotted namespaced IDs, endpoint kinds, DAG acyclicity (`hasPart`, `derivedFrom`), quantity bounds, PDF page rule, inheritance constraints, EN 15804 EPD/GWP rules. | File I/O beyond loading schemas; runtime queries. |
| `building_materials/store.py` | SQLite v2 atomic build (temp file + `os.replace`), `build_meta` staleness guard (`ensure_db`), FTS5 search, and all runtime read queries (`list_nodes`, `get_node`, `list_statements`, `facts`, `walk`, `used_by`, `compare`, `gaps`, `explain`, `cite`). | YAML parsing, HTTP serialization. |
| `building_materials/audit.py` | External-artifact & modeling-convention verification over `store.py` + `.materials/blobs/`: blob SHA-256 integrity, duplicate `(origin, sha256)`, unused sources, orphan nodes, shared-slot contamination, missing property guides, `pypdf` page/number/quote/locator verification. | YAML parsing or schema validation. |
| `building_materials/server.py` | Headless JSON-only `ThreadingHTTPServer`, per-request read-only SQLite connections (`file:<db>?mode=ro`), pagination & error envelopes, `/assets/<blob>` path-traversal guard. | HTML rendering, business/graph logic. |
| `building_materials/cli.py` + `__main__.py` | Thin `argparse` CLI wiring (`python -m building_materials ...`) and JSON stdout / stderr formatting. | Graph algorithms or SQL queries. |

---

## Slice Ladder

```text
[Slice 01] Cutover, Package Skeleton, Entity-Centric YAML Compiler & import-source
    │
    ▼
[Slice 02] Whole-Building Taxonomy Spine, SKU Inheritance, Tabular Matrix & EPD Rules
    │
    ▼
[Slice 03] Lossless SQLite v2 Runtime Store, Tiered gaps & SQLite-Backed audit
    │
    ▼
[Slice 04] Headless Filtered/Paginated JSON HTTP API, Docs & Minimal E2E Suite
```

| Slice | Primary Seam | Playable Checkpoint |
| --- | --- | --- |
| [01](slices/01-cutover-yaml-compiler-and-sources.md) | `compiler.py` + `validator.py` + `sources.py` | Legacy files gone; `validate` passes on modular YAML window seed; `import-source --id <slug>` writes `data/sources/<slug>.yaml` + blob and blocks slug mutation. |
| [02](slices/02-taxonomy-spine-sku-matrix-and-epd.md) | `compiler.py` (matrix/inheritance) + `validator.py` (EPD/taxonomy) | 6-domain building spine wired; Vitro Solarban 70 CSV matrix expands into multiple inheriting `productVariant`s; EN 15804 `gwp` rules enforced. |
| [03](slices/03-sqlite-runtime-store-gaps-and-audit.md) | `schema.sql` v2 + `store.py` + `audit.py` | `build` materializes lossless SQLite DB; `audit` passes (`errors: 0`) against real PDFs; `parts`, `trace`, `compare`, `search`, `gaps --tier catalog\|assembly\|atomic` all run from SQLite. |
| [04](slices/04-json-http-api-docs-and-e2e-tests.md) | `server.py` + `tests/test_e2e.py` | `serve` exposes filtered/paginated `/api/*` + `/assets/<blob>`; `README.md` & skill updated; `python -m unittest discover -s tests -v` passes minimal E2E suite. |

---

## Standing Verification Gates

Every slice must satisfy before moving on:
1. **Zero legacy residue:** No references to `fixtures/building.json`, `viewer.html`, `ui/`, or `.materials/sources/` remain in code.
2. **Real-PDF grounding:** All seeded window & Vitro Solarban 70 claims cite real archived PDFs in `.materials/blobs/` with exact page/table/row locators.
3. **Minimal E2E discipline (`AGENTS.md`):** Tests exercise CLI and HTTP end-to-end paths only—no unit tests of private internals.
4. **Clean CLI exit codes:** `validate` and `audit` exit `0` on valid inputs and `1` with actionable file/line/node diagnostics on invalid inputs.
