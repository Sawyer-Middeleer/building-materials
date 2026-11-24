# Deep Windows (Ring 0 — First Pass)

## Next Agent Prompt

You are implementing **Deep Windows (Ring 0 — First Pass)** under `specs/deep-windows-ring-0/`.

- **Status:** All 4 slices complete, independently reviewed, and verified (last updated 2026-11-24).
- **Next pickup point:** Ready for user review or expanding to Ring 1 (sill flashing, masonry veneer, sheathing/WRB, drywall) and a generalized `project.yaml` evaluator.
- **Active warnings / constraints:**
  - **Follow `AGENTS.md` and `domain-modeling-discipline`:** Zero window-specific columns in `graph.schema.json`, `schema.sql`, or `building_materials/`. Every property, parameter, and interface must be registered in `data/guides/`.
  - **Minimal tests (`AGENTS.md`):** Keep tests minimal—test end-to-end paths only (`tests/test_e2e.py`).
- **Global TODO Checklist:**
  - [x] [Slice 01](slices/01-generalized-3-tier-primitives.md): Add domain-agnostic `parameters`, `compatibleWith`/`incompatibleWith`, `qualifiers.interface`, `expectedProfile`, and `propertyGuides.bands` to schemas, compiler, validator, SQLite store, and API.
  - [x] [Slice 02](slices/02-window-anatomy-guides-and-requirements.md): Deepen `envelope.openings.window` (material-neutral shared slots, full subcomponents), register controlled vocabularies & homeowner benchmark bands, add IECC climate `requirement` profiles and material `incompatibleWith` dispositions.
  - [x] [Slice 03](slices/03-multi-archetype-window-catalog.md): Populate Winco 4410S (thermally broken aluminum) and Andersen 100 Series (Fibrex composite) with CSV SKU matrices, `parameters` (sizes, colors, operation types), chemistry, value chains, and compatibility.
  - [x] [Slice 04](slices/04-decision-compare-and-medians.md): Enrich `compare` + `/api/compare` with plain-English `bands`, live SQLite catalog medians, `parameters` diff, and `--profile` requirement/compatibility checks; extend `tests/test_e2e.py`.
- **Handoff rule:** Update this **Next Agent Prompt** section before ending your pass.

---

## Goal

Make **Ring 0 (`envelope.openings.window`)** deeply explorable by a curious homeowner, designer, or AI agent—answering every question from **specs, sizing, colors/customizations, efficiency/quality metrics in plain English, material compatibility, ballpark cost/lifespan, value chain, and chemistry**—using **100% domain-agnostic BFO/IOF 3-tier primitives** that will immediately reuse on Ring 1 (flashing, masonry, sheathing, drywall) and beyond.

---

## Non-Goals (Deferred to Next Spec)

- No Ring 1 wall assemblies (masonry veneer, drywall, wood framing) yet—only the boundary interface stubs (`rough-opening`, `drainage-plane`, `interior-finish-return`) and material dispositions (`aluminum` ↛ `portland-cement-mortar`).
- No whole-building `project.yaml` instance or UA heat-loss simulator yet—that becomes the next spec once Ring 0 + Ring 1 are populated.

---

## Slice Ladder

| Slice | Primary Seam | Playable Checkpoint |
| --- | --- | --- |
| [01](slices/01-generalized-3-tier-primitives.md) | `graph.schema.json`, `guide.schema.json`, `schema.sql`, `compiler.py`, `validator.py`, `store.py` | Unregistered parameter/interface names fail `validate`; valid `parameters`, `compatibleWith`/`incompatibleWith`, `expectedProfile`, and `propertyGuides.bands` round-trip through SQLite and `/api/*`. |
| [02](slices/02-window-anatomy-guides-and-requirements.md) | `data/guides/`, `data/systems/envelope/windows/`, `data/requirements/` | `envelope.openings.window` has material-neutral shared slots, `expectedProfile`, homeowner benchmark `bands`, IECC CZ 3/5/7 requirements, and aluminum/mortar incompatibility; `validate` & `audit` exit `0`. |
| [03](slices/03-multi-archetype-window-catalog.md) | `data/products/{winco,andersen}/`, `data/materials/`, `data/actors/` | Winco 4410S (aluminum) + Andersen 100 Series (Fibrex multi-operation × multi-glazing CSV matrix) + generic vinyl/wood-clad cost/lifecycle medians compile and pass `audit` (`0` errors) against archived PDFs. |
| [04](slices/04-decision-compare-and-medians.md) | `store.py`, `cli.py`, `server.py`, `tests/test_e2e.py` | `compare product.winco.4410s.single-hung product.andersen.100.casement-smartsun --profile req.iecc.cz5.fenestration` returns plain-English metric bands, live catalog medians, parameter diffs, compatibility flags, and requirement pass/fail; E2E suite passes. |
