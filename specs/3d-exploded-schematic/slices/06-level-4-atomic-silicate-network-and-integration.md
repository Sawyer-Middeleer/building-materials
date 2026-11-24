# Slice 06 — Level 4: 3D Atomic Silicate Network & Full Integration

## Objective
Render the 3D disordered **`amorphous-silicate-network`** (`soda-lime-glass`) at the atomic scale, wire breadcrumb navigation across all 4 levels (`Building › Window › IGU › Atomic`), and polish the complete end-to-end learning flow.

## Scope & Seam
- **`ui/levels/atomic.js`:**
  - Procedural deterministic 3D ball-and-stick + translucent tetrahedra model (~40–60 atoms) of a disordered soda-lime silicate network matching Figure 3 of the archived MDPI paper (`flat-glass-structure`, p. 6):
    - **`silicon`** (`Si`, metallic slate spheres at tetrahedron centers, `userData.nodeId = "silicon"`).
    - **`oxygen`** (`O`, crimson-coral spheres at tetrahedron corners — visually distinguishing **bridging oxygens** `Si–O–Si` from **non-bridging oxygens** `Si–O⁻`, `userData.nodeId = "oxygen"`).
    - **`sodium-ion`** (`Na⁺`, warm violet spheres nestled near single non-bridging oxygens, `userData.nodeId = "sodium-ion"`).
    - **`calcium-ion`** (`Ca²⁺`, teal-emerald spheres bridging pairs of non-bridging oxygens, `userData.nodeId = "calcium-ion"`).
    - Subtle translucent `SiO₄` tetrahedral facets (toggleable) + covalent `Si–O` rods vs. dashed ionic `Na⁺/Ca²⁺···O` links.
  - **Explode behavior (0–100%):** Gently expands inter-tetrahedral spacing and lifts modifier ions (`Na⁺`, `Ca²⁺`) outward so the learner can visually separate the covalent `SiO₄` backbone from the ionic network modifiers.
  - Clicking any atom opens its **Chemistry Card** in the Inspector (formula, atomic number, molar mass, and role in glass) plus its exact MDPI Figure 3 citation.
- **Breadcrumb & Integration (`viewer.html` + `ui/studio.js`):**
  - Top-left canvas breadcrumb: `Building › Window › IGU › Atomic` — clicking any ancestor smoothly zooms/transitions back up the stack.
  - Deep-link from **Graph**, **Compare**, **Tables**, or **Gaps** tabs: if a selected node has a 3D representation, show a **`View in 3D`** button in the Inspector that switches to **Schematic**, jumps to the right level, and focuses/highlights that exact mesh.
  - Keep `tests/test_window_graph.py` updated with an end-to-end check that `/ui/levels/building.js`, `/ui/levels/window.js`, `/ui/levels/igu.js`, and `/ui/levels/atomic.js` are served cleanly.

## Playable Checkpoint
A user can start at the **Building** wall cutaway, explode it, drill into **Winco 4410S** (and swap to **Andersen 100**), drill into the **IGU** (and toggle Air vs. Argon), drill into the **Atomic** silicate network, click a `Na⁺` ion to read its chemistry card and open page 6 of the archived MDPI PDF—all with zero console errors.

## Verification Gates
- `python -m building_materials validate`, `gaps` (`0` gaps), and `python -m unittest discover -s tests -v` all pass.
- End-to-end browser walkthrough across all 4 levels + product swap + citation open.
- `screenshot-critique` on all 4 levels (Building, Window Winco/Andersen, IGU, Atomic) verifying cohesive Studio Architectural Cutaway lighting, clean typography, and zero visual defects.
