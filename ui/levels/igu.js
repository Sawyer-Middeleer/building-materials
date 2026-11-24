import * as THREE from "three";
import { getMaterials, makeBox, makeGhostBox, tagPart } from "../materials.js";

export function buildIguLevel(fill = "argon", variant = "generic") {
  const m = getMaterials();
  const root = new THREE.Group();
  const showBrand = variant !== "generic";

  // Specimen dimensions (1-inch IGU corner cutaway, scaled nicely for studio view)
  const W = 1.65;
  const H = 1.65;
  const paneT = 0.09;     // 6mm nominal glass pane
  const gapD = 0.30;      // 1/2" gas cavity
  const spacerW = 0.10;   // spacer depth inward from perimeter

  // 1. Outer Solargray Glass Pane (z > 0 is exterior)
  const outerZ = gapD / 2 + paneT / 2;
  const outerPane = makeBox(W, H, paneT, m.glassSolargray, {
    edgeColor: 0x334155,
    edgeOpacity: 0.34,
    castShadow: false,
  });
  outerPane.position.set(0, 0, outerZ);
  tagPart(outerPane, {
    nodeId: "outer-pane",
    drillLevel: "atomic",
    explodeVec: new THREE.Vector3(0, 0, 1.05),
    callout: "Outer Pane · Solargray 6mm",
    brand: showBrand ? "Vitro" : null,
    badge: "Atomic →",
  });
  root.add(outerPane);

  // 2. Low-E Coating Film (Surface #2 — interior face of outer pane)
  const lowE = new THREE.Mesh(
    new THREE.BoxGeometry(W - 0.04, H - 0.04, 0.012),
    m.lowECoating
  );
  lowE.position.set(0, 0, gapD / 2 - 0.008);
  tagPart(lowE, {
    nodeId: "low-e-coating",
    explodeVec: new THREE.Vector3(0, 0, 0.62),
    callout: "Low-E Coating · Surface #2",
    brand: showBrand ? "Vitro" : null,
    badge: "SHGC 0.19",
  });
  root.add(lowE);

  // 3. Sealed Gas Cavity (Argon or Dry Air)
  const cavityGroup = new THREE.Group();
  const cavW = W - spacerW - 0.08;
  const cavH = H - spacerW - 0.08;
  const cavBox = new THREE.Mesh(
    new THREE.BoxGeometry(cavW, cavH, gapD - 0.03),
    fill === "argon" ? m.argonGas : m.airGas
  );
  cavBox.position.set(spacerW / 2, spacerW / 2, 0);
  cavityGroup.add(cavBox);

  // Subtle gas molecule dots inside cavity so the fill reads clearly as a layer
  const dotMat = new THREE.MeshStandardMaterial({
    color: fill === "argon" ? 0x0284c7 : 0x64748b,
    roughness: 0.3,
    metalness: 0.1,
  });
  const dotGeo = new THREE.SphereGeometry(0.018, 10, 10);
  const coords = [
    [-0.38, 0.35, -0.05], [-0.12, 0.52, 0.04], [0.22, 0.44, -0.02], [0.48, 0.28, 0.05],
    [-0.32, 0.05, 0.04], [0.02, 0.14, -0.06], [0.36, -0.04, 0.03],
    [-0.24, -0.28, -0.04], [0.14, -0.24, 0.05], [0.46, -0.36, -0.03],
    [-0.02, -0.46, 0.02], [0.28, 0.18, -0.05],
  ];
  for (const [x, y, z] of coords) {
    const d = new THREE.Mesh(dotGeo, dotMat);
    d.position.set(x + spacerW / 2, y + spacerW / 2, z);
    cavityGroup.add(d);
  }
  tagPart(cavityGroup, {
    nodeId: fill === "argon" ? "argon-cavity" : "air-cavity",
    explodeVec: new THREE.Vector3(0, 0, 0.16),
    callout: fill === "argon" ? "Argon Gas Cavity" : "Dry Air Cavity",
    badge: fill === "argon" ? "U 0.24" : "U 0.28",
  });
  root.add(cavityGroup);

  // 4. Aluminum Edge Spacer (L-shaped cutaway along left & bottom edges)
  const spacerGroup = new THREE.Group();
  const spD = gapD - 0.015;
  const spThick = 0.085;
  // Left vertical leg
  const spLeft = makeBox(spThick, H - 0.08, spD, m.aluminumSpacer);
  spLeft.position.set(-W / 2 + spThick / 2 + 0.04, 0, 0);
  spacerGroup.add(spLeft);
  // Bottom horizontal leg
  const spBot = makeBox(W - 0.08, spThick, spD, m.aluminumSpacer);
  spBot.position.set(0, -H / 2 + spThick / 2 + 0.04, 0);
  spacerGroup.add(spBot);

  // Subtle desiccant sightline perforation dots along inner face of spacer
  const perfMat = new THREE.MeshStandardMaterial({ color: 0x334155, roughness: 0.7 });
  const perfGeo = new THREE.BoxGeometry(0.008, 0.026, 0.016);
  for (let i = -5; i <= 5; i++) {
    const p = new THREE.Mesh(perfGeo, perfMat);
    p.position.set(-W / 2 + spThick + 0.042, i * 0.12 + 0.05, 0);
    spacerGroup.add(p);
  }
  const perfGeoH = new THREE.BoxGeometry(0.026, 0.008, 0.016);
  for (let i = -5; i <= 5; i++) {
    const p = new THREE.Mesh(perfGeoH, perfMat);
    p.position.set(i * 0.12 + 0.05, -H / 2 + spThick + 0.042, 0);
    spacerGroup.add(p);
  }
  tagPart(spacerGroup, {
    nodeId: "edge-spacer",
    explodeVec: new THREE.Vector3(-0.34, -0.22, -0.18),
    callout: "Aluminum Edge Spacer",
  });
  root.add(spacerGroup);

  // 5. Primary Seal — Polyisobutylene (PIB) beads between spacer & both glass panes
  const pibGroup = new THREE.Group();
  const pibT = 0.014;
  const pibW = 0.055;
  for (const zSign of [1, -1]) {
    const zPos = zSign * (gapD / 2 - pibT / 2);
    const pL = makeBox(pibW, H - 0.08, pibT, m.pibBlack, { edges: false });
    pL.position.set(-W / 2 + spThick / 2 + 0.04, 0, zPos);
    const pB = makeBox(W - 0.08, pibW, pibT, m.pibBlack, { edges: false });
    pB.position.set(0, -H / 2 + spThick / 2 + 0.04, zPos);
    pibGroup.add(pL, pB);
  }
  tagPart(pibGroup, {
    nodeId: "polyisobutylene",
    explodeVec: new THREE.Vector3(-0.56, -0.36, -0.36),
    callout: "Primary Seal · PIB Vapor Barrier",
  });
  root.add(pibGroup);

  // 6. Secondary Structural Seal — Silicone perimeter bead behind spacer
  const silGroup = new THREE.Group();
  const silT = 0.042;
  const silD = gapD + paneT * 1.4;
  const sL = makeBox(silT, H, silD, m.siliconeSeal);
  sL.position.set(-W / 2 + silT / 2, 0, 0);
  const sB = makeBox(W, silT, silD, m.siliconeSeal);
  sB.position.set(0, -H / 2 + silT / 2, 0);
  silGroup.add(sL, sB);
  tagPart(silGroup, {
    nodeId: "silicone-sealant",
    explodeVec: new THREE.Vector3(-0.80, -0.52, -0.52),
    callout: "Secondary Seal · Silicone",
  });
  root.add(silGroup);

  // 7. Inner Clear Glass Pane (z < 0 is interior)
  const innerZ = -(gapD / 2 + paneT / 2);
  const innerPane = makeBox(W, H, paneT, m.glassClear, {
    edgeColor: 0x334155,
    edgeOpacity: 0.32,
    castShadow: false,
  });
  innerPane.position.set(0, 0, innerZ);
  tagPart(innerPane, {
    nodeId: "inner-pane",
    drillLevel: "atomic",
    explodeVec: new THREE.Vector3(0, 0, -0.95),
    callout: "Inner Pane · Clear 6mm",
    badge: "Atomic →",
  });
  root.add(innerPane);

  // Parent Level 2 Ghost Context: translucent window sash glazing pocket wrapping the left & bottom IGU edges
  const ghostSash = new THREE.Group();
  const pocketD = gapD + paneT * 2 + 0.16;
  const pocketW = 0.22;
  const sLeft = makeGhostBox(pocketW, H + 0.24, pocketD, 0x64748b, 0.2);
  sLeft.position.set(-W / 2 - pocketW / 2 + 0.05, -0.05, 0);
  const sBot = makeGhostBox(W + 0.24, pocketW, pocketD, 0x64748b, 0.2);
  sBot.position.set(-0.05, -H / 2 - pocketW / 2 + 0.05, 0);
  ghostSash.add(sLeft, sBot);
  root.add(ghostSash);

  return {
    group: root,
    cameraPos: new THREE.Vector3(3.75, 2.05, 4.55),
    target: new THREE.Vector3(-0.18, -0.1, 0.05),
    floorY: -1.45,
    defaultNodeId: fill === "argon" ? "igu-gray-argon" : "igu-gray-air",
  };
}
