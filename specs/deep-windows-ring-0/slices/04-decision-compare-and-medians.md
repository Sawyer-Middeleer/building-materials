# Slice 04 — Agent-Ready Decision Compare, Live Medians & Minimal E2E Proof

## Contract Unlocked

Both the CLI (`compare`, `explain`) and headless JSON API (`/api/compare`, `/api/explain/<key>`) return **decision-grade, homeowner-readable context**—mapping every numeric metric into its plain-English `band`, computing live **SQLite catalog medians** across competing variants, diffing `productModel` option `parameters`, and checking material `incompatibleWith` hazards + optional `--profile <requirement_id>` pass/fail—ready to hand straight to an AI agent.

---

## API Seams & Ownership

### 1. Live Catalog Medians & Band Classification (`store.py`)
- Add `catalog_stats(design_id: str, property_name: str, scope: str | None = None) -> dict | None`:
  - Queries SQLite `statements.si_value` across all `productVariant`s realizing `design_id` for `(property, scope)`.
  - Returns `{"count": N, "unit": si_unit, "min": ..., "median": ..., "max": ...}` when `count >= 2` (exact median computed in Python over sorted `si_value` rows).
- Add `classify_band(property_name: str, value: float) -> dict | None`:
  - Matches a value against `property_guides.bands_json` (`min` inclusive, `max` exclusive) and returns `{"label": ..., "meaning": ...}`.
- Enrich `store.compare(left_id, right_id, *, profile_id: str | None = None)`:
  - On each fact row: attach `leftBand`, `rightBand`, and `catalogStats` (live median across peers realizing the same `referenceDesign`).
  - Add `"parameters"` section diffing the parent `productModel` option spaces (`left`, `right`).
  - Add `"compatibility"` section listing each side's `compatibleWith` interfaces and any `incompatibleWith` material dispositions reachable from its `madeOf` materials.
  - When `profile_id` (a `requirement` node ID, e.g. `req.iecc.cz5.fenestration`) is provided: evaluate numeric limit properties on that requirement against `left` and `right` (using `siQuantity` for cross-unit safety) and return `"profileCheck": {"profile": ..., "left": [...], "right": [...]}`.

### 2. CLI & HTTP API Wiring (`cli.py`, `server.py`)
- `python -m building_materials compare <left> <right> [--profile <req_id>]`
- `GET /api/compare?left=<id>&right=<id>&profile=<req_id>`

### 3. Minimal E2E Verification (`tests/test_e2e.py`)
- Extend `test_real_corpus_build_audit_and_cli_queries` and `test_headless_json_http_api` (keeping the minimal 3-test E2E suite structure) to verify:
  - Winco 4410S vs. Andersen 100 Series `compare --profile req.iecc.cz5.fenestration` returns `leftBand`/`rightBand`, live `catalogStats.median`, `parameters` diff, `compatibility` (including aluminum ↛ mortar disposition on Winco), and `profileCheck` results via both CLI and HTTP API.
  - Unregistered parameter/interface rejection in `test_authoring_roundtrip_and_negative_contracts`.

---

## Playable Checkpoint & Verification

1. Run:
   ```text
   python -m building_materials compare product.winco.4410s.single-hung product.andersen.100.single-hung-smartsun --profile req.iecc.cz5.fenestration
   ```
   Confirm output gives a non-pro (or AI agent) a complete, source-cited decision packet: metric values + SI values + plain-English bands + live catalog median + size/color option spaces + material chemistry + aluminum-mortar incompatibility warning + IECC CZ 5 pass/fail.
2. `python -m building_materials audit` exits `0` (`errors: 0`).
3. `python -m unittest discover -s tests -v` passes all E2E tests.
