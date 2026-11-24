const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function fmtQty(q) {
  if (!q) return "";
  const unit = q.unit === "1" ? "" : ` ${q.unit}`;
  const val = q.value !== undefined ? `${q.value}` : `${q.min}–${q.max}`;
  return `${val}${unit}${q.basis ? ` (${q.basis})` : ""}`;
}

export function fmtFact(f) {
  if (!f) return "—";
  if (f.quantity) return fmtQty(f.quantity);
  if (f.state) return f.state;
  return String(f.value);
}

export function fmtQual(q) {
  if (!q) return "";
  return [q.role, q.position, q.sequence !== undefined ? `#${q.sequence}` : "", q.quantity ? fmtQty(q.quantity) : ""].filter(Boolean).join(" · ");
}

function renderGuideCard(node, entry) {
  if (!entry) return "";
  if (entry.firm) {
    const f = entry.firm;
    return `
      <div class="guide-card">
        <div class="guide-kicker">Company / Role Profile</div>
        <p class="guide-summary">${esc(entry.summary)}</p>
        <div class="guide-kv">
          <span class="meta-txt">segment</span><span>${esc(f.segment)}</span>
          ${f.founded ? `<span class="meta-txt">founded</span><span class="mono">${esc(f.founded)}</span>` : ""}
          ${f.headquarters ? `<span class="meta-txt">HQ</span><span>${esc(f.headquarters)}</span>` : ""}
          ${f.knownFor ? `<span class="meta-txt">known for</span><span>${esc(f.knownFor)}</span>` : ""}
        </div>
        ${f.website ? `<a class="guide-ext" href="${esc(f.website)}" target="_blank" rel="noopener">${esc(f.website.replace(/^https?:\/\//, ""))} ↗</a>` : ""}
      </div>`;
  }
  if (entry.chemistry) {
    const c = entry.chemistry;
    return `
      <div class="guide-card guide-chem">
        <div class="guide-kicker">Chemistry Card</div>
        <div class="chem-head">
          <span class="chem-formula">${esc(c.formula)}</span>
          ${c.atomicNumber ? `<span class="tag">Z = ${esc(c.atomicNumber)}</span>` : ""}
          ${c.molarMass ? `<span class="tag">${esc(c.molarMass)}</span>` : ""}
        </div>
        <p class="guide-summary">${esc(entry.summary)}</p>
        ${c.role ? `<p class="guide-sub"><strong>Role:</strong> ${esc(c.role)}</p>` : ""}
      </div>`;
  }
  return `
    <div class="guide-card">
      <div class="guide-kicker">About this ${esc(node.kind)}</div>
      <p class="guide-summary">${esc(entry.summary)}</p>
      ${entry.howItWorks ? `<p class="guide-sub"><strong>How it works:</strong> ${esc(entry.howItWorks)}</p>` : ""}
      ${entry.steps ? `<ol class="guide-steps">${entry.steps.map((s) => `<li>${esc(s)}</li>`).join("")}</ol>` : ""}
      ${entry.tradeoffs ? `<p class="guide-sub"><strong>Tradeoffs:</strong> ${esc(entry.tradeoffs)}</p>` : ""}
      ${entry.whyItMatters ? `<p class="guide-sub"><strong>Why it matters:</strong> ${esc(entry.whyItMatters)}</p>` : ""}
    </div>`;
}

export function renderInspectorPanel(el, {
  node,
  full,
  guide,
  gaps,
  selectedStatementId,
  citation,
  openPropHelp,
  drillLevel,
  canView3D,
  onSelectNode,
  onInspectStatement,
  onTogglePropHelp,
  onDrill,
  onView3D,
  onGraphMode,
}) {
  if (!node) {
    el.innerHTML = `<div class="empty">Click any 3D component, node, or edge to inspect its guide, facts, and PDF sources.</div>`;
    return;
  }

  const outAll = full.out.get(node.id) || [];
  const facts = outAll.filter((r) => "property" in r);
  const outgoing = outAll.filter((r) => "predicate" in r);
  const incoming = full.inc.get(node.id) || [];
  const nodeGaps = (gaps?.gaps || []).filter((g) => g.nodeId === node.id);
  const nodeGuide = guide?.nodes?.[node.id];

  const citeHtml = (() => {
    if (!selectedStatementId) return "";
    if (!citation) return `<div class="cite-card"><span class="empty">Loading citation…</span></div>`;
    if (citation.error) return `<div class="cite-card"><span class="empty">${esc(citation.error)}</span></div>`;
    return citation.evidence.map((ev) => `
      <div class="cite-card">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span class="mono" style="font-weight:600">${esc(citation.statement.id)}</span>
          <span class="tag ${ev.capture === "saved" ? "tag-teal" : "tag-amber"}">${esc(ev.capture)}</span>
        </div>
        <div style="font-weight:600;font-size:12.5px">${esc(ev.source.label)}</div>
        <div class="cite-kv">
          ${Object.entries(ev.locator || {}).map(([k, v]) => `<span class="meta-txt">${esc(k)}</span><span>${esc(v)}</span>`).join("")}
        </div>
        <a class="open-btn" href="${esc(ev.webHref || ev.href)}" target="_blank" rel="noopener">
          Open ${ev.capture === "saved" ? "archived PDF" : "source URL"} ↗
        </a>
      </div>`).join("");
  })();

  const linkRow = (r, dir) => {
    const otherId = dir === "out" ? r.target : r.subject;
    const other = full.byId.get(otherId);
    const qual = fmtQual(r.qualifiers);
    return `<div class="link-row">
      <div class="link-main">
        <div class="meta-txt">${dir === "out" ? "→" : "←"} ${esc(r.predicate)}${qual ? ` · ${esc(qual)}` : ""}</div>
        <button class="link-btn" data-jump="${esc(otherId)}">${esc(other?.label || otherId)}</button>
      </div>
      <button class="cite-link" data-cite="${esc(r.id)}">cite</button>
    </div>`;
  };

  el.innerHTML = `
    <div class="insp-head">
      <div style="display:flex;gap:5px;flex-wrap:wrap">
        <span class="tag">${esc(node.kind)}</span>
        ${node.stage ? `<span class="tag">${esc(node.stage)}</span>` : ""}
        ${node.scale ? `<span class="tag">${esc(node.scale)}</span>` : ""}
        ${nodeGaps.length ? `<span class="tag tag-amber">${nodeGaps.length} gap${nodeGaps.length > 1 ? "s" : ""}</span>` : ""}
      </div>
      <h2 class="insp-title">${esc(node.label)}</h2>
      <div class="meta-txt">${esc(node.id)}</div>
      <div class="insp-actions">
        ${drillLevel ? `<button class="btn-primary-sm" id="btnDrillIn">Drill In →</button>` : ""}
        ${canView3D ? `<button class="btn-sm" id="btnView3D">View in 3D</button>` : ""}
        <button class="btn-sm" data-root="parts">Parts</button>
        <button class="btn-sm" data-root="trace">Trace</button>
        <button class="btn-sm" data-root="used-by">Used By</button>
      </div>
    </div>
    ${citeHtml}
    ${renderGuideCard(node, nodeGuide)}
    ${facts.length ? `<div>
      <div class="insp-section-title"><span>Verified Facts</span><span>${facts.length}</span></div>
      ${facts.map((f) => {
        const pg = guide?.properties?.[f.property];
        const isOpen = openPropHelp.has(f.property);
        return `<div class="fact-row">
          <div class="fact-line">
            <span style="display:inline-flex;align-items:center;gap:5px">
              <span class="mono">${esc(f.property)}</span>
              ${pg ? `<button class="help-dot ${isOpen ? "open" : ""}" data-prop-help="${esc(f.property)}" title="Explain ${esc(pg.title)}">?</button>` : ""}
            </span>
            <span class="fact-val ${f.state ? "unknown" : ""}">${esc(fmtFact(f))}</span>
          </div>
          <div class="fact-line">
            <span class="meta-txt">${esc([f.basis, f.scope, f.method].filter(Boolean).join(" · "))}</span>
            <button class="cite-link" data-cite="${esc(f.id)}">cite</button>
          </div>
          ${f.conditions ? `<div style="font-size:11.5px;color:var(--muted)">${esc(f.conditions)}</div>` : ""}
          ${pg && isOpen ? `<div class="prop-explainer">
            <div style="font-weight:600;margin-bottom:2px">${esc(pg.title)}</div>
            <div>${esc(pg.summary)}</div>
            ${pg.betterDirection ? `<div style="margin-top:3px"><strong>Direction:</strong> ${esc(pg.betterDirection)}</div>` : ""}
            ${pg.typicalRange ? `<div style="margin-top:2px"><strong>Typical:</strong> ${esc(pg.typicalRange)}</div>` : ""}
          </div>` : ""}
        </div>`;
      }).join("")}
    </div>` : ""}
    <div>
      <div class="insp-section-title"><span>Outgoing</span><span>${outgoing.length}</span></div>
      ${outgoing.length ? outgoing.map((r) => linkRow(r, "out")).join("") : `<div class="empty">None</div>`}
    </div>
    <div>
      <div class="insp-section-title"><span>Incoming</span><span>${incoming.length}</span></div>
      ${incoming.length ? incoming.map((r) => linkRow(r, "in")).join("") : `<div class="empty">None</div>`}
    </div>
  `;

  if ($("btnDrillIn")) $("btnDrillIn").onclick = () => onDrill?.(drillLevel, node.id);
  if ($("btnView3D")) $("btnView3D").onclick = () => onView3D?.(node.id);
  el.querySelectorAll("[data-root]").forEach((b) => b.onclick = () => onGraphMode?.(b.dataset.root, node.id));
  el.querySelectorAll("[data-jump]").forEach((b) => b.onclick = () => onSelectNode?.(b.dataset.jump));
  el.querySelectorAll("[data-cite]").forEach((b) => b.onclick = () => {
    const st = full.statements.find((s) => s.id === b.dataset.cite);
    if (st) onInspectStatement?.(st);
  });
  el.querySelectorAll("[data-prop-help]").forEach((b) => b.onclick = () => onTogglePropHelp?.(b.dataset.propHelp));
}

export function renderAnchoredCard(el, {
  node,
  full,
  guide,
  openPropHelp,
  drillLevel,
  firmNode,
  activeTab = "overview",
  selectedStatementId = null,
  citation = null,
  onSelectTab,
  onSelectNode,
  onSelectFirm,
  onInspectStatement,
  onTogglePropHelp,
  onDrill,
  onOpenInGraph,
  onClose,
}) {
  if (!el) return;
  if (!node) {
    el.style.display = "none";
    return;
  }
  el.style.display = "flex";

  const outAll = full.out.get(node.id) || [];
  const facts = outAll.filter((r) => "property" in r);
  const outgoing = outAll.filter((r) => "predicate" in r);
  const incoming = full.inc.get(node.id) || [];
  const linksCount = outgoing.length + incoming.length;
  const entry = guide?.nodes?.[node.id];

  // Collect unique evidence statements on this node (facts + outgoing)
  const citedStmts = outAll.filter((r) => r.evidence && r.evidence.length);

  let bodyHtml = "";
  if (activeTab === "overview") {
    let summaryHtml = "";
    if (entry?.chemistry) {
      const c = entry.chemistry;
      summaryHtml = `
        <div class="chem-head" style="margin-top:2px">
          <span class="chem-formula">${esc(c.formula)}</span>
          ${c.atomicNumber ? `<span class="tag">Z = ${esc(c.atomicNumber)}</span>` : ""}
          ${c.molarMass ? `<span class="tag">${esc(c.molarMass)}</span>` : ""}
        </div>
        <p class="anchor-summary">${esc(entry.summary)}</p>
        ${c.role ? `<p class="anchor-summary"><strong>Role:</strong> ${esc(c.role)}</p>` : ""}`;
    } else if (entry?.firm) {
      const f = entry.firm;
      summaryHtml = `<p class="anchor-summary">${esc(entry.summary)}</p>
        <div class="guide-kv">
          <span class="meta-txt">segment</span><span>${esc(f.segment)}</span>
          ${f.founded ? `<span class="meta-txt">founded</span><span class="mono">${esc(f.founded)}</span>` : ""}
          ${f.headquarters ? `<span class="meta-txt">HQ</span><span>${esc(f.headquarters)}</span>` : ""}
          ${f.knownFor ? `<span class="meta-txt">known for</span><span>${esc(f.knownFor)}</span>` : ""}
        </div>
        ${f.website ? `<a class="guide-ext" href="${esc(f.website)}" target="_blank" rel="noopener">${esc(f.website.replace(/^https?:\/\//, ""))} ↗</a>` : ""}`;
    } else if (entry?.summary) {
      summaryHtml = `<p class="anchor-summary">${esc(entry.summary)}</p>
        ${entry.howItWorks ? `<p class="anchor-summary"><strong>How it works:</strong> ${esc(entry.howItWorks)}</p>` : ""}
        ${entry.tradeoffs ? `<p class="anchor-summary"><strong>Tradeoffs:</strong> ${esc(entry.tradeoffs)}</p>` : ""}`;
    }

    bodyHtml = `
      ${summaryHtml}
      ${facts.length ? `<div class="anchor-facts">
        ${facts.map((f) => {
          const pg = guide?.properties?.[f.property];
          const isOpen = openPropHelp.has(f.property);
          return `<div class="anchor-fact">
            <div class="fact-line">
              <span style="display:inline-flex;align-items:center;gap:4px">
                <span class="mono">${esc(f.property)}</span>
                ${pg ? `<button class="help-dot ${isOpen ? "open" : ""}" data-prop-help="${esc(f.property)}" title="Explain ${esc(pg.title)}">?</button>` : ""}
              </span>
              <span style="display:inline-flex;align-items:center;gap:6px">
                <span class="fact-val ${f.state ? "unknown" : ""}">${esc(fmtFact(f))}</span>
                <button class="cite-link" data-cite="${esc(f.id)}">cite</button>
              </span>
            </div>
            ${pg && isOpen ? `<div class="prop-explainer">
              <strong>${esc(pg.title)}:</strong> ${esc(pg.summary)}
              ${pg.betterDirection ? `<div style="margin-top:2px"><em>${esc(pg.betterDirection)}</em></div>` : ""}
            </div>` : ""}
          </div>`;
        }).join("")}
      </div>` : ""}
    `;
  } else if (activeTab === "sources") {
    const citeCard = (() => {
      if (!selectedStatementId) return "";
      if (!citation) return `<div class="cite-card"><span class="empty">Loading citation…</span></div>`;
      if (citation.error) return `<div class="cite-card"><span class="empty">${esc(citation.error)}</span></div>`;
      return citation.evidence.map((ev) => `
        <div class="cite-card">
          <div style="display:flex;justify-content:space-between;align-items:center">
            <span class="mono" style="font-weight:600">${esc(citation.statement.id)}</span>
            <span class="tag ${ev.capture === "saved" ? "tag-teal" : "tag-amber"}">${esc(ev.capture)}</span>
          </div>
          <div style="font-weight:600;font-size:12px">${esc(ev.source.label)}</div>
          <div class="cite-kv">
            ${Object.entries(ev.locator || {}).map(([k, v]) => `<span class="meta-txt">${esc(k)}</span><span>${esc(v)}</span>`).join("")}
          </div>
          <a class="open-btn" href="${esc(ev.webHref || ev.href)}" target="_blank" rel="noopener">
            Open ${ev.capture === "saved" ? "archived PDF" : "source URL"} ↗
          </a>
        </div>`).join("");
    })();

    bodyHtml = `
      ${citeCard}
      ${citedStmts.length ? `<div class="anchor-list">
        ${citedStmts.map((st) => `
          <button class="anchor-list-row ${st.id === selectedStatementId ? "active" : ""}" data-cite="${esc(st.id)}">
            <span class="mono" style="font-size:11px">${esc(st.property || st.predicate)}</span>
            <span class="meta-txt">${esc(st.target || fmtFact(st))}</span>
          </button>`).join("")}
      </div>` : `<div class="empty">No direct citations on this node.</div>`}
    `;
  } else if (activeTab === "links") {
    const linkRow = (r, dir) => {
      const otherId = dir === "out" ? r.target : r.subject;
      const other = full.byId.get(otherId);
      return `<div class="link-row">
        <div class="link-main">
          <div class="meta-txt">${dir === "out" ? "→" : "←"} ${esc(r.predicate)}</div>
          <button class="link-btn" data-jump="${esc(otherId)}">${esc(other?.label || otherId)}</button>
        </div>
        <button class="cite-link" data-cite="${esc(r.id)}">cite</button>
      </div>`;
    };
    bodyHtml = `
      <div class="anchor-links">
        ${outgoing.map((r) => linkRow(r, "out")).join("")}
        ${incoming.map((r) => linkRow(r, "in")).join("")}
        ${!linksCount ? `<div class="empty">No graph links.</div>` : ""}
      </div>
      <div style="padding-top:6px">
        <button class="btn-sm" id="anchorGraphTabBtn" style="width:100%">Explore in Full Graph Tab →</button>
      </div>
    `;
  }

  el.innerHTML = `
    <div class="anchor-head">
      <div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap">
        <span class="tag">${esc(node.kind)}</span>
        ${firmNode ? `<button class="brand-chip" id="anchorFirmBtn" title="Inspect manufacturer">${esc(firmNode.label)} ↗</button>` : ""}
      </div>
      <button class="anchor-close" id="anchorCloseBtn" title="Hide card">×</button>
    </div>
    <div class="anchor-title">${esc(node.label)}</div>
    <div class="anchor-tabs">
      <button class="anchor-tab ${activeTab === "overview" ? "active" : ""}" data-atab="overview">Overview</button>
      <button class="anchor-tab ${activeTab === "sources" ? "active" : ""}" data-atab="sources">Sources (${citedStmts.length})</button>
      <button class="anchor-tab ${activeTab === "links" ? "active" : ""}" data-atab="links">Links (${linksCount})</button>
    </div>
    <div class="anchor-body">${bodyHtml}</div>
    ${drillLevel ? `<div class="anchor-foot">
      <button class="btn-primary-sm" id="anchorDrillBtn" style="width:100%">Drill Into Next Layer →</button>
    </div>` : ""}
  `;

  if ($("anchorCloseBtn")) $("anchorCloseBtn").onclick = () => onClose?.();
  if ($("anchorDrillBtn")) $("anchorDrillBtn").onclick = () => onDrill?.(drillLevel, node.id);
  if ($("anchorFirmBtn") && firmNode) $("anchorFirmBtn").onclick = () => onSelectFirm?.(firmNode.id);
  if ($("anchorGraphTabBtn")) $("anchorGraphTabBtn").onclick = () => onOpenInGraph?.(node.id);
  el.querySelectorAll("[data-atab]").forEach((b) => b.onclick = () => onSelectTab?.(b.dataset.atab));
  el.querySelectorAll("[data-jump]").forEach((b) => b.onclick = () => onSelectNode?.(b.dataset.jump));
  el.querySelectorAll("[data-prop-help]").forEach((b) => b.onclick = () => onTogglePropHelp?.(b.dataset.propHelp));
  el.querySelectorAll("[data-cite]").forEach((b) => b.onclick = () => {
    const st = full.statements.find((s) => s.id === b.dataset.cite);
    if (st) onInspectStatement?.(st);
  });
}

function $(id) { return document.getElementById(id); }
