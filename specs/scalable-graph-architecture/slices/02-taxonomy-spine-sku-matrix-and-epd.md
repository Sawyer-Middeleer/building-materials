# Slice 02 — Whole-Building Taxonomy Spine, SKU Inheritance, Tabular Matrix & EPD Rules

## Contract Unlocked

The graph scales cleanly across **all building systems** (2050 Materials–style multi-axis classification) and **hundreds of product SKUs** (model inheritance + tabular CSV/YAML matrix expansion + EN 15804 EPD/GWP conventions), proven end-to-end on real Vitro Solarban 70 glazing configurations from the archived PDF.

---

## API Seams & Data Contracts

### 1. Whole-Building Taxonomy Spine (`data/systems/building.yaml`)
Add a root `building` `referenceDesign` linked via `hasPart` (`qualifiers.role: taxonomy-division`) to the 6 top-level building domains, each carrying standard classification `identifiers`:

| Node ID | Label | `uniformat2` | `uniclass` | `masterformat` | `nrm1` |
| --- | --- | --- | --- | --- | --- |
| `building` | Building (Whole Structure) | — | `En_00` | — | `0` |
| `substructure` | Substructure & Foundations | `A` | `Ss_20` | `03 30 00` | `1` |
| `superstructure` | Superstructure & Structural Frame | `B10` | `Ss_25` | `05 00 00` | `2` |
| `envelope` | Building Envelope / Shell | `B20` | `Ss_25_30` | `07 00 00` | `2.5` |
| `interiors` | Interior Construction & Finishes | `C` | `Ss_35` | `09 00 00` | `3` |
| `mep` | Mechanical, Electrical & Plumbing (MEP) | `D` | `Ss_50` | `21 00 00` | `5` |
| `siteworks` | Siteworks & External Works | `G` | `Ss_15` | `31 00 00` | `8` |

Connect the Slice 01 window assembly into the spine: `envelope` → `envelope.openings` (`uniformat2: B2020`, `masterformat: 08 50 00`) → `envelope.openings.window`.

### 2. Controlled ID, Identifier & Cross-Standard Mapping Conventions (`model.py` + `validator.py` + `guide.schema.json`)
- Dotted lowercase ID convention enforced in `validator.py`: `^[a-z0-9]+([.-][a-z0-9]+)*$` (also update `graph.schema.json` ID pattern or enforce in `validator.py` while keeping `graph.schema.json` compatible).
- Recognized cross-standard identifier namespaces in `model.py`:
  - Classifications (ISO 12006-2 / cost): `uniformat2`, `omniclass`, `uniclass`, `masterformat`, `nrm1`, `icms`
  - BIM & semantic dictionaries: `ifc`, `bsdd`
  - Product / SKU / rating registries: `etim`, `gtin`, `nfrc`, `astm`
  - Sustainability & material health / chemistry: `openepd`, `epd`, `hpd`, `cas`
  - *(Other namespaces remain allowed; `validator.py` rejects empty values or duplicate `(namespace, value)` pairs on the same node.)*
- **Property crosswalk metadata (`guide.schema.json`):** Extend `#/$defs/propertyGuide` with optional `ucumUnit` (string) and optional `externalRefs` object (keys such as `bsdd`, `ifcPset`, `openepd`, `etim`) so canonical internal property keys (`uFactor`, `gwp`, `density`) remain human-readable while mapping cleanly to IFC/bSDD/openEPD/ETIM.
- **Seeded cross-standard proof:** Tag `envelope.openings.window` with `ifc: IfcWindow` (alongside `uniformat2`, `uniclass`, `masterformat`, `nrm1`), tag `chem.sio2` with `cas: 7631-86-9` (HPD-compatible chemical identity), and populate `externalRefs` + `ucumUnit` on `uFactor` and `gwp` in `data/guides/properties.yaml`.

### 3. `productModel` → `productVariant` Inheritance (`compiler.py` + `validator.py`)
- **Validation rules (`validator.py`):**
  - A `productVariant` may have at most one `isVariantOf` link, targeting a `productModel`.
  - A `productModel` must not have `isVariantOf`.
- **Compile-time inheritance (`compiler.py`):**
  - A `productModel` entity may declare:
    - Direct `properties:` (shared model-level claims)
    - Optional `variantDefaults:` block (`links:` and `properties:` templates applied to every child `productVariant` linked via `isVariantOf`).
  - When lowering any `productVariant` linked to a `productModel`:
    - Inherit `variantDefaults.links` unless the variant explicitly declares a link with the same `(predicate, qualifiers.role, qualifiers.position)`.
    - Inherit model `properties` and `variantDefaults.properties` unless the variant explicitly declares a property with the same `(property, scope)`.
    - Tag every inherited statement with metadata `inheritedFrom: <origin_statement_id>` (carried in `CompiledBundle` for SQLite storage in Slice 03; stripped before `graph.schema.json` validation if `additionalProperties: false` is kept strict, or added as an optional string field on `#/$defs/statement` in `graph.schema.json` — **lock choice:** add optional `inheritedFrom` string field to `#/$defs/statement` in `graph.schema.json` so IR and SQLite stay 1-to-1).

### 4. Tabular SKU Matrix / CSV Expansion (`compiler.py`)
A `productModel` entity (or standalone matrix YAML file) may declare a `variantsTable:` block:

```yaml
variantsTable:
  csv: vitro-solarban-70-igus.csv      # path relative to YAML file (or inline `rows: [...]`)
  idTemplate: "product.vitro.solarban-70.{sku}"
  labelTemplate: "Vitro Solarban 70 — {label}"
  defaults:
    basis: manufacturer-declared
    scope: center-of-glass
    method: "NFRC 100 / 200"
    evidence:
      - source: source.vitro-solarban-70
        locator:
          page: "{page}"
          table: "Insulating Glass Unit Performance Comparisons"
          row: "{row}"
  links:
    - predicate: realizesDesign
      target: envelope.openings.window.igu
    - predicate: madeOf
      target: "{cavity_material}"
      qualifiers: { role: gas-fill }
  columns:
    u_winter:
      property: uFactor
      unit: "Btu/(h·ft²·°F)"
      scope: center-of-glass
      conditions: "NFRC winter nighttime"
      locatorColumn: "{u_col}"
    shgc:
      property: solarHeatGainCoefficient
      unit: "1"
      locatorColumn: "SHGC"
    vlt:
      property: visibleLightTransmittance
      unit: "1"
      locatorColumn: "Visible Light Transmittance"
```

- **Expansion rules:**
  - Automatically emits `isVariantOf` → parent `productModel` for every row.
  - Interpolates `{col}` placeholders in `idTemplate`, `labelTemplate`, `links[*].target`, and `locator` fields (converting `locator.page` to `int`).
  - Blank CSV cell → skip statement.
  - Literal `"unknown"` or `"withheld"` → emit `state` statement.
  - Numeric cell → parse as `float` and emit `quantity` statement (non-numeric cell raises `CompileError` with `file:row:col`).
  - Records `Provenance(file=csv_path, row=row_num)` on every emitted node and statement.

### 5. EN 15804 EPD / GWP Conventions, First-Class Temporal/Geo Fields & SI Unit Normalization (`model.py` + `compiler.py` + `validator.py` + `graph.schema.json`)

- **First-class EPD/temporal/geographic fields (`graph.schema.json` + `validator.py`):**
  - On `#/$defs/source`: optional `validUntil` (`string`, `format: date`).
  - On `#/$defs/statement`: optional `geography` (ISO 3166 country/region code or standard region string, e.g. `"US"`, `"US-TX"`, `"EU"`), `pcr` (Product Category Rule identifier), `validUntil` (`string`, `format: date`), and `plantActor` (ID referencing an `actor` node; `validator.py` verifies it exists and has `kind == "actor"`).
- **EPD/GWP rules (`validator.py`):** For any statement whose `property` is in `EPD_PROPERTIES = {"gwp", "gwpFossil", "gwpBiogenic", "gwpLuluc", "embodiedCarbon"}`:
  - `scope` is **required** and must match a valid EN 15804 lifecycle module expression (`A1`, `A2`, `A3`, `A1-A3`, `A4`, `A5`, `A1-A5`, `B1`–`B7`, `C1`–`C4`, `C1-C4`, `D`, or `+`-joined combinations like `A1-A3+C1-C4+D`).
  - If `quantity` is present (i.e. not `state: unknown|withheld`):
    - `quantity.unit` must contain `CO2e` (e.g. `kg CO2e`, `kg CO2e/m2`).
    - `quantity.basis` is **required** (declared unit / reference flow, e.g. `per m2 (6mm coated glass)` or `per window unit`).
  - Add `gwp` entry to `data/guides/properties.yaml`.
- **Generic median/range benchmarks:** Concrete `productModel`/`productVariant` nodes carry primary performance/EPD benchmarks (`measured`, `simulated`, `manufacturer-declared`); generic `referenceDesign`/`material` nodes may optionally carry `basis: typical-reference` median or min/max range benchmarks (kept strictly separated by `basis`).
- **Compile-time SI unit normalization (`model.py` + `compiler.py`):**
  - Keep verbatim source `quantity` untouched on every statement (so `audit` verifies exact numbers against archived PDFs).
  - Add a deterministic conversion table in `model.py` mapping common architectural/AEC units to canonical SI units (`Btu/(h·ft²·°F)` → `W/(m²·K)` × `5.678263`, `psf` → `Pa` × `47.880259`, `in` → `m` × `0.0254`, `mm` → `m` × `0.001`, `ft` → `m` × `0.3048`, `lb/ft³` → `kg/m³` × `16.018463`, `cfm/ft²` → `L/(s·m²)` × `5.08`, plus pass-through for already-SI and dimensionless `"1"`/`"%"` units).
  - `compiler.py` computes `siQuantity` (`{value, unit}` or `{min, max, unit}`) for every convertible numeric statement (attached in `CompiledBundle` for SQLite storage in Slice 03; `None` if unit is unmapped).

### 6. Real Product-Line Proof (`data/products/vitro-solarban-70.{yaml,csv}`)
- Author `data/products/vitro-solarban-70.yaml` (`product.vitro.solarban-70`) + `data/products/vitro-solarban-70-igus.csv` backed by the real archived `.materials/blobs/2eb6adbb1870afdb6b5d2da57a71f9f92b4c6d0af406e8b3c649692f99759dde.pdf`.
- Read actual rows from page 2 (`Insulating Glass Unit Performance Comparisons`) of the archived PDF before writing the CSV—include at least 4 real SKU variants (e.g. Clear + Clear Air, Clear + Clear Argon, Solargray + Clear Air, Solargray + Clear Argon) with real U-factor, SHGC, and VLT values plus a model-level `gwp` (`scope: A1-A3`, `state: unknown` if not in the datasheet, or measured if from an archived EPD) to prove inheritance and EPD conventions.

---

## Playable Checkpoint & Verification

1. Run `python -m building_materials validate` → exits `0`, reporting expanded `productVariant` count (≥ 4 Vitro SKUs) and all 6 taxonomy divisions.
2. Verify negative contracts via CLI on a temporary YAML file:
   - Invalid EPD scope (e.g. `property: gwp`, `scope: whole-window`) → `validate` exits `1` with clear diagnostic.
   - `gwp` quantity without `quantity.basis` → `validate` exits `1`.
   - Non-numeric cell in a numeric CSV column → `validate` exits `1` reporting exact `file:row:col`.
   - `productVariant` with two `isVariantOf` links → `validate` exits `1`.

---

## Delegated Decisions

The implementer may choose:
- Exact set of ≥ 4 Vitro Solarban 70 glass configurations from page 2 of the archived PDF.
- Whether `variantsTable` is embedded on the `productModel` entity or also supported as a standalone file referencing `model: <id>` (embedded on `productModel` is required; standalone is optional).
- Exact wording of `gwp` property guide prose in `data/guides/properties.yaml`.

## What Must Stay Green

- Slice 01 `validate` and `import-source` behavior remains intact.
- Every expanded CSV row cites exact page/table/row/column locators verified against the real archived Vitro PDF.
