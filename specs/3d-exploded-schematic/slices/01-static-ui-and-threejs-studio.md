# Slice 01 — Static `/ui/*` Serving & Three.js Studio Cutaway Rig

## Objective
Establish the zero-bundler ES module architecture and the **Studio Architectural Cutaway** lighting/material/camera rig in Three.js.

## Scope & Seam
- **`building_materials.py`:** Add path-traversal-safe static serving for `/ui/<path>` (`.js` as `application/javascript`, `.css` as `text/css`).
- **`viewer.html`:** Add `<script type="importmap">` pinned to Three.js `0.170.0` (CDN ES modules: `three`, `three/addons/controls/OrbitControls.js`, `three/addons/environments/RoomEnvironment.js`), add **Schematic** as the default first tab in top nav (`Schematic | Graph | Compare | Tables | Gaps`), and mount the 3D canvas container.
- **`ui/studio.js`:**
  - `WebGLRenderer` (`antialias: true`, `ACESFilmicToneMapping`, `toneMappingExposure = 1.05`, `PCFSoftShadowMap`, `devicePixelRatio` capped at 2).
  - Warm architectural paper background (`#f4f2ec`) + subtle studio floor shadow catcher (`ShadowMaterial`, opacity `0.12`).
  - Lighting: `PMREMGenerator` + `RoomEnvironment` IBL for realistic glass/metal reflections + soft key `DirectionalLight` casting crisp shadows + cool fill light.
  - `OrbitControls` with smooth damping (`enableDamping: true`), sensible polar/distance limits, and `frameObject(group)` + smooth camera tween helper.
  - Explode controller (`setExplode(t)` for `t ∈ [0, 1]`) lerping every child mesh with `userData.explodeVec` from its base position.
- **`ui/materials.js`:**
  - Reusable PBR material presets (`glassClear`, `glassSolargray`, `lowECoating`, `aluminumAnodized`, `polyurethaneBreak`, `fibrexComposite`, `pibBlack`, `siliconeSeal`, `brickMasonry`, `gypsumInterior`, `flashingMembrane`).
  - Helper `addCadEdges(mesh, thresholdDeg = 24, opacity = 0.22)` attaching crisp `LineSegments(EdgesGeometry)` so every PBR solid reads like a hyperrealistic architectural schematic.

## Playable Checkpoint
Loading `http://127.0.0.1:8000/` opens directly to the **Schematic** tab showing a 3-piece studio-lit test stack (aluminum frame, tinted glass, inner glass) with smooth orbit/zoom and a working 0–100% **Explode** slider.

## Verification Gates
- `python -m unittest discover -s tests -v` passes (including a check that `/ui/studio.js` returns 200 and path traversal returns 404).
- Browser loads with 0 console errors; Explode slider smoothly separates parts and resets cleanly.
- `screenshot-critique` verifies warm-paper backdrop, crisp CAD edges, soft ground shadows, and realistic glass reflection/transmission without harsh clipping.
