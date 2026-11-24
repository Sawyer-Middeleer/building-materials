import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

export type PlateMode = "window" | "atomic";
export type CameraPreset = "axon" | "section" | "plan";
export type MaterialArchetype = "generic" | "fibrex" | "clad-wood" | "aluminum";

export interface PlatePartSpec {
  id: string;
  label: string;
  nodeId: string;
  basePos: [number, number, number];
  explodeVec: [number, number, number];
  anchorLocal: [number, number, number];
}

interface ProjectedCallout {
  id: string;
  label: string;
  x: number;
  y: number;
  labelX: number;
}

interface PlotterPlate3DProps {
  mode: PlateMode;
  materialArchetype?: MaterialArchetype;
  selectedPartId: string | null;
  onSelectPart: (partId: string, nodeId: string) => void;
  explode: number; // 0..1
  preset: CameraPreset;
  presetTick: number;
}

const ARCHETYPE_PALETTE: Record<
  MaterialArchetype,
  { frame: number; sash: number; fin: number; thermalBreak?: number }
> = {
  generic: { frame: 0xeae3d6, sash: 0xf2ede3, fin: 0xeae3d6 },
  fibrex: { frame: 0x7b6b5d, sash: 0x918071, fin: 0xe5dfd3 },
  "clad-wood": { frame: 0xf4f3ee, sash: 0xdfb982, fin: 0xf4f3ee },
  aluminum: { frame: 0xc5ccd1, sash: 0xd0d6da, fin: 0xb8c0c6, thermalBreak: 0x2d2b28 },
};

const INK = 0x181715;
const INK_LIGHT = 0x5c574f;
const VERMILION = 0xc93d24;
const VERMILION_HOVER = 0xe38f7e;
const PAPER_FILL = 0xf7f4ed;
const FRAME_TINT = 0xeae3d6;
const SASH_TINT = 0xf2ede3;
const GLASS_TINT = 0xd7e6e5;
const COATING_TINT = 0xc6dada;
const METAL_TINT = 0xdad7cf;
const DARK_SEAL = 0x45413b;
const WALL_SHEATH = 0xe6e0d2;
const WALL_STUD = 0xf1ece1;

function addInkMesh(
  parent: THREE.Object3D,
  geo: THREE.BufferGeometry,
  color: number,
  partId: string,
  opts?: {
    opacity?: number;
    transparent?: boolean;
    pos?: [number, number, number];
    rot?: [number, number, number];
    edgeColor?: number;
    edgeAngle?: number;
  }
): THREE.Mesh {
  const mat = new THREE.MeshLambertMaterial({
    color,
    transparent: opts?.transparent ?? false,
    opacity: opts?.opacity ?? 1,
    side: THREE.DoubleSide,
    polygonOffset: true,
    polygonOffsetFactor: 1,
    polygonOffsetUnits: 1,
  });
  const mesh = new THREE.Mesh(geo, mat);
  mesh.userData = {
    isPickableMesh: partId !== "wall",
    partId,
    baseColor: color,
    baseOpacity: opts?.opacity ?? 1,
  };
  if (opts?.pos) mesh.position.set(...opts.pos);
  if (opts?.rot) mesh.rotation.set(...opts.rot);

  const edges = new THREE.EdgesGeometry(geo, opts?.edgeAngle ?? 24);
  const line = new THREE.LineSegments(
    edges,
    new THREE.LineBasicMaterial({ color: opts?.edgeColor ?? INK })
  );
  line.userData = { isEdge: true };
  mesh.add(line);
  parent.add(mesh);
  return mesh;
}

function extrudeProfile(
  points: [number, number][],
  depth: number,
  bevel = 0
): THREE.ExtrudeGeometry {
  const shape = new THREE.Shape();
  points.forEach(([x, y], idx) => {
    if (idx === 0) shape.moveTo(x, y);
    else shape.lineTo(x, y);
  });
  shape.closePath();
  return new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: bevel > 0,
    bevelThickness: bevel,
    bevelSize: bevel,
    bevelSegments: 1,
  });
}

function buildWindowAssembly(
  root: THREE.Group,
  archetype: MaterialArchetype = "generic"
): {
  groups: Map<string, THREE.Group>;
  specs: PlatePartSpec[];
} {
  const pal = ARCHETYPE_PALETTE[archetype];
  const groups = new Map<string, THREE.Group>();
  const makeGroup = (id: string) => {
    const g = new THREE.Group();
    g.userData = { partId: id };
    root.add(g);
    groups.set(id, g);
    return g;
  };

  // --- WALL ROUGH-OPENING CUTAWAY (architectural context, non-pickable) ---
  const wallG = makeGroup("wall");
  // Sill wood plate (2x6 rough opening sill)
  addInkMesh(wallG, new THREE.BoxGeometry(2.55, 0.24, 1.02), WALL_STUD, "wall", {
    pos: [0.06, -1.24, -0.04],
    edgeColor: INK_LIGHT,
  });
  // Right framing stud jamb
  addInkMesh(wallG, new THREE.BoxGeometry(0.28, 2.38, 1.02), WALL_STUD, "wall", {
    pos: [1.2, -0.05, -0.04],
    edgeColor: INK_LIGHT,
  });
  // Exterior sheathing + siding layer on right jamb
  addInkMesh(wallG, new THREE.BoxGeometry(0.32, 2.52, 0.14), WALL_SHEATH, "wall", {
    pos: [1.22, -0.05, 0.54],
    edgeColor: INK_LIGHT,
  });
  // Sloped metal sill flashing pan under window sill
  const panGeo = extrudeProfile(
    [
      [-0.48, 0.0],
      [0.46, 0.0],
      [0.46, -0.09],
      [0.42, -0.09],
      [0.42, -0.03],
      [-0.45, -0.03],
      [-0.45, 0.08],
      [-0.48, 0.08],
    ],
    2.24
  );
  panGeo.rotateY(Math.PI / 2);
  addInkMesh(wallG, panGeo, METAL_TINT, "wall", {
    pos: [-1.14, -1.09, 0.0],
    edgeColor: INK_LIGHT,
  });
  // Interior drywall return trim
  addInkMesh(wallG, new THREE.BoxGeometry(0.1, 2.36, 0.16), PAPER_FILL, "wall", {
    pos: [1.04, -0.05, -0.6],
    edgeColor: INK_LIGHT,
  });

  // --- 1. PERIMETER FRAME (extruded stepped architectural jamb + sloped sill + nailing flange) ---
  const frameG = makeGroup("frame");
  // Stepped left jamb profile (depth extruded vertically along Y)
  const jambProfile = extrudeProfile(
    [
      [-0.42, 0.0], // exterior face
      [0.36, 0.0], // interior face
      [0.36, 0.18], // interior stop
      [0.14, 0.18], // sash pocket step
      [0.14, 0.25], // weatherstrip kerf ridge
      [-0.12, 0.25], // main thermal web
      [-0.12, 0.16], // exterior drip rebate
      [-0.36, 0.16],
      [-0.36, 0.22], // exterior rain screen lip
      [-0.42, 0.22],
    ],
    2.18
  );
  jambProfile.rotateX(-Math.PI / 2);
  jambProfile.rotateY(Math.PI / 2);
  addInkMesh(frameG, jambProfile, pal.frame, "frame", { pos: [-1.05, -1.06, 0.0] });

  // Right jamb (mirrored stepped profile)
  const rightJamb = extrudeProfile(
    [
      [-0.42, 0.0],
      [0.36, 0.0],
      [0.36, 0.16],
      [0.12, 0.16],
      [0.12, 0.22],
      [-0.14, 0.22],
      [-0.14, 0.14],
      [-0.42, 0.14],
    ],
    2.18
  );
  rightJamb.rotateX(-Math.PI / 2);
  rightJamb.rotateY(-Math.PI / 2);
  addInkMesh(frameG, rightJamb, pal.frame, "frame", { pos: [1.02, -1.06, 0.0] });

  // Sloped water-shedding sill extrusion (extruded horizontally along X)
  const sillProfile = extrudeProfile(
    [
      [-0.44, -0.04], // exterior nose drip
      [0.38, -0.04], // interior sill base
      [0.38, 0.2], // interior stool lip
      [0.12, 0.2], // sash seat
      [0.12, 0.13], // drainage channel
      [-0.14, 0.11], // sloped exterior sill plane
      [-0.44, 0.06], // sloped nose
    ],
    2.07
  );
  sillProfile.rotateY(Math.PI / 2);
  addInkMesh(frameG, sillProfile, pal.frame, "frame", { pos: [-1.05, -1.04, 0.0] });

  // Poured-and-debridged polyurethane thermal break strip on thermally broken aluminum frames
  if (pal.thermalBreak !== undefined) {
    addInkMesh(frameG, new THREE.BoxGeometry(0.16, 2.18, 0.09), pal.thermalBreak, "frame", {
      pos: [-0.95, 0.03, 0.02],
    });
    addInkMesh(frameG, new THREE.BoxGeometry(2.07, 0.14, 0.09), pal.thermalBreak, "frame", {
      pos: [-0.015, -0.97, 0.02],
    });
  }

  // Integrated exterior nailing flange (1-3/8" setback fin)
  addInkMesh(frameG, new THREE.BoxGeometry(0.11, 2.34, 0.03), pal.fin, "frame", {
    pos: [-1.1, 0.02, 0.42],
  });
  addInkMesh(frameG, new THREE.BoxGeometry(2.26, 0.11, 0.03), pal.fin, "frame", {
    pos: [-0.02, -1.11, 0.42],
  });

  // --- 2. OPERABLE SASH (stepped glazing-pocket sash extrusion + snap-in glazing bead) ---
  const sashG = makeGroup("sash");
  const sashStile = extrudeProfile(
    [
      [-0.2, 0.0],
      [0.22, 0.0],
      [0.22, 0.15],
      [0.1, 0.15], // glazing rabbet interior
      [0.1, 0.08], // glazing pocket seat
      [-0.11, 0.08],
      [-0.11, 0.16], // exterior glazing leg
      [-0.2, 0.16],
    ],
    1.84
  );
  sashStile.rotateX(-Math.PI / 2);
  sashStile.rotateY(Math.PI / 2);
  addInkMesh(sashG, sashStile, pal.sash, "sash", { pos: [-0.82, -0.84, 0.04] });

  const sashRight = extrudeProfile(
    [
      [-0.2, 0.0],
      [0.22, 0.0],
      [0.22, 0.15],
      [0.1, 0.15],
      [0.1, 0.08],
      [-0.11, 0.08],
      [-0.11, 0.16],
      [-0.2, 0.16],
    ],
    1.84
  );
  sashRight.rotateX(-Math.PI / 2);
  sashRight.rotateY(-Math.PI / 2);
  addInkMesh(sashG, sashRight, pal.sash, "sash", { pos: [0.8, -0.84, 0.04] });

  const sashRail = extrudeProfile(
    [
      [-0.2, 0.0],
      [0.22, 0.0],
      [0.22, 0.16],
      [0.09, 0.16],
      [0.09, 0.09],
      [-0.11, 0.09],
      [-0.11, 0.17],
      [-0.2, 0.17],
    ],
    1.62
  );
  sashRail.rotateY(Math.PI / 2);
  addInkMesh(sashG, sashRail, pal.sash, "sash", { pos: [-0.82, -0.84, 0.04] });

  // Snap-in interior glazing bead along bottom rail
  addInkMesh(sashG, new THREE.BoxGeometry(1.42, 0.055, 0.045), pal.sash, "sash", {
    pos: [-0.01, -0.68, -0.15],
  });

  // --- 3. COATED OUTER GLASS PANE (1/4" architectural lite + surface #2 low-e tint) ---
  const outerG = makeGroup("outer-pane");
  addInkMesh(outerG, new THREE.BoxGeometry(1.42, 1.68, 0.036), GLASS_TINT, "outer-pane", {
    pos: [-0.01, 0.12, 0.125],
    transparent: true,
    opacity: 0.62,
  });
  // Thin low-e coating indicator strip on surface #2 (cavity side)
  addInkMesh(outerG, new THREE.BoxGeometry(1.38, 1.64, 0.008), COATING_TINT, "outer-pane", {
    pos: [-0.01, 0.12, 0.102],
    transparent: true,
    opacity: 0.45,
    edgeColor: INK_LIGHT,
  });

  // --- 4. WARM-EDGE STAINLESS SPACER BAR + DUAL PERIMETER SEAL ---
  const spacerG = makeGroup("spacer");
  // U-channel hollow stainless steel spacer along left, bottom, right perimeter
  addInkMesh(spacerG, new THREE.BoxGeometry(0.048, 1.64, 0.13), METAL_TINT, "spacer", {
    pos: [-0.69, 0.12, 0.02],
  });
  addInkMesh(spacerG, new THREE.BoxGeometry(1.42, 0.048, 0.13), METAL_TINT, "spacer", {
    pos: [-0.01, -0.69, 0.02],
  });
  addInkMesh(spacerG, new THREE.BoxGeometry(0.048, 1.64, 0.13), METAL_TINT, "spacer", {
    pos: [0.67, 0.12, 0.02],
  });
  // Secondary silicone perimeter seal bead outside spacer
  addInkMesh(spacerG, new THREE.BoxGeometry(1.46, 0.032, 0.155), DARK_SEAL, "spacer", {
    pos: [-0.01, -0.73, 0.02],
  });
  addInkMesh(spacerG, new THREE.BoxGeometry(0.032, 1.68, 0.155), DARK_SEAL, "spacer", {
    pos: [-0.73, 0.12, 0.02],
  });

  // --- 5. CLEAR INNER GLASS PANE ---
  const innerG = makeGroup("inner-pane");
  addInkMesh(innerG, new THREE.BoxGeometry(1.42, 1.68, 0.036), GLASS_TINT, "inner-pane", {
    pos: [-0.01, 0.12, -0.085],
    transparent: true,
    opacity: 0.48,
  });

  // --- 6. DUAL WEATHERSTRIPPING (bulb compression gasket + fin-seal kerf strip) ---
  const weatherG = makeGroup("weatherstripping");
  // Vertical compression bulb cylinder + kerf fin along left jamb
  addInkMesh(weatherG, new THREE.CylinderGeometry(0.026, 0.026, 1.88, 10), DARK_SEAL, "weatherstripping", {
    pos: [-0.85, 0.08, -0.17],
  });
  addInkMesh(weatherG, new THREE.BoxGeometry(0.045, 1.88, 0.022), DARK_SEAL, "weatherstripping", {
    pos: [-0.89, 0.08, -0.17],
  });
  // Horizontal sill compression bulb
  const sillBulb = new THREE.CylinderGeometry(0.026, 0.026, 1.68, 10);
  sillBulb.rotateZ(Math.PI / 2);
  addInkMesh(weatherG, sillBulb, DARK_SEAL, "weatherstripping", {
    pos: [-0.01, -0.87, -0.17],
  });

  // --- 7. OPERATING HARDWARE (cam sash lock housing, contoured lever handle, hinge track) ---
  const hwG = makeGroup("hardware");
  // Stainless steel sill hinge channel track
  addInkMesh(hwG, new THREE.BoxGeometry(0.76, 0.028, 0.09), METAL_TINT, "hardware", {
    pos: [-0.24, -0.89, 0.06],
  });
  // Sash lock escutcheon base plate
  addInkMesh(hwG, new THREE.BoxGeometry(0.11, 0.34, 0.045), METAL_TINT, "hardware", {
    pos: [-0.79, 0.02, -0.26],
  });
  // Sculpted cam lock handle lever
  const leverGeo = extrudeProfile(
    [
      [0, 0],
      [0.055, 0],
      [0.07, -0.22],
      [0.02, -0.24],
    ],
    0.04
  );
  addInkMesh(hwG, leverGeo, METAL_TINT, "hardware", {
    pos: [-0.82, 0.06, -0.32],
  });
  // Sill operator crank shoe housing
  addInkMesh(hwG, new THREE.BoxGeometry(0.32, 0.085, 0.11), METAL_TINT, "hardware", {
    pos: [0.06, -0.86, -0.31],
  });

  const specs: PlatePartSpec[] = [
    {
      id: "frame",
      label: "Frame",
      nodeId: "envelope.openings.window.frame",
      basePos: [0, 0, 0],
      explodeVec: [-0.62, -0.06, 0.18],
      anchorLocal: [-1.05, 1.12, 0.0],
    },
    {
      id: "sash",
      label: "Sash",
      nodeId: "envelope.openings.window.sash",
      basePos: [0, 0, 0],
      explodeVec: [-0.22, 0.04, 0.25],
      anchorLocal: [-0.82, 1.0, 0.04],
    },
    {
      id: "outer-pane",
      label: "Outer Pane",
      nodeId: "envelope.openings.window.outer-pane",
      basePos: [0, 0, 0],
      explodeVec: [0, 0.08, 1.02],
      anchorLocal: [-0.22, 0.96, 0.125],
    },
    {
      id: "spacer",
      label: "IGU Spacer",
      nodeId: "envelope.openings.window.spacer",
      basePos: [0, 0, 0],
      explodeVec: [0, 0.04, 0.52],
      anchorLocal: [0.12, 0.94, 0.02],
    },
    {
      id: "inner-pane",
      label: "Inner Pane",
      nodeId: "envelope.openings.window.inner-pane",
      basePos: [0, 0, 0],
      explodeVec: [0, 0, -0.26],
      anchorLocal: [0.46, 0.96, -0.085],
    },
    {
      id: "weatherstripping",
      label: "Weatherstrip",
      nodeId: "envelope.openings.window.weatherstripping",
      basePos: [0, 0, 0],
      explodeVec: [-0.36, -0.14, -0.66],
      anchorLocal: [-0.85, 1.02, -0.17],
    },
    {
      id: "hardware",
      label: "Hardware",
      nodeId: "envelope.openings.window.hardware",
      basePos: [0, 0, 0],
      explodeVec: [0.16, -0.32, -0.96],
      anchorLocal: [-0.79, 0.2, -0.26],
    },
  ];

  return { groups, specs };
}

function buildAtomicNetwork(root: THREE.Group): {
  groups: Map<string, THREE.Group>;
  specs: PlatePartSpec[];
} {
  const groups = new Map<string, THREE.Group>();
  const makeGroup = (id: string) => {
    const g = new THREE.Group();
    g.userData = { partId: id };
    root.add(g);
    groups.set(id, g);
    return g;
  };

  const siG = makeGroup("chem.si");
  const oG = makeGroup("chem.o");
  const naG = makeGroup("chem.na-ion");
  const caG = makeGroup("chem.ca-ion");

  const tetraCenters: [number, number, number][] = [
    [-0.95, 0.25, 0.2],
    [-0.15, 0.65, -0.25],
    [0.72, 0.3, 0.18],
    [-0.55, -0.58, -0.15],
    [0.25, -0.32, 0.42],
    [0.95, -0.52, -0.22],
    [-0.08, -0.02, -0.68],
  ];

  tetraCenters.forEach(([x, y, z], idx) => {
    addInkMesh(siG, new THREE.TetrahedronGeometry(0.46, 0), PAPER_FILL, "chem.si", {
      pos: [x, y, z],
      rot: [idx * 0.45, idx * 0.7, 0.2],
      transparent: true,
      opacity: 0.72,
    });
    addInkMesh(siG, new THREE.SphereGeometry(0.08, 12, 12), INK, "chem.si", { pos: [x, y, z] });
  });

  const bridges: [number, number, number][] = [
    [-0.55, 0.45, -0.02],
    [0.28, 0.48, -0.03],
    [-0.75, -0.16, 0.02],
    [-0.15, -0.45, 0.14],
    [0.58, -0.42, 0.1],
    [0.48, 0.0, 0.3],
    [-0.12, 0.32, -0.46],
  ];
  bridges.forEach((pos) => {
    addInkMesh(oG, new THREE.OctahedronGeometry(0.095, 0), GLASS_TINT, "chem.o", { pos });
  });

  const naPositions: [number, number, number][] = [
    [-0.32, 0.08, 0.56],
    [0.52, 0.02, -0.34],
    [-0.02, -0.82, -0.05],
  ];
  naPositions.forEach((pos) => {
    addInkMesh(naG, new THREE.SphereGeometry(0.125, 16, 16), VERMILION, "chem.na-ion", { pos });
  });

  const caPositions: [number, number, number][] = [
    [0.18, 0.16, 0.08],
    [-0.78, -0.78, 0.32],
  ];
  caPositions.forEach((pos) => {
    addInkMesh(caG, new THREE.SphereGeometry(0.14, 16, 16), METAL_TINT, "chem.ca-ion", { pos });
  });

  const specs: PlatePartSpec[] = [
    {
      id: "chem.si",
      label: "Silicon (Si)",
      nodeId: "chem.si",
      basePos: [0, 0, 0],
      explodeVec: [-0.35, 0.25, 0],
      anchorLocal: [-0.95, 0.68, 0.2],
    },
    {
      id: "chem.o",
      label: "Bridging Oxygen (O)",
      nodeId: "chem.o",
      basePos: [0, 0, 0],
      explodeVec: [0, 0.48, 0],
      anchorLocal: [-0.15, 0.58, -0.02],
    },
    {
      id: "chem.na-ion",
      label: "Alkali Modifier (Na+)",
      nodeId: "chem.na-ion",
      basePos: [0, 0, 0],
      explodeVec: [0.35, 0.22, 0.45],
      anchorLocal: [0.52, 0.14, -0.34],
    },
    {
      id: "chem.ca-ion",
      label: "Stabilizer (Ca2+)",
      nodeId: "chem.ca-ion",
      basePos: [0, 0, 0],
      explodeVec: [0.42, -0.32, 0.25],
      anchorLocal: [0.18, 0.3, 0.08],
    },
  ];

  return { groups, specs };
}

export function PlotterPlate3D({
  mode,
  materialArchetype = "generic",
  selectedPartId,
  onSelectPart,
  explode,
  preset,
  presetTick,
}: PlotterPlate3DProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [callouts, setCallouts] = useState<ProjectedCallout[]>([]);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  const stateRef = useRef({
    selectedPartId,
    hoveredId,
    explode,
    onSelectPart,
  });
  stateRef.current = { selectedPartId, hoveredId, explode, onSelectPart };

  const cameraCtrlRef = useRef<{
    setPreset: (p: CameraPreset) => void;
  } | null>(null);

  useEffect(() => {
    cameraCtrlRef.current?.setPreset(preset);
  }, [preset, presetTick]);

  useEffect(() => {
    const container = stageRef.current;
    if (!container) return;

    const scene = new THREE.Scene();
    const root = new THREE.Group();
    scene.add(root);

    const { groups, specs } =
      mode === "atomic" ? buildAtomicNetwork(root) : buildWindowAssembly(root, materialArchetype);

    // Collect ONLY pickable Mesh objects (excludes LineSegments and wall cutaway)
    const pickableMeshes: THREE.Mesh[] = [];
    root.traverse((obj) => {
      if (obj instanceof THREE.Mesh && obj.userData?.isPickableMesh) {
        pickableMeshes.push(obj);
      }
    });

    // Bright architectural print-plate lighting (delicate 3-tone plane shading, zero muddy shadows)
    const hemi = new THREE.HemisphereLight(0xffffff, 0xede8dc, 1.05);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xfffdf8, 0.34);
    key.position.set(5, 9, 7);
    scene.add(key);

    const width = container.clientWidth || 720;
    const height = container.clientHeight || 420;
    const aspect = width / height;
    const frustum = mode === "atomic" ? 3.5 : 4.25;

    const camera = new THREE.OrthographicCamera(
      (-frustum * aspect) / 2,
      (frustum * aspect) / 2,
      frustum / 2,
      -frustum / 2,
      0.1,
      50
    );

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(width, height);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.enablePan = false;
    controls.minZoom = 0.7;
    controls.maxZoom = 2.4;

    const applyPreset = (p: CameraPreset) => {
      if (p === "section") {
        camera.position.set(0.01, 0.05, 8);
      } else if (p === "plan") {
        camera.position.set(0.01, 8, 0.01);
      } else {
        camera.position.set(5.4, 3.6, 6.2);
      }
      camera.lookAt(0, 0, 0);
      controls.target.set(0, 0, 0);
      controls.update();
    };
    applyPreset(preset);
    cameraCtrlRef.current = { setPreset: applyPreset };

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerDownPos = { x: 0, y: 0 };

    const getHitPart = (e: PointerEvent): string | null => {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
      raycaster.setFromCamera(pointer, camera);
      const hits = raycaster.intersectObjects(pickableMeshes, false);
      if (hits.length === 0) return null;
      return (hits[0].object.userData?.partId as string) ?? null;
    };

    const onPointerDown = (e: PointerEvent) => {
      pointerDownPos = { x: e.clientX, y: e.clientY };
    };
    const onPointerUp = (e: PointerEvent) => {
      const dist = Math.hypot(e.clientX - pointerDownPos.x, e.clientY - pointerDownPos.y);
      if (dist > 6) return;
      const pid = getHitPart(e);
      if (pid) {
        const spec = specs.find((s) => s.id === pid);
        if (spec) stateRef.current.onSelectPart(spec.id, spec.nodeId);
      }
    };
    const onPointerMove = (e: PointerEvent) => {
      if (e.buttons !== 0) return; // don't flicker highlights while orbiting
      const pid = getHitPart(e);
      setHoveredId(pid);
      renderer.domElement.style.cursor = pid ? "pointer" : "grab";
    };
    const onPointerLeave = () => {
      setHoveredId(null);
    };

    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
    renderer.domElement.addEventListener("pointermove", onPointerMove);
    renderer.domElement.addEventListener("pointerleave", onPointerLeave);

    const onResize = () => {
      const w = container.clientWidth || 720;
      const h = container.clientHeight || 420;
      const a = w / h;
      camera.left = (-frustum * a) / 2;
      camera.right = (frustum * a) / 2;
      camera.top = frustum / 2;
      camera.bottom = -frustum / 2;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
      renderer.render(scene, camera);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(container);
    renderer.render(scene, camera);

    let rafId = 0;
    let lastProjectionTime = 0;

    const animate = (now: number) => {
      rafId = requestAnimationFrame(animate);
      controls.update();

      const { explode: targetExplode, selectedPartId: sel, hoveredId: hov } = stateRef.current;

      for (const spec of specs) {
        const g = groups.get(spec.id);
        if (!g) continue;
        const tx = spec.basePos[0] + spec.explodeVec[0] * targetExplode;
        const ty = spec.basePos[1] + spec.explodeVec[1] * targetExplode;
        const tz = spec.basePos[2] + spec.explodeVec[2] * targetExplode;
        g.position.lerp(new THREE.Vector3(tx, ty, tz), 0.15);

        const isSel = sel === spec.id;
        const isHov = hov === spec.id;
        g.traverse((obj) => {
          if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshLambertMaterial) {
            const baseColor = obj.userData.baseColor as number;
            const baseOpacity = obj.userData.baseOpacity as number;
            if (isSel) {
              obj.material.color.setHex(VERMILION);
              obj.material.opacity = Math.max(baseOpacity, 0.88);
            } else if (isHov) {
              obj.material.color.setHex(VERMILION_HOVER);
              obj.material.opacity = Math.max(baseOpacity, 0.84);
            } else {
              obj.material.color.setHex(baseColor);
              obj.material.opacity = baseOpacity;
            }
          }
        });
      }

      renderer.render(scene, camera);

      // Update projected leader endpoints at ~20fps while keeping top labels FIXED in order (never teleporting!)
      if (now - lastProjectionTime > 48) {
        lastProjectionTime = now;
        const w = container.clientWidth || 720;
        const h = container.clientHeight || 420;
        const pad = 64;
        const span = Math.max(120, w - pad * 2);
        const projected = specs.map((spec, idx) => {
          const g = groups.get(spec.id);
          const world = new THREE.Vector3(...spec.anchorLocal);
          if (g) world.add(g.position);
          world.project(camera);
          const x = ((world.x + 1) / 2) * w;
          const y = ((-world.y + 1) / 2) * h;
          const labelX = specs.length > 1 ? pad + (idx / (specs.length - 1)) * span : w / 2;
          return {
            id: spec.id,
            label: spec.label,
            x,
            y,
            labelX,
          };
        });
        setCallouts(projected);
      }
    };
    rafId = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafId);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      renderer.domElement.removeEventListener("pointermove", onPointerMove);
      renderer.domElement.removeEventListener("pointerleave", onPointerLeave);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === container) {
        container.removeChild(renderer.domElement);
      }
    };
  }, [mode, materialArchetype]);

  return (
    <div className="plate-canvas-stage" ref={stageRef}>
      {/* Fixed-label dotted leader lines that track 3D anchors smoothly without swapping top labels */}
      <svg className="callout-layer" width="100%" height="100%" aria-hidden="true">
        {callouts.map((c) => {
          const active = selectedPartId === c.id;
          const hov = hoveredId === c.id;
          return (
            <g key={c.id}>
              <line
                x1={c.labelX}
                y1={34}
                x2={c.x}
                y2={c.y}
                stroke={active ? "#c93d24" : hov ? "#d87d6b" : "#a8a296"}
                strokeWidth={active ? 1.15 : 0.75}
                strokeDasharray="2 3"
              />
              <circle
                cx={c.x}
                cy={c.y}
                r={active ? 3.2 : 2}
                fill={active ? "#c93d24" : "#181715"}
              />
            </g>
          );
        })}
      </svg>

      {/* Stationary, unnumbered top callout labels */}
      <div className="callout-layer">
        {callouts.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`callout-tag${selectedPartId === c.id ? " active" : ""}`}
            style={{ left: `${c.labelX}px`, top: "10px" }}
            onMouseEnter={() => setHoveredId(c.id)}
            onMouseLeave={() => setHoveredId(null)}
            onClick={() => {
              const target =
                mode === "atomic" ? c.id : `envelope.openings.window.${c.id}`;
              onSelectPart(c.id, target);
            }}
          >
            {c.label}
          </button>
        ))}
      </div>
    </div>
  );
}
