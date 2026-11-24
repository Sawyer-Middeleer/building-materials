# Slice 04 — Level 2: Complete Window Unit & Live Product Swap

## Objective
Render a detailed, explodable single-hung window unit where the user can swap live between **Winco 4410S (Thermally Broken Aluminum)** and **Andersen 100 Series (Fibrex Composite)** and visually see *why* their thermal and structural profiles differ.

## Scope & Seam
- **`ui/levels/window.js`:**
  - Procedural single-hung window assembly with corner cutaway reveal so the cross-section of the frame extrusion is visible:
    - **Mode A — Winco 4410S (`winco-4410s-single-hung`):**
      - `winco-4410s-frame`: 4-inch deep brushed 6063-T6 extruded aluminum outer & inner channels, visibly separated by a poured amber/charcoal **`polyurethane-thermal-break`** core (`userData.nodeId = "polyurethane-thermal-break"`).
      - `winco-4410s-sash`: 1-5/8" hollow-tube extruded aluminum lower operable sash + fixed upper glazing pocket.
      - `igu-gray-argon`: clickable dual-pane IGU (`userData.drillLevel = "igu"`).
    - **Mode B — Andersen 100 Series (`andersen-100-single-hung`):**
      - `andersen-100-frame` & `andersen-100-sash`: matte dark-bronze/charcoal **`fibrex-composite`** extruded hollow multi-chamber profiles (no metal thermal break channel needed!).
      - `igu-gray-argon`: clickable dual-pane SmartSun + Argon IGU (`userData.drillLevel = "igu"`).
  - **Product Switcher Pill** in the canvas subbar: `Winco 4410S (Aluminum)` | `Andersen 100 (Fibrex)`.
    - Switching swaps the 3D frame/sash geometry & PBR materials live, updates the Inspector to the selected window variant (`U = 0.50` / `AW-65` vs `U = 0.25` / `LC-PG30`), and keeps the current camera angle and explode state intact.
  - **Explode behavior (0–100%):** Separates exterior frame half, thermal break core (Winco), interior frame half, operable sash, and IGU along the Z-axis with crisp CAD edges and leader callouts.

## Playable Checkpoint
In Level 2, toggling between Winco 4410S and Andersen 100 visibly transforms the 3D window from brushed aluminum + structural urethane thermal break to matte Fibrex composite, while the right Inspector updates the NFRC U-factor (`0.50` vs `0.25`), Design Pressure (`97.5 psf` vs `30 psf`), and manufacturer firm links (`winco` vs `andersen`). Clicking the IGU drills into Level 3.

## Verification Gates
- `screenshot-critique` + `compare-screenshots` comparing Winco 4410S (exploded) vs. Andersen 100 (exploded): verify the thermal break is unmistakably legible on Winco, material contrast (metallic aluminum vs. matte Fibrex) reads clearly, and zero z-fighting occurs at frame corners.
