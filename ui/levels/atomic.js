import * as THREE from "three";
import { getMaterials, makeGhostBox, tagPart } from "../materials.js";

function makeBond(p1, p2, mat, radius = 0.028) {
  const dir = new THREE.Vector3().subVectors(p2, p1);
  const len = dir.length();
  const cyl = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, len, 10), mat);
  cyl.position.copy(p1).add(p2).multiplyScalar(0.5);
  cyl.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir.normalize());
  cyl.castShadow = true;
  cyl.raycast = () => {};
  return cyl;
}

function makeTetrahedronMesh(corners, mat) {
  const [a, b, c, d] = corners;
  const positions = new Float32Array([
    a.x, a.y, a.z, b.x, b.y, b.z, c.x, c.y, c.z,
    a.x, a.y, a.z, c.x, c.y, c.z, d.x, d.y, d.z,
    a.x, a.y, a.z, d.x, d.y, d.z, b.x, b.y, b.z,
    b.x, b.y, b.z, d.x, d.y, d.z, c.x, c.y, c.z,
  ]);
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.computeVertexNormals();
  const mesh = new THREE.Mesh(geo, mat);
  mesh.raycast = () => {};
  return mesh;
}

export function buildAtomicLevel() {
  const m = getMaterials();
  const root = new THREE.Group();

  // Parent Level 3 Ghost Context: translucent cross-section of the 6mm float glass pane
  const glassSlice = makeGhostBox(4.35, 3.05, 0.92, 0x475569, 0.18);
  root.add(glassSlice);

  // Structured Zachariasen Continuous Random Network (2.5D architectural cutaway)
  // Left: intact 6-membered & 5-membered SiO4 rings; Right: broken modifier pocket hosting Na+ & Ca2+
  const siCoords = [
    // Left 6-membered ring (indices 0..5)
    new THREE.Vector3(-1.55,  0.52,  0.10), // 0
    new THREE.Vector3(-0.92,  0.96, -0.12), // 1
    new THREE.Vector3(-0.22,  0.58,  0.14), // 2
    new THREE.Vector3(-0.26, -0.24, -0.10), // 3
    new THREE.Vector3(-0.96, -0.68,  0.12), // 4
    new THREE.Vector3(-1.58, -0.26, -0.08), // 5
    // Upper-right 5-membered ring extension (indices 6..8)
    new THREE.Vector3( 0.48,  1.02, -0.14), // 6
    new THREE.Vector3( 1.24,  0.76,  0.12), // 7
    new THREE.Vector3( 1.52,  0.04, -0.12), // 8
    // Lower-right broken chain bordering the modifier cavity (indices 9..11)
    new THREE.Vector3( 0.42, -0.82,  0.10), // 9
    new THREE.Vector3( 1.22, -0.86, -0.10), // 10
    new THREE.Vector3(-0.92, -1.28, -0.12), // 11 (bottom anchor)
  ];

  // Bridging Si–O–Si covalent links (note the intentional open break between 2–8, 3–9/10, 8–10 forming the modifier cavity)
  const bridges = [
    [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 0], // intact 6-ring
    [1, 6], [6, 7], [7, 8], [2, 6],                 // upper 5-ring
    [3, 9], [9, 10], [4, 11],                       // lower chain
  ];

  const siGeo = new THREE.SphereGeometry(0.115, 22, 18);
  const oGeo = new THREE.SphereGeometry(0.082, 18, 16);
  const naGeo = new THREE.SphereGeometry(0.125, 20, 16);
  const caGeo = new THREE.SphereGeometry(0.135, 20, 16);

  const siCorners = siCoords.map(() => []);

  // 1. Silicon Network Formers (Si4+)
  siCoords.forEach((pos, idx) => {
    const sphere = new THREE.Mesh(siGeo, m.atomSilicon);
    sphere.position.copy(pos);
    sphere.castShadow = true;
    tagPart(sphere, {
      nodeId: "silicon",
      explodeVec: new THREE.Vector3(0, 0, -0.12),
      callout: idx === 1 ? "Silicon (Si⁴⁺) · Network Former" : null,
      badge: idx === 1 ? "Z=14" : null,
    });
    root.add(sphere);
  });

  // 2. Bridging Oxygens (Si–O–Si) with gentle 145° amorphous kink
  bridges.forEach(([i, j], idx) => {
    const a = siCoords[i];
    const b = siCoords[j];
    const mid = new THREE.Vector3().addVectors(a, b).multiplyScalar(0.5);
    const edge = new THREE.Vector3().subVectors(b, a).normalize();
    const perp = new THREE.Vector3(-edge.y, edge.x, 0).multiplyScalar(idx % 2 === 0 ? 0.07 : -0.07);
    mid.add(perp);
    mid.z += (idx % 2 === 0 ? 0.05 : -0.05);

    const oMesh = new THREE.Mesh(oGeo, m.atomOxygenBridge);
    oMesh.position.copy(mid);
    oMesh.castShadow = true;
    tagPart(oMesh, {
      nodeId: "oxygen",
      explodeVec: new THREE.Vector3(0, 0, -0.12),
      callout: idx === 0 ? "Bridging Oxygen (Si–O–Si)" : null,
    });
    root.add(oMesh);

    root.add(makeBond(a, mid, m.bondCovalent), makeBond(mid, b, m.bondCovalent));
    siCorners[i].push(mid.clone());
    siCorners[j].push(mid.clone());
  });

  // 3. Non-Bridging Oxygens (NBOs) terminating the broken bonds around the modifier cavity
  const nboSpecs = [
    { si: 2,  dir: new THREE.Vector3(0.65, -0.25, 0.12) },
    { si: 3,  dir: new THREE.Vector3(0.75,  0.18, 0.10) },
    { si: 8,  dir: new THREE.Vector3(-0.62, -0.30, 0.10) },
    { si: 9,  dir: new THREE.Vector3(0.28,  0.65, 0.12) },
    { si: 10, dir: new THREE.Vector3(0.18,  0.65, -0.08) },
    { si: 7,  dir: new THREE.Vector3(-0.22, -0.68, 0.08) },
  ];

  const nboPositions = [];
  nboSpecs.forEach(({ si, dir }, idx) => {
    const start = siCoords[si];
    const pos = start.clone().add(dir.clone().normalize().multiplyScalar(0.40));
    nboPositions.push(pos);
    siCorners[si].push(pos.clone());

    const oMesh = new THREE.Mesh(oGeo, m.atomOxygenNonBridge);
    oMesh.position.copy(pos);
    oMesh.castShadow = true;
    tagPart(oMesh, {
      nodeId: "oxygen",
      explodeVec: new THREE.Vector3(0, 0, 0.05),
      callout: idx === 0 ? "Non-Bridging Oxygen (O⁻)" : null,
    });
    root.add(oMesh);
    root.add(makeBond(start, pos, m.bondCovalent));
  });

  // Add subtle out-of-plane apical oxygens so each SiO4 tetrahedron has 4 complete corners
  siCoords.forEach((pos, i) => {
    while (siCorners[i].length < 4) {
      const zSign = siCorners[i].length % 2 === 0 ? 1 : -1;
      const apex = pos.clone().add(new THREE.Vector3(0.04 * zSign, 0.03, 0.34 * zSign));
      siCorners[i].push(apex);
      const oMesh = new THREE.Mesh(oGeo, m.atomOxygenBridge);
      oMesh.position.copy(apex);
      oMesh.scale.setScalar(0.84);
      tagPart(oMesh, { nodeId: "oxygen", explodeVec: new THREE.Vector3(0, 0, -0.12) });
      root.add(oMesh);
      root.add(makeBond(pos, apex, m.bondCovalent, 0.022));
    }
    root.add(makeTetrahedronMesh(siCorners[i].slice(0, 4), m.tetraFacet));
  });

  // 4. Modifier Ions in the Interstitial Cavity — pull cleanly forward (+Z) when Exploded
  // Sodium (Na+) Flux Modifiers nestled near single NBOs
  const naPositions = [
    new THREE.Vector3(0.55,  0.22, 0.16),
    new THREE.Vector3(-0.92, 0.14, 0.18), // inside the 6-ring interstitial void
  ];
  naPositions.forEach((pos, idx) => {
    const mesh = new THREE.Mesh(naGeo, m.atomSodium);
    mesh.position.copy(pos);
    mesh.castShadow = true;
    tagPart(mesh, {
      nodeId: "sodium-ion",
      explodeVec: new THREE.Vector3(0.18 * (idx === 0 ? 1 : -0.5), 0.12, 1.05),
      callout: idx === 0 ? "Sodium Ion (Na⁺) · Flux Modifier" : null,
      badge: idx === 0 ? "Z=11" : null,
    });
    root.add(mesh);
  });

  // Calcium (Ca2+) Network Stabilizer bridging opposing NBOs in the lower-right pocket
  const caPos = new THREE.Vector3(0.95, -0.22, 0.14);
  const caMesh = new THREE.Mesh(caGeo, m.atomCalcium);
  caMesh.position.copy(caPos);
  caMesh.castShadow = true;
  tagPart(caMesh, {
    nodeId: "calcium-ion",
    explodeVec: new THREE.Vector3(0.28, -0.14, 1.15),
    callout: "Calcium Ion (Ca²⁺) · Stabilizer",
    badge: "Z=20",
  });
  root.add(caMesh);

  return {
    group: root,
    cameraPos: new THREE.Vector3(0.65, 0.55, 6.45),
    target: new THREE.Vector3(0.15, -0.02, 0),
    floorY: -1.78,
    defaultNodeId: "amorphous-silicate-network",
  };
}
