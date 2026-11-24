import * as THREE from "three";
import { getMaterials, makeBox, makeGhostBox, tagPart } from "../materials.js";

function makePerimeter(w, h, thickness, depth, mat, opts = {}) {
  const g = new THREE.Group();
  const top = makeBox(w, thickness, depth, mat, opts);
  top.position.set(0, h / 2 - thickness / 2, 0);
  const bot = makeBox(w, thickness, depth, mat, opts);
  bot.position.set(0, -h / 2 + thickness / 2, 0);
  const left = makeBox(thickness, h - thickness * 2, depth, mat, opts);
  left.position.set(-w / 2 + thickness / 2, 0, 0);
  const right = makeBox(thickness, h - thickness * 2, depth, mat, opts);
  right.position.set(w / 2 - thickness / 2, 0, 0);
  g.add(top, bot, left, right);
  return g;
}

export function buildWindowLevel(variant = "generic", fill = "argon") {
  const m = getMaterials();
  const root = new THREE.Group();
  const isWinco = variant === "winco";
  const isAndersen = variant === "andersen";
  const isGeneric = !isWinco && !isAndersen;
  const W = 1.36, H = 1.82;

  const frameNode = isWinco ? "winco-4410s-frame" : isAndersen ? "andersen-100-frame" : "window-frame";
  const sashNode = isWinco ? "winco-4410s-sash" : isAndersen ? "andersen-100-sash" : "window-sash";
  const unitNode = isWinco ? "winco-4410s-single-hung" : isAndersen ? "andersen-100-single-hung" : "window-assembly";
  const iguNode = isGeneric ? "insulating-glass-unit" : (fill === "argon" ? "igu-gray-argon" : "igu-gray-air");

  if (isWinco) {
    // Winco 4410S: split 6063-T6 extruded aluminum + poured polyurethane thermal break
    const extFrame = makePerimeter(W, H, 0.075, 0.068, m.aluminumAnodized, { edgeOpacity: 0.28 });
    extFrame.position.set(0, 0, 0.064);
    tagPart(extFrame, {
      nodeId: frameNode,
      explodeVec: new THREE.Vector3(0, 0, 0.72),
      callout: "6063-T6 Exterior Frame",
      brand: "Winco",
    });
    root.add(extFrame);

    const thermalBreak = makePerimeter(W - 0.03, H - 0.03, 0.042, 0.042, m.polyurethaneBreak, { edgeOpacity: 0.3 });
    thermalBreak.position.set(0, 0, 0.0);
    tagPart(thermalBreak, {
      nodeId: "polyurethane-thermal-break",
      explodeVec: new THREE.Vector3(0, 0, 0.22),
      callout: "Polyurethane Thermal Break",
      brand: "Winco",
    });
    root.add(thermalBreak);

    const intFrame = makePerimeter(W, H, 0.075, 0.068, m.aluminumAnodized, { edgeOpacity: 0.28 });
    intFrame.position.set(0, 0, -0.064);
    tagPart(intFrame, {
      nodeId: frameNode,
      explodeVec: new THREE.Vector3(0, 0, -0.78),
      callout: "6063-T6 Interior Frame",
      brand: "Winco",
    });
    root.add(intFrame);
  } else if (isAndersen) {
    // Andersen 100 Series: Single-piece extruded Fibrex wood-polymer composite frame
    const fibrexFrame = makePerimeter(W, H, 0.088, 0.145, m.fibrexComposite, { edgeOpacity: 0.32, edgeColor: 0x0f172a });
    const flange = makePerimeter(W + 0.09, H + 0.09, 0.045, 0.008, m.fibrexComposite, { edgeOpacity: 0.24 });
    flange.position.set(0, 0, 0.055);
    fibrexFrame.add(flange);
    fibrexFrame.position.set(0, 0, 0);
    tagPart(fibrexFrame, {
      nodeId: frameNode,
      explodeVec: new THREE.Vector3(0, 0, -0.62),
      callout: "Fibrex Composite Frame",
      brand: "Andersen",
    });
    root.add(fibrexFrame);
  } else {
    // Generic Reference Architecture: neutral perimeter frame (no proprietary thermal break or flange)
    const refFrame = makePerimeter(W, H, 0.082, 0.135, m.genericFrame, { edgeOpacity: 0.3 });
    refFrame.position.set(0, 0, 0);
    tagPart(refFrame, {
      nodeId: frameNode,
      explodeVec: new THREE.Vector3(0, 0, -0.58),
      callout: "Window Perimeter Frame",
    });
    root.add(refFrame);
  }

  // Lower operable single-hung sash
  const sashW = W - 0.16, sashH = H * 0.48;
  const sashMat = isWinco ? m.aluminumAnodized : isAndersen ? m.fibrexComposite : m.genericFrame;
  const sash = makePerimeter(sashW, sashH, 0.052, 0.058, sashMat, { edgeOpacity: 0.28 });
  const latch = makeBox(0.11, 0.022, 0.025, m.aluminumSpacer);
  latch.position.set(0, sashH / 2 - 0.01, -0.036);
  sash.add(latch);
  sash.position.set(0, -H * 0.22, -0.015);
  tagPart(sash, {
    nodeId: sashNode,
    explodeVec: new THREE.Vector3(0, -0.26, -0.32),
    callout: isWinco ? "Aluminum Operable Sash" : isAndersen ? "Fibrex Operable Sash" : "Operable Sash",
    brand: isWinco ? "Winco" : isAndersen ? "Andersen" : null,
  });
  root.add(sash);

  // Upper fixed IGU + lower sash IGU (clickable -> drills to Level 3 IGU)
  const makeIguUnit = (gw, gh, yPos, zPos, explodeZ, label) => {
    const g = new THREE.Group();
    const outer = makeBox(gw, gh, 0.012, m.glassSolargray, { edges: false, castShadow: false });
    outer.position.set(0, 0, 0.018);
    const lowe = makeBox(gw - 0.02, gh - 0.02, 0.002, m.lowECoating, { edges: false, castShadow: false });
    lowe.position.set(0, 0, 0.010);
    const spacer = makePerimeter(gw - 0.01, gh - 0.01, 0.018, 0.024, m.aluminumSpacer, { edgeOpacity: 0.25 });
    const inner = makeBox(gw, gh, 0.012, m.glassClear, { edges: false, castShadow: false });
    inner.position.set(0, 0, -0.018);
    g.add(outer, lowe, spacer, inner);
    g.position.set(0, yPos, zPos);
    tagPart(g, {
      nodeId: iguNode,
      explodeVec: new THREE.Vector3(0, yPos > 0 ? 0.14 : -0.18, explodeZ),
      drillLevel: "igu",
      callout: label,
      brand: isGeneric ? null : "Vitro",
      badge: isGeneric ? "dbl-click" : (fill === "argon" ? "U 0.24" : "U 0.28"),
    });
    return g;
  };

  root.add(makeIguUnit(W - 0.17, H * 0.45, H * 0.23, 0.018, 0.42, "Upper Insulating Glass Unit"));
  root.add(makeIguUnit(sashW - 0.09, sashH - 0.09, -H * 0.22, -0.012, -0.02, "Lower Sash IGU"));

  // Parent Level 1 Ghost Context: faint architectural outline of the surrounding wall opening
  const ghostWall = new THREE.Group();
  const wallT = 0.34, wallD = 0.26;
  const gTop = makeGhostBox(W + wallT * 2, wallT, wallD);
  gTop.position.set(0, H / 2 + wallT / 2 + 0.02, -0.02);
  const gBot = makeGhostBox(W + wallT * 2, wallT * 0.85, wallD + 0.06);
  gBot.position.set(0, -H / 2 - (wallT * 0.85) / 2 - 0.02, 0.01);
  const gLeft = makeGhostBox(wallT, H + 0.04, wallD);
  gLeft.position.set(-W / 2 - wallT / 2 - 0.02, 0, -0.02);
  const gRight = makeGhostBox(wallT, H + 0.04, wallD);
  gRight.position.set(W / 2 + wallT / 2 + 0.02, 0, -0.02);
  ghostWall.add(gTop, gBot, gLeft, gRight);
  root.add(ghostWall);

  return {
    group: root,
    cameraPos: new THREE.Vector3(3.25, 1.35, 4.45),
    target: new THREE.Vector3(0, 0, 0.1),
    floorY: -1.35,
    defaultNodeId: unitNode,
  };
}
