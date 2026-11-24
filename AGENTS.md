# Building Materials

Build a source-backed graph that explains what goes into a building—from assemblies down to atomic structure—and how each component is designed, made, and installed.

## Current Scope (Concentric Expansion)

Start at the **window unit and its subcomponents** (`envelope.openings.window`), then expand outward one ring at a time to immediately adjacent envelope and interior systems (**flashing, masonry veneer, sheathing/WRB, framing, drywall**). Keep scope tight and deep around real physical interfaces before branching to distant building systems.

## Modeling Discipline (Pragmatic BFO / IOF 3-Tier Split)

1. **Tiny, domain-agnostic core:** Keep `graph.schema.json`, `schema.sql`, and `building_materials/` free of trade- or product-specific columns. Keep `hasPart` strictly physical element/assembly composition (Uniformat II / IFC). Keep **design specs** (`referenceDesign`, `productModel`, `productVariant`, `requirement`), **matter** (`material`, `chemicalEntity`), **roles/positions** (`qualifiers`), and **processes** (`process`) distinct.
2. **Controlled vocabulary (`data/guides/`):** Never invent ad-hoc property, parameter, or interface names in YAML/CSV. Register every reusable term once in `data/guides/` with its unit, plain-English guide, benchmark bands, and external crosswalks (`ifcPset`, `bsdd`, `openepd`, `etim`).
3. **Guided domain profiles:** Express what a specific system expects (e.g., window vs. masonry vs. drywall) as declarative per-system checklists—not hardcoded schema fields—so authoring stays guided without EAV drift.
4. **Compatibility in three places only:** Material-to-material chemical/physical dispositions live once on `material` (`incompatibleWith`); mating geometry/ports use registered `interface` links; code/climate/occupancy suitability lives in `requirement` profiles.
5. **Reference graph vs. building instances:** Keep universal knowledge (`data/` → SQLite) strictly separate from specific building instances (house, apartment, school, data center).

## Data Integrity & Testing

- **Primary sources only:** Cite archived manufacturer datasheets, NFRC/AHRI directories, openEPD, HPD, ASTM/EN standards, or USGS/NREL data via `import-source --id <issuer.slug>`. Never scrape secondary aggregators or invent numbers.
- **Lookup before minting:** Run `search` before creating `actor`, `material`, or `chemicalEntity` nodes; reuse shared IDs and attach unique external IDs (`cas`, `nfrc`, `openepd`, `gtin`).
- **Minimal tests:** Keep tests minimal. Test end-to-end paths only (`tests/test_e2e.py`).
