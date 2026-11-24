# 3D Exploded Architectural Schematic UI

## Goal

Make the Building Materials explorer a **hyperrealistic, interactive 3D architectural schematic** where a learner starts at a building wall/facade, explodes it into components, clicks any piece to drill down through **4 physical scales** (`Building → Window Unit → IGU → Atomic Silicate Network`), and inspects the exact **graph claims**, **educational guide**, **firm/chemistry cards**, and **PDF source citations** bound directly to every rendered 3D mesh.

## Locked Decisions

- **Renderer & Geometry:** Pure procedural **Three.js** (ES modules, zero Blender pipeline, zero `npm`/bundler build step). All geometry, PBR materials, and CAD edge-line overlays are authored in small modular JS files under `ui/` served directly by `building_materials.py`.
- **4-Level Drill-Down Stack (v1 Window Slice):**
  1. **Building Facade / Wall Cutaway** (`window-assembly` in a schematic masonry/framed wall opening)
  2. **Complete Window Unit** (exploded frame, thermal break, sash, IGU — with live **Winco 4410S Aluminum** vs. **Andersen 100 Series Fibrex** product swap)
  3. **Insulating Glass Unit (IGU)** (outer Solargray pane, nanometer `low-e-coating` on surface #2, aluminum `edge-spacer`, dual PIB + silicone `edge-seal`, toggleable `air-cavity` / `argon-cavity`, clear `inner-pane`)
  4. **Atomic Scale** (3D disordered `SiO₄` tetrahedral silicate network with `silicon`, `oxygen`, `sodium-ion`, and `calcium-ion` bound to `window.guide.json` chemistry cards)
- **Visual Direction — Studio Architectural Cutaway:**
  - Warm light-paper studio backdrop (`#f4f2ec`), neutral studio IBL (`RoomEnvironment`), soft ground contact shadows.
  - Physically based PBR materials (`MeshPhysicalMaterial` with transmission/IOR/tint for glass, brushed metallic aluminum, matte textured Fibrex composite, subtle translucent gas volume).
  - Crisp, restrained CAD edge lines (`EdgesGeometry` at low opacity) and clean leader-line callouts on exploded parts.
- **UI Cutover:** The 3D Schematic becomes the primary landing tab (`Schematic`) in `viewer.html`, keeping `Graph`, `Compare`, `Tables`, and `Gaps` as secondary tabs. Hard cutover—no legacy compatibility shims.

## Module & API Seams

```text
building_materials.py   # adds static serving for /ui/* (JS/CSS) alongside existing /api/*
viewer.html             # top nav (Schematic | Graph | Compare | Tables | Gaps) + shared Inspector
ui/
  studio.js             # Three.js renderer, RoomEnvironment IBL, camera/OrbitControls, raycaster, tweening
  materials.js          # shared PBR material library + CAD edge-line & cutaway helpers
  inspector.js          # unified right drawer: Guide card + Direct Facts (? explainers) + Links + Citations
  levels/
    building.js         # Level 1: wall cutaway + clickable window opening
    window.js           # Level 2: Winco 4410S vs Andersen 100 exploded window unit
    igu.js              # Level 3: 6-layer exploded IGU cutaway (air/argon toggle)
    atomic.js           # Level 4: 3D disordered SiO4 tetrahedral network + Na+/Ca2+ ions
```

### Data Binding Contract (3D Mesh → Graph + Guide)
Every interactive `THREE.Object3D` carries:
- `userData.nodeId`: exact node ID in `fixtures/window.json` (validated against `/api/graph` on boot—unknown IDs log a loud error).
- `userData.explodeVec`: `THREE.Vector3` direction and distance for the 0–100% **Explode** slider.
- `userData.drillLevel`: optional next level ID (`"window"`, `"igu"`, `"atomic"`) triggered by clicking the **Drill In** button or double-clicking the mesh.

## Slice Ladder

| Slice | Focus | Playable Checkpoint |
| --- | --- | --- |
| [01](slices/01-static-ui-and-threejs-studio.md) | Static `/ui/*` serving & Three.js Studio Cutaway rig | `http://127.0.0.1:8000/` renders studio-lit PBR + CAD-edged placeholder block with orbit, pan, zoom, and explode slider. |
| [02](slices/02-unified-inspector-and-guide-binding.md) | Raycast binding + unified Inspector (Graph + Guide + Citations) | Clicking any 3D mesh selects its graph node and renders its `guide.json` card, `?` metric explainers, facts, links, and PDF citations. |
| [03](slices/03-level-1-building-facade.md) | Level 1: Building wall cutaway & opening | Explodable wall section (masonry veneer, sheathing, cavity, flashing, sill pan) with clickable `window-assembly` that drills to Level 2. |
| [04](slices/04-level-2-window-unit-and-product-swap.md) | Level 2: Window Unit + Winco/Andersen live swap | Explodable frame, polyurethane thermal break, sash, and IGU; toggling Winco 4410S ↔ Andersen 100 swaps 3D geometry, materials, and Inspector facts live. |
| [05](slices/05-level-3-igu-layers.md) | Level 3: 6-layer IGU cutaway | Explodable outer Solargray lite, surface #2 low-e film, aluminum spacer, PIB/silicone dual seal, air/argon cavity toggle, and clear inner lite. |
| [06](slices/06-level-4-atomic-silicate-network-and-integration.md) | Level 4: Atomic silicate network & full polish | 3D disordered `SiO₄` tetrahedral network with clickable `Si`, `O`, `Na⁺`, `Ca²⁺` ions, breadcrumb navigation, and full end-to-end verification. |

## Standing Verification Gates

Every visual slice (01–06) must pass before landing:
1. **CLI & Tests:** `python -m building_materials validate`, `gaps`, and `python -m unittest discover -s tests -v` stay green.
2. **Browser Smoke:** Zero console errors, 60fps smooth orbit/explode, raycast click updates Inspector.
3. **Visual Gate (`screenshot-critique`):** Capture a live screenshot of the slice's 3D view (assembled + exploded) and run an unprimed `screenshot-critique` pass checking lighting, material readability, edge-line crispness, framing, and label legibility.
4. **Before/After Comparison (`compare-screenshots`):** From Slice 03 onward, compare each slice's render against the previous checkpoint to confirm visual fidelity improved without regressions.

## Non-Goals (v1)

- No Blender `.glb` authoring pipeline or asset bundler (`npm` / Vite / Webpack).
- No photorealistic ray-traced path tracing (standard Three.js PBR + `RoomEnvironment` IBL + soft shadows only).
- No full-building multi-room interior modeling—Level 1 is a focused architectural wall/facade cutaway framing the window opening.
- No backward-compatibility shims for the previous landing layout.
