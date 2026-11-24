import * as THREE from "three";

function makeBrickTexture() {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 512;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#cfc8bc";
  ctx.fillRect(0, 0, 512, 512);
  const rows = 16, cols = 4;
  const rh = 512 / rows, cw = 512 / cols, mortar = 4;
  const tones = ["#b36247", "#a6583e", "#bc6d50", "#9e5139", "#b8684c"];
  for (let r = 0; r < rows; r++) {
    const offset = (r % 2) * (cw / 2);
    for (let col = -1; col <= cols; col++) {
      const idx = Math.abs((r * 7 + col * 13)) % tones.length;
      ctx.fillStyle = tones[idx];
      ctx.fillRect(col * cw + offset + mortar / 2, r * rh + mortar / 2, cw - mortar, rh - mortar);
    }
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.repeat.set(2.2, 2.2);
  return tex;
}

function makeWoodTexture() {
  const c = document.createElement("canvas");
  c.width = 256;
  c.height = 256;
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#d9c29c";
  ctx.fillRect(0, 0, 256, 256);
  ctx.strokeStyle = "rgba(130, 95, 50, 0.16)";
  for (let i = 0; i < 42; i++) {
    ctx.beginPath();
    ctx.moveTo(i * 6 + 2, 0);
    ctx.bezierCurveTo(i * 6 + 5, 85, i * 6 - 2, 170, i * 6 + 3, 256);
    ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

let _cache = null;

export function getMaterials() {
  if (_cache) return _cache;
  const brickMap = makeBrickTexture();
  const woodMap = makeWoodTexture();

  _cache = {
    glassSolargray: new THREE.MeshPhysicalMaterial({
      color: 0x627782,
      transmission: 0.68,
      transparent: true,
      opacity: 1,
      roughness: 0.06,
      metalness: 0.05,
      ior: 1.52,
      thickness: 0.14,
      reflectivity: 0.92,
      envMapIntensity: 1.25,
    }),
    glassClear: new THREE.MeshPhysicalMaterial({
      color: 0xeaf4f7,
      transmission: 0.86,
      transparent: true,
      opacity: 1,
      roughness: 0.04,
      metalness: 0.02,
      ior: 1.52,
      thickness: 0.10,
      reflectivity: 0.9,
      envMapIntensity: 1.2,
    }),
    lowECoating: new THREE.MeshPhysicalMaterial({
      color: 0x14b8a6,
      metalness: 0.72,
      roughness: 0.14,
      transparent: true,
      opacity: 0.44,
      iridescence: 1.0,
      iridescenceIOR: 1.75,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
    aluminumAnodized: new THREE.MeshStandardMaterial({
      color: 0xd5dae0,
      metalness: 0.82,
      roughness: 0.27,
      envMapIntensity: 1.15,
    }),
    aluminumSpacer: new THREE.MeshStandardMaterial({
      color: 0xbec6cf,
      metalness: 0.86,
      roughness: 0.24,
      envMapIntensity: 1.15,
    }),
    polyurethaneBreak: new THREE.MeshStandardMaterial({
      color: 0xd97706,
      metalness: 0.04,
      roughness: 0.44,
    }),
    fibrexComposite: new THREE.MeshStandardMaterial({
      color: 0x3b3834,
      metalness: 0.04,
      roughness: 0.68,
    }),
    genericFrame: new THREE.MeshStandardMaterial({
      color: 0x9aa3ad,
      metalness: 0.16,
      roughness: 0.48,
    }),
    pibBlack: new THREE.MeshStandardMaterial({
      color: 0x191a1e,
      metalness: 0.05,
      roughness: 0.55,
    }),
    siliconeSeal: new THREE.MeshStandardMaterial({
      color: 0x4b5563,
      metalness: 0.06,
      roughness: 0.46,
    }),
    argonGas: new THREE.MeshPhysicalMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.14,
      roughness: 0.2,
      depthWrite: false,
    }),
    airGas: new THREE.MeshPhysicalMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.08,
      roughness: 0.2,
      depthWrite: false,
    }),
    brickMasonry: new THREE.MeshStandardMaterial({
      map: brickMap,
      roughness: 0.86,
      metalness: 0.02,
    }),
    sheathing: new THREE.MeshStandardMaterial({
      color: 0xc2b28f,
      roughness: 0.82,
      metalness: 0.02,
    }),
    woodStud: new THREE.MeshStandardMaterial({
      map: woodMap,
      roughness: 0.78,
      metalness: 0.02,
    }),
    gypsumInterior: new THREE.MeshStandardMaterial({
      color: 0xf1efe9,
      roughness: 0.9,
      metalness: 0.0,
    }),
    flashingMembrane: new THREE.MeshStandardMaterial({
      color: 0x1e40af,
      roughness: 0.42,
      metalness: 0.12,
    }),
    insulationBatt: new THREE.MeshStandardMaterial({
      color: 0xe9c9b8,
      roughness: 0.95,
      metalness: 0.0,
    }),
    atomSilicon: new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.45, roughness: 0.28 }),
    atomOxygenBridge: new THREE.MeshStandardMaterial({ color: 0xdc2626, metalness: 0.12, roughness: 0.32 }),
    atomOxygenNonBridge: new THREE.MeshStandardMaterial({ color: 0xf97316, metalness: 0.12, roughness: 0.32 }),
    atomSodium: new THREE.MeshStandardMaterial({ color: 0x7c3aed, metalness: 0.25, roughness: 0.28 }),
    atomCalcium: new THREE.MeshStandardMaterial({ color: 0x0d9488, metalness: 0.25, roughness: 0.28 }),
    bondCovalent: new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.2, roughness: 0.45 }),
    tetraFacet: new THREE.MeshPhysicalMaterial({
      color: 0x3b82f6,
      transparent: true,
      opacity: 0.11,
      roughness: 0.25,
      side: THREE.DoubleSide,
      depthWrite: false,
    }),
    ghostContext: new THREE.MeshBasicMaterial({
      color: 0x94a3b8,
      transparent: true,
      opacity: 0.055,
      depthWrite: false,
    }),
  };
  return _cache;
}

export function addCadEdges(mesh, thresholdDeg = 24, color = 0x1e293b, opacity = 0.22) {
  const geo = new THREE.EdgesGeometry(mesh.geometry, thresholdDeg);
  const mat = new THREE.LineBasicMaterial({ color, transparent: true, opacity });
  const lines = new THREE.LineSegments(geo, mat);
  lines.raycast = () => {};
  mesh.add(lines);
  return lines;
}

export function makeBox(w, h, d, material, opts = {}) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  mesh.castShadow = opts.castShadow ?? true;
  mesh.receiveShadow = opts.receiveShadow ?? true;
  if (opts.edges !== false) {
    addCadEdges(mesh, opts.edgeThreshold ?? 24, opts.edgeColor ?? 0x1e293b, opts.edgeOpacity ?? 0.22);
  }
  return mesh;
}

export function makeGhostBox(w, h, d, edgeColor = 0x64748b, edgeOpacity = 0.22) {
  const m = getMaterials();
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m.ghostContext);
  mesh.castShadow = false;
  mesh.receiveShadow = false;
  mesh.raycast = () => {};
  addCadEdges(mesh, 20, edgeColor, edgeOpacity);
  return mesh;
}

export function tagPart(obj, { nodeId, explodeVec = null, drillLevel = null, callout = null, brand = null, badge = null }) {
  obj.userData.nodeId = nodeId;
  obj.userData.drillLevel = drillLevel;
  obj.userData.callout = callout;
  obj.userData.brand = brand;
  obj.userData.badge = badge;
  obj.userData.basePos = obj.position.clone();
  obj.userData.explodeVec = explodeVec ? explodeVec.clone() : new THREE.Vector3();
  obj.traverse((child) => {
    if (child.isMesh) {
      child.userData.owner = obj;
      child.userData.nodeId = nodeId;
      child.userData.drillLevel = drillLevel;
    }
  });
  return obj;
}
