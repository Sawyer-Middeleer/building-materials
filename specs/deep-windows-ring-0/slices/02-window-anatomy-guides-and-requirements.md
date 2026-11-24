# Slice 02 — Window Anatomy Deepening, Guides & Climate/Code Requirements

## Contract Unlocked

`envelope.openings.window` becomes a clean, **material-neutral Ring 0 reference assembly** with registered homeowner-friendly vocabularies (`parameters`, `interfaces`, `properties` + benchmark `bands`), reusable IECC climate `requirement` profiles, and material-level `incompatibleWith` dispositions ready for multi-vendor comparison.

---

## Data Deliverables

### 1. Material-Neutral Shared Slots & Complete Window Anatomy (`data/systems/envelope/windows/assembly.yaml`)
- Remove vendor-specific `madeOf: material.aluminum-6063-t6` from the shared `envelope.openings.window.frame` and `envelope.openings.window.sash` slots (so competing aluminum, Fibrex, vinyl, and wood-clad windows can realize `envelope.openings.window` without triggering `shared-slot-contamination`).
- Add core window subcomponents as `referenceDesign` parts under `envelope.openings.window`:
  - `envelope.openings.window.weatherstripping` (air/water compression or fin-seal gasket)
  - `envelope.openings.window.hardware` (balances, locks, hinges/operators)
- Attach `expectedProfile` on `envelope.openings.window`:
  - `properties`: `uFactor`, `solarHeatGainCoefficient`, `visibleLightTransmittance`, `airInfiltration`, `structuralDesignPressure`, `installedCostPerArea`, `serviceLife`
  - `parameters`: `operationType`, `nominalWidth`, `nominalHeight`, `jambDepth`, `finishColor`
  - `interfaces`: `rough-opening`, `drainage-plane`, `interior-finish-return`

### 2. Controlled Vocabularies & Non-Pro Benchmark Bands (`data/guides/`)
- **`data/guides/parameters.yaml`:** Register domain-agnostic configuration axes (`operationType`, `nominalWidth`, `nominalHeight`, `jambDepth`, `thickness`, `finishColor`, `interiorFinish`, `hardwareFinish`, `grilleStyle`, `glazingPackage`).
- **`data/guides/interfaces.yaml`:** Register Ring 0 ↔ Ring 1 boundaries (`rough-opening`, `drainage-plane`, `interior-finish-return`, `glazing-pocket`).
- **`data/guides/properties.yaml`:** Add `structuralDesignPressure`, `condensationResistanceFactor`, `airInfiltration`, `performanceClass`, `installedCostPerArea`, `serviceLife`, `maintenanceLevel` — and populate plain-English `bands` (with `meaning` explaining how it feels/performs for a non-pro) on `uFactor`, `solarHeatGainCoefficient`, `visibleLightTransmittance`, `structuralDesignPressure`, `condensationResistanceFactor`, `airInfiltration`, and `installedCostPerArea`.

### 3. Material Dispositions & IECC Climate Requirements
- **Material incompatibility (authored once on `material`):**
  - `material.aluminum-6063-t6 --incompatibleWith--> material.portland-cement-mortar` (alkaline corrosion in wet mortar contact; requires protective coating or separation membrane) — add minimal `material.portland-cement-mortar` reference material citing archived `ed63e6e3c545...pdf` (SPEC MIX) or `ac647fef344e...pdf` (UA Div 04).
- **Reusable IECC climate-zone `requirement` profiles (`data/requirements/iecc-fenestration.yaml`):**
  - `req.iecc.cz3.fenestration` (cooling-dominant: low SHGC priority, moderate U-factor)
  - `req.iecc.cz5.fenestration` (cold-mixed: U-factor ≤ 0.27–0.30, balanced SHGC)
  - `req.iecc.cz7.fenestration` (very cold: low U-factor priority, higher passive-solar SHGC allowed)
  - Each cites a primary IECC / DOE Building Energy Codes source archived via `import-source`.

---

## Playable Checkpoint & Verification

1. `python -m building_materials validate` and `audit` exit `0` with `0` errors and `0` warnings.
2. `python -m building_materials explain uFactor` returns homeowner-readable `bands` + `ucumUnit` + `externalRefs`.
3. `python -m building_materials explain nominalWidth` and `explain rough-opening` return their registered parameter/interface guides.
4. `python -m building_materials parts envelope.openings.window` walks cleanly through all subcomponents with zero `shared-slot-contamination`.
