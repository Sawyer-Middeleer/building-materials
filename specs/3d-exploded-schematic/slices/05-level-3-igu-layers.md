# Slice 05 — Level 3: 6-Layer Insulating Glass Unit (IGU) Cutaway

## Objective
Render an explodable corner cutaway of the 1-inch **Insulating Glass Unit (IGU)** showing every physical layer from exterior Solargray glass to the nanometer low-e coating, perimeter spacer, dual sealant, gas cavity, and interior clear glass.

## Scope & Seam
- **`ui/levels/igu.js`:**
  - Procedural 6-layer IGU corner specimen (~350mm × 350mm × 25mm true-to-proportion 1-inch unit: two 6mm lites + 13mm cavity):
    1. **`outer-pane`** (`glassSolargray` tinted refractive PBR, `userData.drillLevel = "atomic"`): 1/4-inch Solargray float glass.
    2. **`low-e-coating`** (ultra-thin iridescent metallic-teal translucent sheet directly on **surface #2**, facing the cavity): visually teaches which glass face carries the triple-silver coating and why it faces inward.
    3. **`edge-spacer`** (`aluminumAnodized` hollow U-channel perimeter bar with tiny perforated desiccant slots along its inner face).
    4. **`edge-seal`** (two distinct visible perimeter beads: thin matte-black **`polyisobutylene`** primary seal sandwiched between spacer and glass, backed by structural charcoal **`silicone-sealant`** secondary seal around the outer edge).
    5. **`argon-cavity` / `air-cavity`** (subtle volumetric translucent gas slab with gentle floating particles; toggleable via a `Dry Air (U 0.28)` | `Argon (U 0.24)` pill in the subbar that swaps the cavity node ID and updates `igu-gray-air` vs. `igu-gray-argon` facts).
    6. **`inner-pane`** (`glassClear` clear refractive PBR, `userData.drillLevel = "atomic"`): 1/4-inch clear float glass.
  - **Explode behavior (0–100%):** Smoothly fans all 6 layers apart along the Z-axis (plus pulls the secondary seal outward) so every single layer is individually clickable with zero occlusion, accompanied by clean leader callouts (`Surface #2 Low-E`, `1/2" Argon Cavity`, `PIB + Silicone Dual Seal`).

## Playable Checkpoint
Drilling into the IGU displays the 6-layer cutaway. Clicking the iridescent film on surface #2 inspects `low-e-coating` (and cites Vitro Solarban 70 p. 1); toggling Air vs. Argon updates the cavity visual and U-factor (`0.28` vs. `0.24`); clicking either glass pane drills into Level 4 (Atomic Silicate Network).

## Verification Gates
- `screenshot-critique` + `compare-screenshots` (assembled vs. exploded): verify surface #2 low-e film is clearly distinguishable from the tinted outer pane, dual PIB/silicone seal layers are readable, and glass transmission looks clean over the warm-paper backdrop.
