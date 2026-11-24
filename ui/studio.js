import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { RoomEnvironment } from "three/addons/environments/RoomEnvironment.js";

export class SchematicStudio {
  constructor(container, { onSelect, onDrill, onHover }) {
    this.container = container;
    this.onSelect = onSelect;
    this.onDrill = onDrill;
    this.onHover = onHover;

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0xf4f2ec);

    const w = Math.max(1, container.clientWidth);
    const h = Math.max(1, container.clientHeight);
    this.camera = new THREE.PerspectiveCamera(34, w / h, 0.05, 100);
    this.camera.position.set(3.2, 2.1, 4.2);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h);
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.06;
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(this.renderer.domElement);

    // Studio IBL via RoomEnvironment for clean glass & anodized aluminum reflections
    const pmrem = new THREE.PMREMGenerator(this.renderer);
    this.envRT = pmrem.fromScene(new RoomEnvironment(), 0.04);
    this.scene.environment = this.envRT.texture;
    pmrem.dispose();

    // Soft architectural key + fill + rim lighting
    const hemi = new THREE.HemisphereLight(0xfffdf8, 0xd8d4c8, 0.55);
    this.scene.add(hemi);

    const key = new THREE.DirectionalLight(0xfffaf0, 1.35);
    key.position.set(4.5, 6.5, 5.0);
    key.castShadow = true;
    key.shadow.mapSize.set(1024, 1024);
    key.shadow.camera.near = 0.5;
    key.shadow.camera.far = 22;
    key.shadow.camera.left = -4;
    key.shadow.camera.right = 4;
    key.shadow.camera.top = 4;
    key.shadow.camera.bottom = -4;
    key.shadow.bias = -0.0005;
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0xe0ecff, 0.55);
    fill.position.set(-5, 2.5, -3);
    this.scene.add(fill);

    // Subtle ground contact shadow plane
    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(24, 24),
      new THREE.ShadowMaterial({ opacity: 0.11 })
    );
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.6;
    floor.receiveShadow = true;
    floor.raycast = () => {};
    this.floor = floor;
    this.scene.add(floor);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;
    this.controls.minDistance = 0.6;
    this.controls.maxDistance = 16;
    this.controls.maxPolarAngle = Math.PI * 0.88;

    this.rootGroup = new THREE.Group();
    this.scene.add(this.rootGroup);

    this.explode = 0;
    this.targetExplode = 0;
    this.interactiveParts = [];
    this.selectedNodeId = null;
    this.lensDirectIds = null;     // Set<string> | null
    this.lensContainerIds = null;  // Set<string> | null
    this.hoveredMesh = null;
    this.calloutLayer = null;
    this.leaderSvg = null;
    this.anchorCardEl = null;
    this.calloutEls = [];
    this.tween = null;

    this.raycaster = new THREE.Raycaster();
    this.pointer = new THREE.Vector2();
    this.downPos = { x: 0, y: 0 };

    this._bindEvents();
    this._raf = requestAnimationFrame(() => this._loop());
  }

  attachCalloutLayer(el, leaderSvg = null, anchorCardEl = null) {
    this.calloutLayer = el;
    this.leaderSvg = leaderSvg;
    this.anchorCardEl = anchorCardEl;
    this._rebuildCallouts();
  }

  setContent(group, { cameraPos, target = new THREE.Vector3(0, 0, 0), floorY = -1.5, keepCamera = false } = {}) {
    while (this.rootGroup.children.length) {
      this.rootGroup.remove(this.rootGroup.children[0]);
    }
    this.rootGroup.add(group);
    this.floor.position.y = floorY;

    this.interactiveParts = [];
    group.traverse((obj) => {
      if (obj.userData?.basePos) {
        this.interactiveParts.push(obj);
      }
    });
    this._applyExplode(this.explode);
    this._rebuildCallouts();

    if (!keepCamera && cameraPos) {
      this.tweenCamera(cameraPos, target);
    }
  }

  tweenCamera(pos, target = new THREE.Vector3(0, 0, 0), durationMs = 460) {
    this.tween = {
      start: performance.now(),
      duration: durationMs,
      fromPos: this.camera.position.clone(),
      toPos: pos.clone(),
      fromTarget: this.controls.target.clone(),
      toTarget: target.clone(),
    };
  }

  setExplode(t) {
    this.targetExplode = Math.max(0, Math.min(1, t));
  }

  setSelectedNode(nodeId) {
    this.selectedNodeId = nodeId;
    this._updateHighlights();
  }

  setLensNodes(directIds = null, containerIds = null) {
    this.lensDirectIds = directIds && directIds.size ? directIds : null;
    this.lensContainerIds = containerIds && containerIds.size ? containerIds : null;
    this._updateHighlights();
  }

  _applyExplode(t) {
    for (const part of this.interactiveParts) {
      const b = part.userData.basePos;
      const v = part.userData.explodeVec;
      if (b && v) {
        part.position.set(b.x + v.x * t, b.y + v.y * t, b.z + v.z * t);
      }
    }
  }

  _rebuildCallouts() {
    if (!this.calloutLayer) return;
    this.calloutLayer.innerHTML = "";
    this.calloutEls = [];
    const seen = new Set();
    for (const part of this.interactiveParts) {
      const label = part.userData.callout;
      if (!label || seen.has(label)) continue;
      seen.add(label);
      const pin = document.createElement("button");
      pin.className = "callout-pin";
      const brand = part.userData.brand;
      const badge = part.userData.badge;
      pin.innerHTML = `${brand ? `<span class="pin-brand">${brand}</span>` : ""}<span>${label}</span>${badge ? `<span class="pin-metric">${badge}</span>` : ""}`;
      pin.onclick = (e) => {
        e.stopPropagation();
        if (part.userData.nodeId) this.onSelect?.(part.userData.nodeId, part.userData.drillLevel);
      };
      this.calloutLayer.appendChild(pin);
      this.calloutEls.push({ el: pin, part });
    }
  }

  _updateCallouts() {
    if (!this.calloutLayer) return;
    const lensActive = Boolean(this.lensDirectIds || this.lensContainerIds);
    const showAll = this.explode >= 0.18;
    const w = this.container.clientWidth;
    const h = this.container.clientHeight;
    const box = new THREE.Box3();
    const pos = new THREE.Vector3();
    const anchor = new THREE.Vector3();

    const placed = [];
    for (const item of this.calloutEls) {
      const nid = item.part.userData.nodeId;
      const inLens = (this.lensDirectIds?.has(nid)) || (this.lensContainerIds?.has(nid));
      if (!showAll && !inLens) {
        item.el.style.opacity = "0";
        item.el.style.pointerEvents = "none";
        continue;
      }
      if (lensActive && !inLens && nid !== this.selectedNodeId) {
        item.el.style.opacity = "0";
        item.el.style.pointerEvents = "none";
        continue;
      }
      box.setFromObject(item.part);
      box.getCenter(anchor);
      pos.copy(anchor);
      pos.y = box.max.y + 0.05;
      pos.project(this.camera);
      anchor.project(this.camera);
      const visible = pos.z < 1 && pos.x > -1.05 && pos.x < 1.05 && pos.y > -1.05 && pos.y < 1.05;
      if (!visible) {
        item.el.style.opacity = "0";
        item.el.style.pointerEvents = "none";
        continue;
      }
      const ew = item.el.offsetWidth || 120;
      const halfW = ew / 2 + 12;
      const maxRight = this.anchorCardEl && this.anchorCardEl.style.display !== "none" ? w - 340 : w;
      const sx = Math.max(halfW, Math.min(Math.max(halfW + 10, maxRight - halfW), (pos.x * 0.5 + 0.5) * w));
      const sy = Math.max(66, Math.min(h - 92, (-pos.y * 0.5 + 0.5) * h));
      const ax = (anchor.x * 0.5 + 0.5) * w;
      const ay = (-anchor.y * 0.5 + 0.5) * h;
      placed.push({ item, sx, sy, ax, ay, hw: ew / 2 + 6 });
    }

    // Gentle vertical de-overlap pass so callout pills stay readable
    placed.sort((a, b) => a.sy - b.sy);
    for (let i = 0; i < placed.length; i++) {
      for (let j = 0; j < i; j++) {
        const prev = placed[j];
        const cur = placed[i];
        if (Math.abs(cur.sx - prev.sx) < prev.hw + cur.hw && cur.sy - prev.sy < 26) {
          cur.sy = Math.min(h - 92, prev.sy + 26);
        }
      }
    }

    let svgMarkup = "";
    for (const p of placed) {
      const nid = p.item.part.userData.nodeId;
      const isSel = nid === this.selectedNodeId;
      const inLens = Boolean(this.lensDirectIds?.has(nid) || this.lensContainerIds?.has(nid));
      p.item.el.style.transform = `translate(${p.sx}px, ${p.sy}px) translate(-50%, -100%)`;
      p.item.el.style.opacity = "0.96";
      p.item.el.style.pointerEvents = "auto";
      p.item.el.classList.toggle("active", isSel);
      p.item.el.classList.toggle("lens-hit", inLens && !isSel);
      // Hairline leader from 3D part center to callout pill bottom
      const stroke = inLens ? "#7e22ce" : isSel ? "rgba(24,24,22,0.75)" : "rgba(24,24,22,0.22)";
      svgMarkup += `<line x1="${p.ax.toFixed(1)}" y1="${p.ay.toFixed(1)}" x2="${p.sx.toFixed(1)}" y2="${(p.sy - 2).toFixed(1)}" stroke="${stroke}" stroke-width="${(isSel || inLens) ? 1.35 : 0.9}" stroke-dasharray="${(isSel || inLens) ? "" : "2,2"}"/>`;
      svgMarkup += `<circle cx="${p.ax.toFixed(1)}" cy="${p.ay.toFixed(1)}" r="${(isSel || inLens) ? 3.5 : 2.0}" fill="${inLens ? "#7e22ce" : isSel ? "#181816" : "rgba(24,24,22,0.35)"}"/>`;
    }

    // Draw crisp architectural elbow tether from selected 3D part directly to the floating Anchor Card
    if (this.leaderSvg && this.anchorCardEl && this.anchorCardEl.style.display !== "none" && this.selectedNodeId) {
      const selPart = this.interactiveParts.find((p) => p.userData?.nodeId === this.selectedNodeId);
      if (selPart) {
        box.setFromObject(selPart);
        box.getCenter(anchor);
        anchor.project(this.camera);
        if (anchor.z < 1) {
          const ax = (anchor.x * 0.5 + 0.5) * w;
          const ay = (-anchor.y * 0.5 + 0.5) * h;
          const cRect = this.anchorCardEl.getBoundingClientRect();
          const wrapRect = this.container.getBoundingClientRect();
          const cx = cRect.left - wrapRect.left;
          const cy = cRect.top - wrapRect.top + Math.min(28, cRect.height / 2);
          const elbowX = ax + (cx - ax) * 0.55;
          svgMarkup += `<path d="M ${ax.toFixed(1)} ${ay.toFixed(1)} L ${elbowX.toFixed(1)} ${cy.toFixed(1)} L ${cx.toFixed(1)} ${cy.toFixed(1)}" fill="none" stroke="rgba(24,24,22,0.55)" stroke-width="1.25" stroke-linecap="round"/>`;
          svgMarkup += `<circle cx="${ax.toFixed(1)}" cy="${ay.toFixed(1)}" r="4.5" fill="#fff" stroke="#181816" stroke-width="1.75"/>`;
          svgMarkup += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="2.5" fill="#181816"/>`;
        }
      }
    }

    if (this.leaderSvg) {
      this.leaderSvg.setAttribute("viewBox", `0 0 ${w} ${h}`);
      this.leaderSvg.innerHTML = svgMarkup;
    }
  }

  _updateHighlights() {
    const lensActive = Boolean(this.lensDirectIds || this.lensContainerIds);
    this.rootGroup.traverse((obj) => {
      if (!obj.isMesh || !obj.material || !("emissive" in obj.material)) return;
      if (!obj.userData._origMat) {
        obj.userData._origMat = obj.material;
      }
      const nid = obj.userData.nodeId;
      const isSel = nid && nid === this.selectedNodeId;
      const isHov = this.hoveredMesh && nid === this.hoveredMesh.userData.nodeId;
      const isLensDirect = Boolean(nid && this.lensDirectIds?.has(nid));
      const isLensContainer = Boolean(nid && this.lensContainerIds?.has(nid));

      if (lensActive && !isLensDirect && !isLensContainer) {
        // Dim unrelated parts so the vendor's footprint pops cleanly
        if (!obj.userData._dimMat) {
          const dm = obj.userData._origMat.clone();
          dm.transparent = true;
          dm.opacity = Math.min(dm.opacity ?? 1, 0.16);
          dm.depthWrite = false;
          obj.userData._dimMat = dm;
        }
        obj.material = obj.userData._dimMat;
        return;
      }

      if (isLensDirect || isLensContainer || isSel || isHov) {
        if (!obj.userData._hlMat) {
          obj.userData._hlMat = obj.userData._origMat.clone();
        }
        if (isLensDirect) {
          obj.userData._hlMat.emissive.setHex(0x7e22ce);
          obj.userData._hlMat.emissiveIntensity = 0.36;
        } else if (isLensContainer) {
          obj.userData._hlMat.emissive.setHex(0x9333ea);
          obj.userData._hlMat.emissiveIntensity = 0.22;
        } else {
          obj.userData._hlMat.emissive.setHex(isSel ? 0x1d4ed8 : 0x3b82f6);
          obj.userData._hlMat.emissiveIntensity = isSel ? 0.26 : 0.14;
        }
        obj.material = obj.userData._hlMat;
      } else if (obj.userData._origMat) {
        obj.material = obj.userData._origMat;
      }
    });
  }

  _pick(clientX, clientY) {
    const rect = this.renderer.domElement.getBoundingClientRect();
    this.pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
    this.pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
    this.raycaster.setFromCamera(this.pointer, this.camera);
    const hits = this.raycaster.intersectObjects(this.rootGroup.children, true);
    for (const h of hits) {
      if (h.object.isMesh && h.object.userData?.nodeId) return h.object;
    }
    return null;
  }

  _bindEvents() {
    const dom = this.renderer.domElement;
    dom.addEventListener("pointerdown", (e) => {
      this.downPos = { x: e.clientX, y: e.clientY };
      this.tween = null;
    });
    dom.addEventListener("pointermove", (e) => {
      const hit = this._pick(e.clientX, e.clientY);
      if (hit !== this.hoveredMesh) {
        this.hoveredMesh = hit;
        dom.style.cursor = hit ? "pointer" : "grab";
        this._updateHighlights();
      }
      this.onHover?.(hit ? hit.userData.nodeId : null, e.clientX, e.clientY);
    });
    dom.addEventListener("pointerup", (e) => {
      const moved = Math.hypot(e.clientX - this.downPos.x, e.clientY - this.downPos.y);
      if (moved > 5) return;
      const hit = this._pick(e.clientX, e.clientY);
      if (hit) {
        this.onSelect?.(hit.userData.nodeId, hit.userData.drillLevel);
      }
    });
    dom.addEventListener("dblclick", (e) => {
      const hit = this._pick(e.clientX, e.clientY);
      if (hit?.userData?.drillLevel) {
        this.onDrill?.(hit.userData.drillLevel, hit.userData.nodeId);
      }
    });

    this._ro = new ResizeObserver(() => this.resize());
    this._ro.observe(this.container);
  }

  resize() {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  _loop() {
    this._raf = requestAnimationFrame(() => this._loop());
    if (Math.abs(this.explode - this.targetExplode) > 0.001) {
      this.explode += (this.targetExplode - this.explode) * 0.14;
      this._applyExplode(this.explode);
    }
    if (this.tween) {
      const t = Math.min(1, (performance.now() - this.tween.start) / this.tween.duration);
      const ease = 1 - Math.pow(1 - t, 3);
      this.camera.position.lerpVectors(this.tween.fromPos, this.tween.toPos, ease);
      this.controls.target.lerpVectors(this.tween.fromTarget, this.tween.toTarget, ease);
      if (t >= 1) this.tween = null;
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this._updateCallouts();
  }

  dispose() {
    cancelAnimationFrame(this._raf);
    this._ro?.disconnect();
    this.envRT?.dispose();
    this.controls?.dispose();
    this.renderer?.dispose();
    this.renderer?.domElement?.remove();
  }
}
