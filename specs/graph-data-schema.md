# Building materials graph schema

## Purpose

Explain what goes into a building—from whole-building systems and assemblies down to atomic structure—and how specific products, materials, and processes fit into that structure and its value chain.

One graph supports two traversals plus comparison:
- **Physical composition** follows `hasPart`, `madeOf`, `hasComposition`, `hasStructure`, `includesChemical`, `realizesDesign`, and `usesConfiguration`.
- **Value chain** follows processes (`uses`, `produces`, `performedBy`) across `extraction`, `research`, `testing`, `design`, `specification`, `fabrication`, `distribution`, and `installation`.
- **Comparison** diffs facts (with verbatim and SI-normalized quantities), materials, parts, and processes across competing products or variants.

## Authoring vs. Runtime Architecture

- **Authoring source of truth (`data/`):** Modular entity-centric YAML files organized by domain subfolder (`systems/`, `products/`, `materials/`, `chemistry/`, `actors/`, `sources/`, `guides/`), plus tabular CSV SKU matrices (`variantsTable`) and `productModel` → `productVariant` inheritance (`variantDefaults`).
- **Compiled IR:** `building_materials/compiler.py` lowers `data/` into canonical `nodes + statements + guide` validated against [graph.schema.json](../graph.schema.json) and [guide.schema.json](../guide.schema.json).
- **Primary runtime store:** Lossless SQLite v2 + FTS5 database ([schema.sql](../schema.sql)) at `.materials/materials.db`, rebuilt atomically whenever `data/` changes and queried by both the CLI and headless JSON HTTP API (`serve`).

## Multi-Axis Taxonomy & Standards Reconciliation

- **Primary `hasPart` spine (Uniformat II / IFC):** `building` → `substructure`, `superstructure`, `envelope`, `interiors`, `mep`, `siteworks` → assemblies → subcomponents.
- **Cross-standard `identifiers`:** Any node can carry classification and registry codes across `uniformat2`, `omniclass`, `uniclass`, `masterformat`, `nrm1`, `icms`, `ifc`, `bsdd`, `etim`, `gtin`, `nfrc`, `astm`, `openepd`, `epd`, `hpd`, and `cas`.
- **Property & unit crosswalks:** Canonical internal property keys live in `data/guides/properties.yaml` with optional `ucumUnit` and `externalRefs` (`ifcPset`, `bsdd`, `openepd`, `etim`). Numeric statements preserve verbatim source `quantity` for PDF `audit` and auto-compute `siQuantity` for cross-unit comparison.
- **EPD & temporal/geographic claims:** Statements support first-class `geography`, `pcr`, `validUntil`, and `plantActor` (plus `validUntil` on `source`). Embodied-carbon properties (`gwp`, `gwpFossil`, `gwpBiogenic`, `gwpLuluc`, `embodiedCarbon`) require a valid EN 15804 `scope` (e.g. `A1-A3`) and, when quantified, a `CO2e` unit plus declared-unit `quantity.basis`.

## Record types

| Record | Meaning | Key fields beyond ID and label |
| --- | --- | --- |
| `referenceDesign` | Reusable building system, assembly, component, or taxonomy division. | Revision, part relationships, classification identifiers. |
| `productModel` | Manufacturer's catalog product line. | Manufacturer (`manufacturedBy`), `variantDefaults`, `variantsTable`. |
| `productVariant` | Specific documented SKU or configuration of a product model. | `isVariantOf`, `realizesDesign`, variant-specific materials/parts, performance/EPD claims. |
| `material` | Material family, feedstock, or named formulation. | Composition (`hasComposition`), structure (`hasStructure`), optional `typical-reference` medians. |
| `structureModel` | Arrangement of matter at a stated scale (atomic network, crystal lattice, grains). | `scale`, constituent `chemicalEntity` links. |
| `chemicalEntity` | Element, ion, molecule, oxide, or polymer. | External identifiers such as `cas` RN. |
| `process` | Value-chain step across 8 stages (`extraction` through `installation`). | `stage`, `uses`, `produces`, `performedBy`. |
| `requirement` | Property limit or design constraint from a specification or standard. | Target (`appliesTo`) and cited specification source. |
| `actor` | Manufacturer, plant, testing lab, standard body, or trade role. | Name, identifiers, guide metadata. |
| `source` | Specific document revision or web capture used as evidence. | Origin HTTP(S) URL, media type, issuer, `validUntil`, SHA-256. |

## Invariants

- Node IDs use lowercase dotted namespaces (`^[a-z0-9]+([.-][a-z0-9]+)*$`).
- Composition (`hasPart`) and claim derivations (`derivedFrom`) must be acyclic.
- A `productVariant` may belong to at most one `productModel` via `isVariantOf`.
- Properties apply strictly to their subject and `scope` (center-of-glass never leaks onto whole-window).
- Distinguish zero, `unknown`, and `withheld` states; preserve competing claims with scopes, geography, and validity dates.
- Sources are immutable: `import-source --id <slug>` refuses to overwrite an existing slug with different bytes or origin.
- Completeness is evaluated by tier (`gaps --tier catalog|assembly|atomic`).
