# Slice 02 — Raycast Binding & Unified Inspector (Graph + Guide + Citations)

## Objective
Connect 3D meshes directly to the graph (`/api/graph`, `/api/cite`) and the companion educational guide (`/api/guide`), so clicking any rendered piece explains **what it is**, **what it's made of**, **how it performs**, and **which PDF proves it**.

## Scope & Seam
- **`ui/studio.js`:**
  - Pointer raycasting against interactive meshes (`userData.nodeId`):
    - Hover: subtle highlight outline/emissive lift + floating 2D cursor tooltip showing the node's label and `kind`.
    - Click: selects `userData.nodeId`, highlights the mesh, and notifies `inspector.js`.
    - Double-click (when `userData.drillLevel` is set): triggers level transition.
  - Boot-time contract check: verify every `userData.nodeId` in the mounted scene exists in `/api/graph`.
- **`ui/inspector.js`:**
  - Shared right-hand drawer used by **Schematic** (and all secondary tabs).
  - Sections in calm visual hierarchy:
    1. **Header:** kind/stage tags, label, ID, and a prominent **`Drill In →`** button when the selected mesh supports a deeper 3D level (plus `Parts` / `Trace` / `Used By` quick-links to the Graph tab).
    2. **Learn / About Card** (from `/api/guide` `nodes[id]`, tailored by `kind`):
       - **Firm card** (`actor` with `firm`): Founded, HQ, segment, known for, website link.
       - **Chemistry card** (`chemicalEntity` with `chemistry`): Formula, atomic number, molar mass, category, and role in the window.
       - **Process card** (`process` with `steps`): Numbered plain-English manufacturing steps + why it matters.
       - **Component / Material card**: Plain-English summary, how it works, tradeoffs.
    3. **Direct Facts** (from graph statements): Each metric displays value + unit + scope + basis + `cite` button AND a quiet `?` button that toggles the inline property explainer from `/api/guide` `properties[prop]` (`title`, `summary`, `betterDirection`, `typicalRange`).
    4. **Relationships** (Outgoing / Incoming) + inline **Citation Card** (with `Open archived snapshot ↗` PDF link).

## Playable Checkpoint
Clicking any mesh in the 3D scene immediately updates the right Inspector with its **About** card, `?` metric explainers, graph links, and clickable PDF citations; clicking `andersen` or `vitro` in Outgoing/Incoming links shows the Company Profile card.

## Verification Gates
- 0 console errors; clicking every mesh in the test scene resolves a valid graph node.
- Clicking `?` on `uFactor` opens the inline U-factor explainer; clicking `cite` opens the archived PDF link at `#page=N`.
- `screenshot-critique` verifies the Inspector is calm, scannable, and never visually crowds the 3D canvas.
