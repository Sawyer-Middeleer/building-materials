# Slice 03 — Multi-Archetype Window Catalog (Winco Aluminum vs. Andersen Fibrex + Cost/Lifecycle)

## Contract Unlocked

A homeowner, designer, or agent can explore and compare **two deeply sourced, contrasting window manufacturers** (commercial thermally broken aluminum vs. residential Fibrex wood-fiber/thermoplastic composite) plus **typical-reference residential archetype medians** (vinyl / wood-clad) across performance, sizes, colors, operation types, wall compatibility, cost/lifespan, value chain, and material chemistry.

---

## Primary Sources Used

**Already archived in `.materials/blobs/`:**
- `444ec77febce8f02330253af5fb1ef9072a30c6c859e23388127c7f539c807e0.pdf` — Winco 4410S Performance Data
- `f96b2ee629fd14e691eeb9e2d67d342e375020cccede0003cb51ca318ce7c217.pdf` — Winco 4410S Construction & Fabrication
- `5dce633e14c6f42d315afaa866f8fa28b0bc7a589810e0cc83b973861d985224.pdf` — Andersen 100 Series NFRC Certified Total Unit Performance (5 pages)

**Archive via `import-source --id <issuer.slug>` during implementation:**
- Andersen 100 Series Product/Size & Color Guide PDF (for verified `parameters`: size ranges, colors, jamb depths, hardware finishes).
- Public DOE / NREL National Residential Efficiency Measures Database (REMDB) or ENERGY STAR window cost/lifespan reference (for `basis: typical-reference` `installedCostPerArea` and `serviceLife` benchmarks).

---

## Data Deliverables

1. **Materials & Chemistry (`data/materials/polymers/` & `data/chemistry/polymers.yaml`):**
   - `material.polyurethane-thermal-break` (poured-and-debridged structural polyurethane) + polymer chemistry
   - `material.fibrex-composite` (reclaimed wood fiber + thermoplastic polymer composite; proprietary additive package explicitly noted) + `chem.cellulose` & `chem.pvc`
   - `material.upvc-frame` (generic rigid uPVC vinyl frame material for typical-reference archetype comparison)
2. **Winco 4410S (`data/actors/manufacturers/winco.yaml`, `data/products/winco/4410s.{yaml,csv}`):**
   - `product.winco.4410s` (`productModel`) with `parameters` (frame depth, finishes, operation type), `compatibleWith` (`rough-opening` commercial/masonry strap/receptor), `variantDefaults` (6063-T6 aluminum + polyurethane thermal break), and `4410s-skus.csv` (verified U-factor, CRF, DP, Air Infiltration, AAMA class from archived PDF).
   - Fabrication processes (`thermal-break-pouring`, `winco-window-assembly`).
3. **Andersen 100 Series (`data/actors/manufacturers/andersen.yaml`, `data/products/andersen/100-series.{yaml,csv}`):**
   - `product.andersen.100-series` (`productModel`) with `parameters` (`operationType`: single-hung/casement/awning/gliding/picture, `nominalWidth`/`nominalHeight` ranges, `finishColor`, `interiorFinish`, `hardwareFinish`, `grilleStyle`), `compatibleWith` (`rough-opening` wood-frame nailing fin), `variantDefaults` (Fibrex frame & sash), and `100-series-skus.csv` expanding ≥ 8 real NFRC rows across operation types × glazing packages (`Low-E4`, `SmartSun`, `PassiveSun`, `HeatLock`) straight from archived `5dce633e14c6...pdf` with `nfrc` unique identifiers!
   - Fabrication processes (`fibrex-compounding`, `composite-extrusion`, `andersen-window-assembly`).
4. **Typical-Reference Cost & Lifespan Benchmarks:**
   - Attach `basis: typical-reference` `installedCostPerArea`, `serviceLife`, and `maintenanceLevel` claims (citing NREL REMDB / primary public benchmark) to window archetypes so homeowners can weigh cost vs. thermal/durability tradeoffs.

---

## Playable Checkpoint & Verification

1. `python -m building_materials validate`, `build`, and `audit` all exit `0` (`errors: 0`, zero unexpected warnings) across all archived PDFs.
2. `python -m building_materials nodes --kind productVariant` lists both Vitro IGU SKUs, Winco 4410S SKUs, and ≥ 8 Andersen 100 Series SKUs across operation types and glazing packages.
3. `python -m building_materials compare product.winco.4410s.single-hung product.andersen.100.single-hung-smartsun` cleanly diffs aluminum + polyurethane thermal break vs. Fibrex composite, whole-window U-factor (`0.50` vs `0.25`), DP, CRF, processes, and materials.
4. `python -m building_materials gaps --tier catalog` reports zero unexpected catalog gaps.
