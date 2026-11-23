# Building materials graph schema

## Purpose

Explain what goes into a building—from assemblies down to atomic structure—and how specific products, materials, and processes fit into that structure and its value chain. A reader can start at a window assembly, follow its glazing unit down through glass and atomic structure, trace the processes that make and install it, and compare alternative products or configurations (such as air-filled vs. argon-filled glazing, or slate vs. clay tile vs. concrete tile roofs) side by side.

Use one graph for two traversals plus comparison. Composition follows links such as `hasPart`, `madeOf`, `hasComposition`, `hasStructure`, and `includesChemical`. The value chain follows processes that use, transform, test, specify, distribute, or install those same records. Specific products and variants realize reference designs so alternatives can be compared on material composition, properties, and supply chain.

The first slice is a window. The fixture is plain JSON, checked by JSON Schema and graph validation. The Python CLI and local web UI are the entry points for exploring it.

## Run v1

From the project directory, use Python 3.11 or later. Install the validator once with `python -m pip install -r requirements.txt`.

```text
python -m building_materials validate
python -m building_materials parts window-assembly
python -m building_materials trace igu-gray-argon
python -m building_materials used-by vitro-solarban-70
python -m building_materials compare igu-gray-air igu-gray-argon
python -m building_materials facts igu-gray-reference
python -m building_materials cite igu-gray-shgc
python -m building_materials serve --open
python -m unittest discover -s tests -v
```

The commands default to `fixtures/window.json`. Pass `--graph` or `--assets` before the command to use a different graph or archive. Use `python -m building_materials import-source <url>` to fetch and archive a source. For a file already on disk, use `python -m building_materials import-source <path> --url <source-url>`. Every imported file keeps its original HTTP(S) URL. Local captures live under `.materials/`. When a capture is absent, citations still resolve using the source URL and locator.

## Record types

| Record | Meaning | Key fields beyond ID and label |
| --- | --- | --- |
| `referenceDesign` | A reusable building system, assembly, component, or structural slot. | Revision, part relationships, governing requirements. |
| `productModel` | A manufacturer's catalog identity, such as coated glass or a window/roofing line. | Manufacturer (`manufacturedBy`), applicable designs and variants. |
| `productVariant` | A specific documented configuration of a product model (e.g., air vs. argon fill). | Product model (`isVariantOf`), realized design (`realizesDesign`), specific materials/parts, and performance claims. |
| `material` | A material family, feedstock, or named formulation (e.g., soda-lime silicate glass, argon, silica sand). | Composition and structure claims where supported. |
| `structureModel` | A description of how matter is arranged at a stated scale (e.g., atomic network, crystal lattice, grains). | `scale`, structural motif, constituent chemicals. |
| `chemicalEntity` | An element, ion, molecule, or oxide used in a composition or structure statement. | External identifiers where available. |
| `process` | A value-chain step that extracts, researches, tests, designs, specifies, fabricates, distributes, or installs a material or component. | `stage`, inputs (`uses`), outputs (`produces`), responsible actor (`performedBy`). |
| `requirement` | A property limit, prescribed product, or design constraint from a published specification or standard. | Target design/product (`appliesTo`) and versioned specification source. |
| `actor` | A manufacturer, testing lab, standard body, or trade role in the value chain. | Name and known identifiers. |
| `source` | A specific document revision or web capture used as evidence. | Origin HTTP(S) URL, media type, issuer, capture date, and SHA-256 when archived. |

## Relationships

| Relationship | Allowed endpoints and meaning | Relevant qualifiers |
| --- | --- | --- |
| `hasPart` | Reference design or product variant → reference design or product variant. | Role, quantity, sequence or position. Use separate edges for inside and outside panes. |
| `realizesDesign` / `isVariantOf` | Product model or variant → reference design; product variant → product model. | Role or revision where documented. |
| `usesConfiguration` / `usesProduct` | Reference design or product variant → sub-configuration or product model. | Role or position where documented. |
| `manufacturedBy` | Product model → actor. | — |
| `madeOf` | Reference design or product variant → material. | Role, layer or surface (`position`), and quantities with units. |
| `hasComposition` / `hasStructure` / `includesChemical` | Material → constituent material, chemical entity, or structure model; structure model → chemical entity. | Role, composition basis, amount or range. |
| `uses` / `produces` | Process → input or output (materials, feedstocks, designs, products, documents). | Explicit `role` distinguishing feedstocks, substrates, coatings, specifications, and outputs. |
| `performedBy` | Process → actor. | Role on the process. |
| `appliesTo` | Requirement → reference design, product model, or product variant. | Revision or scope where documented. |
| `supersedes` | A later revision → the earlier record it replaces. | — |

Properties and sourced relationships are **claims**. Every claim carries a subject, a `basis` (`measured`, `simulated`, `manufacturer-declared`, `specification`, `typical-reference`, or `inferred`), and at least one source citation with a locator. Every numeric quantity requires an explicit unit (`"1"` for dimensionless quantities). Store `scope`, `method`, and `conditions` where they change interpretation (e.g., center-of-glass vs. whole-window U-factor).

## Value-chain stages

| Stage | Meaning |
| --- | --- |
| `extraction` | Mining, quarrying, or harvesting raw feedstocks (e.g., silica sand, clay, slate). |
| `research`, `testing` | Developing materials/coatings and running physical tests or thermal simulations. |
| `design`, `specification` | Designing assemblies and setting governing architectural/performance requirements. |
| `fabrication` | Forming, coating, firing, cutting, and assembling materials into products and units. |
| `distribution` | Packaging, transporting, and supplying products to site. |
| `installation` | Placing, sealing, and integrating the product into the building structure. |

## Invariants

- Composition (`hasPart`) and claim derivations (`derivedFrom`) must be acyclic.
- A property applies strictly to its claim's subject and scope. A center-of-glass glazing rating never leaks onto a whole-window assembly.
- Distinguish raw feedstocks (silica sand, soda ash, limestone), bulk oxide composition (`SiO₂`, `Na₂O`, `CaO`), and atomic structure (`Si`, `O`, `Na⁺`, `Ca²⁺` network).
- Preserve competing source claims with their scopes and versions. Treat zero, `unknown`, and `withheld` as distinct states.
- Importing a changed document at the same URL registers a new source version so existing citations keep resolving to their original archived bytes.
