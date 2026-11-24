import * as THREE from "three";
import { getMaterials, makeBox, tagPart } from "../materials.js";

function makeWallFrame(w, h, openingW, openingH, depth, mat, opts = {}) {
  const g = new THREE.Group();
  const sideW = (w - openingW) / 2;
  const topH = (h - openingH) / 2;
  const left = makeBox(sideW, h, depth, mat, opts);
  left.position.set(-(openingW / 2 + sideW / 2), 0, 0);
  const right = makeBox(sideW, h, depth, mat, opts);
  right.position.set(openingW / 2 + sideW / 2, 0, 0);
  const top = makeBox(openingW, topH, depth, mat, opts);
  top.position.set(0, openingH / 2 + topH / 2, 0);
  const bot = makeBox(openingW, topH, depth, mat, opts);
  bot.position.set(0, -(openingH / 2 + topH / 2), 0);
  g.add(left, right, top, bot);
  return g;
}

export function buildBuildingLevel(spec = { window: "generic", fill: "argon" }) {
  const m = getMaterials();
  const root = new THREE.Group();
  const winVariant = spec?.window || "generic";
  const W = 2.6, H = 2.5, OW = 1.16, OH = 1.56;

  // 1. Exterior brick masonry veneer (+Z front)
  const brick = makeWallFrame(W, H, OW + 0.04, OH + 0.04, 0.11, m.brickMasonry, { edgeOpacity: 0.18 });
  brick.position.set(0, 0, 0.24);
  // Stone sill under the opening
  const stoneSill = makeBox(OW + 0.18, 0.08, 0.16, m.gypsumInterior, { edgeOpacity: 0.28 });
  stoneSill.position.set(0, -(OH / 2 + 0.06), 0.02);
  brick.add(stoneSill);
  tagPart(brick, {
    nodeId: "window-installation",
    explodeVec: new THREE.Vector3(0, 0, 0.85),
    callout: "Masonry Veneer & Opening",
  });
  root.add(brick);

  // 2. Exterior sheathing + liquid-applied flashing membrane around opening
  const sheathing = makeWallFrame(W, H, OW, OH, 0.035, m.sheathing, { edgeOpacity: 0.2 });
  sheathing.position.set(0, 0, 0.11);
  tagPart(sheathing, {
    nodeId: "window-specification",
    explodeVec: new THREE.Vector3(0, 0, 0.35),
    callout: "Exterior Sheathing",
  });
  root.add(sheathing);

  // Liquid-applied flashing sill pan & jamb wrap (UA Section 08 50 00)
  const flashing = new THREE.Group();
  const fThick = 0.018, fDepth = 0.22;
  const fSill = makeBox(OW + 0.04, fThick, fDepth, m.flashingMembrane, { edgeOpacity: 0.3 });
  fSill.position.set(0, -OH / 2 + fThick / 2, 0.0);
  const fLeft = makeBox(fThick, OH, fDepth, m.flashingMembrane, { edgeOpacity: 0.3 });
  fLeft.position.set(-OW / 2 + fThick / 2, 0, 0.0);
  const fRight = makeBox(fThick, OH, fDepth, m.flashingMembrane, { edgeOpacity: 0.3 });
  fRight.position.set(OW / 2 - fThick / 2, 0, 0.0);
  const fHead = makeBox(OW + 0.04, fThick, fDepth, m.flashingMembrane, { edgeOpacity: 0.3 });
  fHead.position.set(0, OH / 2 - fThick / 2, 0.0);
  flashing.add(fSill, fLeft, fRight, fHead);
  flashing.position.set(0, 0, 0.02);
  tagPart(flashing, {
    nodeId: "window-installation",
    explodeVec: new THREE.Vector3(0, -0.18, 0.52),
    callout: "Flashing & Sill Pan",
  });
  root.add(flashing);

  // 3. Wall stud framing + insulation cavity
  const framing = new THREE.Group();
  const studD = 0.14, studW = 0.055;
  const xs = [-W / 2 + studW / 2, -OW / 2 - studW / 2, OW / 2 + studW / 2, W / 2 - studW / 2];
  for (const x of xs) {
    const stud = makeBox(studW, H, studD, m.woodStud, { edgeOpacity: 0.2 });
    stud.position.set(x, 0, 0);
    framing.add(stud);
  }
  const header = makeBox(OW + studW * 2, 0.16, studD, m.woodStud, { edgeOpacity: 0.2 });
  header.position.set(0, OH / 2 + 0.08, 0);
  const sillPlate = makeBox(OW + studW * 2, 0.06, studD, m.woodStud, { edgeOpacity: 0.2 });
  sillPlate.position.set(0, -OH / 2 - 0.03, 0);
  const topPlate = makeBox(W, 0.06, studD, m.woodStud, { edgeOpacity: 0.2 });
  topPlate.position.set(0, H / 2 - 0.03, 0);
  const botPlate = makeBox(W, 0.06, studD, m.woodStud, { edgeOpacity: 0.2 });
  botPlate.position.set(0, -H / 2 + 0.03, 0);
  framing.add(header, sillPlate, topPlate, botPlate);

  // Subtle insulation batts in flanking stud bays
  const bayW = (W - OW) / 2 - studW * 2 - 0.02;
  if (bayW > 0.1) {
    for (const side of [-1, 1]) {
      const batt = makeBox(bayW, H - 0.14, studD - 0.02, m.insulationBatt, { edges: false, castShadow: false });
      batt.position.set(side * (OW / 2 + studW + bayW / 2 + 0.01), 0, 0);
      framing.add(batt);
    }
  }
  framing.position.set(0, 0, -0.02);
  tagPart(framing, {
    nodeId: "window-specification",
    explodeVec: new THREE.Vector3(0, 0, -0.25),
    callout: "Wall Framing",
  });
  root.add(framing);

  // 4. Interior gypsum board (-Z back)
  const gypsum = makeWallFrame(W, H, OW, OH, 0.025, m.gypsumInterior, { edgeOpacity: 0.16 });
  gypsum.position.set(0, 0, -0.13);
  tagPart(gypsum, {
    nodeId: "window-installation",
    explodeVec: new THREE.Vector3(0, 0, -0.72),
    callout: "Interior Drywall",
  });
  root.add(gypsum);

  // 5. Hero clickable Window Assembly seated inside the opening (morphs with active Spec)
  const winGroup = new THREE.Group();
  const fw = OW - 0.04, fh = OH - 0.04, fd = 0.13, ft = 0.065;
  const frameMat = winVariant === "andersen" ? m.fibrexComposite
    : winVariant === "winco" ? m.aluminumAnodized
    : m.genericFrame;
  const fL = makeBox(ft, fh, fd, frameMat);
  fL.position.set(-fw / 2 + ft / 2, 0, 0);
  const fR = makeBox(ft, fh, fd, frameMat);
  fR.position.set(fw / 2 - ft / 2, 0, 0);
  const fT = makeBox(fw, ft, fd, frameMat);
  fT.position.set(0, fh / 2 - ft / 2, 0);
  const fB = makeBox(fw, ft, fd, frameMat);
  fB.position.set(0, -fh / 2 + ft / 2, 0);
  const meetRail = makeBox(fw - ft * 2, 0.045, 0.06, frameMat);
  meetRail.position.set(0, 0.02, 0.01);

  const glassW = fw - ft * 2 + 0.01;
  const glassH = fh - ft * 2 + 0.01;
  const outerPane = makeBox(glassW, glassH, 0.012, m.glassSolargray, { edges: false, castShadow: false });
  outerPane.position.set(0, 0, 0.02);
  const innerPane = makeBox(glassW, glassH, 0.01, m.glassClear, { edges: false, castShadow: false });
  innerPane.position.set(0, 0, -0.02);

  winGroup.add(fL, fR, fT, fB, meetRail, outerPane, innerPane);
  winGroup.position.set(0, 0, 0.07);
  const winNodeId = winVariant === "winco" ? "winco-4410s-single-hung"
    : winVariant === "andersen" ? "andersen-100-single-hung"
    : "window-assembly";
  const winCallout = winVariant === "winco" ? "Winco 4410S Window"
    : winVariant === "andersen" ? "Andersen 100 Window"
    : "Window Assembly (Reference)";
  const winBrand = winVariant === "winco" ? "Winco" : winVariant === "andersen" ? "Andersen" : null;
  const winBadge = winVariant === "winco" ? "U 0.50" : winVariant === "andersen" ? "U 0.25" : "dbl-click";

  tagPart(winGroup, {
    nodeId: winNodeId,
    explodeVec: new THREE.Vector3(0, 0, 1.38),
    drillLevel: "window",
    callout: winCallout,
    brand: winBrand,
    badge: winBadge,
  });
  root.add(winGroup);

  return {
    group: root,
    cameraPos: new THREE.Vector3(3.85, 1.85, 5.15),
    target: new THREE.Vector3(0, 0, 0.25),
    floorY: -1.35,
    defaultNodeId: winNodeId,
  };
}
