# Building materials graph schema

## Purpose

Describe what goes into a building and how it gets there. A learner can start at a house, follow its window down through the glazing unit, glass, and atomic structure, then trace the same window back through research, design, specification, fabrication, procurement, and installation. The graph should also answer why a material, process, or configuration changes a property.

Use one graph for two traversals. Composition follows links such as `hasPart`, `madeOf`, and `hasStructure`. The value chain follows activities that use, produce, evaluate, move, or install those same records. A glazing unit can be a part of a window and the output of a fabrication activity. Both paths point to the same glazing unit ID.

The first slice is one window. The fixture is plain JSON, checked by JSON Schema and graph validation. The Python CLI is the entry point for exploring it.

## Run v1

From the project directory, use Python 3.11 or later. Install the validator once with `python -m pip install -r requirements.txt`.

```text
python -m building_materials validate
python -m building_materials parts opening-w01
python -m building_materials trace window-w01
python -m building_materials facts igu-gray-reference
python -m building_materials cite igu-gray-shgc
python -m unittest discover -s tests -v
```

The commands default to `fixtures/window.json`. Pass `--graph` or `--assets` before the command to use a different graph or archive. Use `python -m building_materials import-source <url>` to fetch and archive a source. For a file already on disk, use `python -m building_materials import-source <path> --url <source-url>`. Every imported file keeps its original HTTP(S) URL. The command returns a source ID to cite. Local captures live under `.materials/`. When a capture is absent, citations can still use the source URL and locator.

## Record types

| Record | Meaning | Minimum fields or links beyond ID and label |
| --- | --- | --- |
| Reference design | A reusable building system, assembly, component, or configuration. It can have multiple revisions. | Kind, revision, part relationships, relevant requirements. |
| Product model | A manufacturer's catalog identity, such as a window family or coated glass. | Manufacturer, model identifier, applicable variants. |
| Product variant | An orderable or documented configuration of a product model. | Product model, variant identifier or distinguishing options, applicable revision and market when known. Link to the design it realizes when documented. |
| Physical item | A real building, opening, assembly, part, or material batch. | Kind, available project, lot, or serial identifiers, links to the applicable design or product variant. |
| Material | A material family or identified formulation, such as soda-lime silicate glass or a named grade. | Family or formulation status, composition and structure claims where supported. A formulation can be a more specific member of a family. |
| Structure model | A description of how matter is arranged at a stated scale. | Scale, structural motif or phase, scope, and evidence. It may describe pores, grains, polymer chains, a crystal lattice, or a local atomic network. |
| Chemical entity | A substance, element, molecule, ion, or other chemical entity used in a composition or structure statement. | Entity kind and external identifier where available. |
| Process definition | A known way to make, test, move, or install something. | Process kind, input and output roles, and any documented conditions. |
| Activity | A particular execution of a process, test, or project step. | Stage from the values below, time and location when known, responsible actor where known, relevant inputs or outputs, and supporting evidence. It can reference a process definition. |
| Requirement | A property limit, prescribed product or detail, or other constraint on a design or opening. | Subject, criterion, value or reference, applicable scope, and versioned specification source. |
| Decision | A documented selection, approval, substitution, or rejection. | Subject or opening, selected option or outcome, decision maker and date when known, governing requirements, and evidence. |
| Actor | A party in the chain, such as a glass producer, lab, designer, fabricator, or installer. | Name and known identifiers. The actor's role belongs to its relationship with an activity or decision. |
| Source | A specific document revision or web capture used as evidence. | Issuer, source type, title, source URL, capture date, and issue date or revision when known. Include the stored asset reference and content hash when captured. |

Give every record a stable local ID. Model, SKU, lot, serial, IFC, and chemistry identifiers live alongside it with their issuer or namespace. Use version-specific references when a changed datasheet, design, or specification could change the interpretation. The same label can refer to different things, and matching it alone cannot establish identity. A reference design describes how a window is built. A product model identifies a manufacturer's offering. A variant identifies its particular configuration. A physical item identifies a specific unit or batch.

## Relationships

| Relationship | Allowed endpoints and meaning | Relevant qualifiers |
| --- | --- | --- |
| `hasPart` | Reference design → reference design, or physical item → physical item. A design edge states intent and an item edge describes physical composition. | Role, quantity, sequence or position. Use separate edges for inside and outside panes even when the same pane type fills both roles. |
| `realizesDesign` / `isVariantOf` / `isInstanceOf` | Product variant → reference design, variant → product model, physical item → variant or reference design. | Applicable revision. The physical item's realized identity requires its own evidence. |
| `fillsOpening` | Physical window → physical opening. | Evidence linking the installation activity to the unit and opening, with the effective date when known. Replacements preserve the earlier installation history. |
| `madeOf` | Design or physical item → material. | Role, layer or surface, and quantities such as thickness or fraction. Each recorded quantity includes its unit. |
| `hasComposition` / `hasStructure` | Material → chemical entity, constituent material, or structure model, as appropriate. | Composition basis, amount or range, and the scope of the formulation or structural model. |
| `uses` / `produces` | Activity → input or output. Inputs and outputs can be physical items, data, or documents. Fabrication can create or transform an item. Packing and shipping refer to the same item as it moves. | Role, quantity and unit, and lot or identifier where known. Use explicit roles to distinguish material feedstocks, process media, design inputs, samples, and results. |
| `performedBy` | Activity or decision → actor. | Role on this activity or decision. |
| `appliesTo` / `evaluates` / `selects` | Requirement → design or opening. Decision → requirement or candidate. Decision → selected configuration. | Revision and stated rationale where the source provides it. |
| `supersedes` | A later revision or decision → the earlier record it replaces. | Effective date and reason where documented. |

Properties and sourced relationships are **claims**. Each claim has a subject, a defined property or relationship, a target or literal value, and evidence. Every structured quantity includes a value or range and an explicit unit, including counts and dimensionless quantities. Record the basis where it changes meaning, such as mass percent versus mole percent. Keep an unlabelled number in its source evidence until its unit is established. Store the measured or reported scope and method, such as center-of-glass versus whole-window U-factor, a specific test standard, or an EPD indicator and life-cycle module. Attach evidence as a source ID and a locator within that source. Record a basis such as measured, simulated, manufacturer-declared, project-recorded, typical reference, inferred, or illustrative. A derived claim links to its input claims and calculation or inference.

## Source collection

Start with a manual import of a URL or file. Register a source once and reuse it across claims. Keep the original PDF, image, or web capture in an asset folder and give the graph a reference to it. If only a link is available, record that status so it is clear which evidence can be reopened from a saved copy.

- For a local capture, retain the original HTTP(S) URL, media type, capture date, and SHA-256 of the stored bytes. Reuse the stored bytes when two imports have the same hash. If the document changes at the same URL, register a new source version. Existing citations keep their original version.
- A PDF citation records the one-based PDF page and a section, table, row, or figure when needed. A web citation records the best available page anchor or heading and a short identifying quote or table row when needed. The locator belongs to the citation, since multiple claims can cite different places in the same source.
- Extracted text or OCR can help find evidence. A normalized claim still carries the source, exact location, subject, and unit. Keep source snapshots and extracted text outside the graph's records.

For the window fixture, Vitro reports a simulated center-of-glass solar heat gain coefficient of **0.19** for the 1-inch Solarban 70 Solargray + Clear glazing configuration. The evidence points to PDF page 2, the insulating glass performance table, the Solargray + Clear row, and the SHGC column. Store the quantity as dimensionless and associate it with that glazing configuration. [Vitro product datasheet](https://vitroglazings.com/media/0wapqqqk/pds_solarban_70.pdf) · [W3C web citation selectors](https://www.w3.org/TR/annotation-model/#selectors)

## Value-chain stages

Use a short set of stage values on activities. Activities can repeat and branch. Trace their inputs, outputs, and affected items to discover the order.

| Stage values | Meaning |
| --- | --- |
| `research`, `testing` | Research develops a material, process, or prototype. Testing generates evidence for a specific sample or configuration. |
| `design`, `specification`, `approval` | Design creates or revises a configuration. Specification states project requirements. Approval records a review outcome for a proposed configuration. |
| `ordering`, `fabrication` | Ordering records the requested variant and quantity. Fabrication turns inputs into or transforms a physical item. |
| `packing`, `shipping`, `receiving` | Packing groups items for transport. Shipping moves them. Receiving records what arrived. These activities preserve the identities of the units being handled. |
| `installation`, `verification` | Installation associates the physical unit with its opening. Verification records what was actually observed there. |

## Invariants

- Physical decomposition must be acyclic. Reusing a design or material across assemblies is expected. Part role, position, and quantity belong to the use relationship.
- A property applies to its claim's subject and configuration. A glazing-unit rating cannot become a frame or whole-window rating through part traversal. A generic glass composition does not establish an exact branded formulation.
- Distinguish batch feedstocks, reported composition, and atomic structure. Silica and soda ash can be inputs to glassmaking, oxide percentages can describe the finished bulk glass, and a structural model can describe the network. Each relation answers a different question.
- Preserve what was specified, approved, ordered, fabricated, delivered, and installed through linked decisions and activities. The product recommendation and the product evidenced in the opening can differ. Missing lot or installation evidence leaves a gap in the trace.
- Preserve competing source claims with their scopes and versions. Treat zero, unknown, and withheld as distinct states. Reference or illustrative data must stay visibly identifiable.

## First fixture and acceptance

Use one reference window with a frame, sash, insulating glass unit, two panes, separate spacer and seal roles, and a gas cavity. Follow the outer pane into its substrate and coating. The generic substrate path reaches a soda-lime silicate glass structure model and its silicon–oxygen network, sodium ions, and calcium ions.

Pair that reference assembly with Vitro's published Solarban 70 glazing data and the University of Alabama's public specification for a gray exterior pane with Solarban 70 on surface #2. The datasheet and owner specification establish separate claims. Use labeled illustrative records for specimen history, fabrication lots, approvals, and the installed opening where project evidence is unavailable. [Vitro glazing data](https://www.vitroglazings.com/media/0wapqqqk/pds_solarban_70.pdf) · [University of Alabama window guidelines](https://constructionpublicinfo.ua.edu/wp-content/uploads/Design-Guidelines/Section-III/Division-08-Openings/08-50-00-Windows.pdf) · [Soda-lime silicate structure](https://www.mdpi.com/2075-5309/16/3/506)

The fixture is sufficient when it can answer these questions:

1. From a window opening, which pane carries the coating and on which surface? Can the reader reach the substrate's material structure?
2. Which glass or gas options were evaluated, which configuration was selected, and which source supports the decision? Which published properties apply to the glazing configuration, and which apply to the whole window?
3. From a window's part list, can the reader select the same glazing unit produced by a fabrication activity and trace its inputs, approval, and installation? Does the trace distinguish delivery from installation and show where evidence is missing or illustrative?
4. If the installed variant differs from the specified one, can the reader recover both identities and the substitution record? Can the same glass model be found wherever it is used?
5. Can the reader tell which upstream claims describe a process generally, and which identify an actual batch or test that contributed to this item?
6. Can the reader reopen a performance claim at the exact table row on the cited revision? Does importing an updated PDF at the same URL preserve the original citation?

## Standards to borrow from

| Concern | Reference |
| --- | --- |
| Building elements, openings, and decomposition | [IFC window types](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcWindowType.htm) · [Building Topology Ontology](https://w3c-lbd-cg.github.io/bot/) |
| Assembly parts and material layers | [Building Product Ontology](https://www.sciencedirect.com/science/article/pii/S0926580521003782) · [Digital Construction Materials](https://digitalconstruction.github.io/Materials/v/0.5/) |
| Materials science and chemistry | [EMMO](https://emmc.eu/emmo/) · [PubChem](https://pubchem.ncbi.nlm.nih.gov/docs/periodic-table-element-pages) |
| Property definitions, units, and environmental declarations | [buildingSMART Data Dictionary](https://technical.buildingsmart.org/services/bsdd/data-structure/) · [QUDT](https://www.qudt.org/) · [openEPD](https://docs.open-epd-forum.org/en/open-epd-format-1/) |
| R&D and process provenance | [PMD Core Ontology](https://github.com/materialdigital/core-ontology) · [W3C PROV-O](https://www.w3.org/TR/prov-o/) |
| Supply chain and construction records | [GS1 EPCIS](https://ref.gs1.org/standards/epcis/) · [IFC process relationships](https://standards.buildingsmart.org/IFC/RELEASE/IFC4_3/HTML/lexical/IfcRelAssignsToProcess.htm) |

These are vocabulary and interchange references. The window fixture will show which external identifiers and mappings the graph needs to carry.
