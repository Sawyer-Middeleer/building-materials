# Slice 03 — Level 1: Building Facade & Wall Cutaway

## Objective
Build the top-level **Building Facade / Wall Cutaway** scene so learners start at the scale of a building wall opening before drilling into the window assembly.

## Scope & Seam
- **`ui/levels/building.js`:**
  - Procedural cutaway section of a classic masonry/framed exterior wall (~2.4m × 2.4m cutaway corner/bay) inspired by the University of Alabama Section 08 50 00 wall details:
    - Exterior brick/stone veneer course (`brickMasonry` PBR + subtle mortar joints)
    - Drainage cavity & continuous exterior sheathing
    - Wood/metal stud framing + interior gypsum board finish
    - Liquid-applied flashing sill pan & perimeter trim clip / panning (`window-installation` context)
    - Recessed rough opening containing the clickable **`window-assembly`** (`userData.nodeId = "window-assembly"`, `userData.drillLevel = "window"`).
  - **Explode behavior (0–100%):** Smoothly separates the exterior veneer forward, interior gypsum backward, flashing/panning outward, and slides the complete `window-assembly` forward out of the rough opening so the learner sees how a window actually sits in a wall.
  - **Visual callouts:** Subtle 2D HTML leader pins projected from 3D anchor points (hidden when collapsed, appearing cleanly when Explode > 25%) labeling the Window Assembly, Masonry Veneer, Flashing/Sill Pan, and Wall Framing.

## Playable Checkpoint
Landing on `http://127.0.0.1:8000/` shows the studio-lit architectural wall cutaway with the installed window. Dragging **Explode** peels back the wall layers and slides the window out of the opening; clicking the window inspects `window-assembly`; clicking **Drill In →** (or double-clicking the window) smoothly transitions the camera into Level 2.

## Verification Gates
- `screenshot-critique` + `compare-screenshots` (assembled vs. 70% exploded): verify architectural proportions, crisp cutaway edges, legible leader labels with zero overlap, and clear visual emphasis on the clickable window assembly.
