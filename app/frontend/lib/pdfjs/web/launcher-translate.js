// Floating translation pill, cursor tool toggle, search match navigation, scale-lock,
// and AutoCAD-style word-level rectangular zone selection with dual-mode support for Mozilla PDF.js
(function() {
  let tooltip = null;
  let popover = null;
  let cadCard = null;
  let zoneBox = null;
  let lastExportedCadPath = "";
  let viewerToolMode = 0; // 0: AutoCAD Zone (Рамка), 1: Hand (Лапа), 2: Linear Text (Текст)
  let isMouseDown = false;
  let isDragging = false;
  let zoneStart = { clientX: 0, clientY: 0, target: null };
  let zoneSelectedText = "";
  let currentZoneSpans = [];
  let activeSelectionSnapshot = "";
  let selectionMenu = null;

  function clearZoneSelection() {
    const hadSelection = Boolean(zoneSelectedText || (zoneBox && zoneBox.style.display !== "none") || currentZoneSpans.length > 0);
    if (zoneBox) {
      zoneBox.style.display = "none";
      zoneBox.style.width = "0px";
      zoneBox.style.height = "0px";
    }
    document.querySelectorAll(".textLayer :is(span, .launcher-word).zone-selected").forEach((el) => {
      el.classList.remove("zone-selected");
    });
    currentZoneSpans = [];
    zoneSelectedText = "";
    activeSelectionSnapshot = "";
    if (selectionMenu) selectionMenu.style.display = "none";
    return hadSelection;
  }

  // Tokenize compound multi-word spans into individual word elements.
  // In complex PDF catalogs (e.g. Reynaers, Schuco, architectural schedules), multiple columns
  // or table cells are frequently emitted in the PDF content stream as a single wide text chunk.
  // Breaking them down into individual word elements gives each word its own independent 2D bounding box,
  // preventing rectangular selections from bleeding across columns.
  function tokenizeTextLayerWords(layerDiv) {
    if (!layerDiv || layerDiv.dataset.launcherTokenized) return;

    const spans = Array.from(layerDiv.querySelectorAll("span:not(.markedContent):not(.endOfContent)"));
    for (let i = 0; i < spans.length; i++) {
      const span = spans[i];
      if (span.children.length > 0 || span.classList.contains("launcher-word")) continue;

      const text = span.textContent;
      if (!text || !text.includes(" ")) continue;

      const tokens = text.split(/(\s+)/);
      if (tokens.length <= 1) continue;

      const frag = document.createDocumentFragment();
      for (let t = 0; t < tokens.length; t++) {
        const token = tokens[t];
        if (!token) continue;
        if (/^\s+$/.test(token)) {
          frag.appendChild(document.createTextNode(token));
        } else {
          const wSpan = document.createElement("span");
          wSpan.className = "launcher-word";
          wSpan.textContent = token;
          frag.appendChild(wSpan);
        }
      }
      span.textContent = "";
      span.appendChild(frag);
    }

    layerDiv.dataset.launcherTokenized = "true";
  }

  function extractZoneText() {
    if (!currentZoneSpans || currentZoneSpans.length === 0) {
      zoneSelectedText = "";
      return;
    }

    // Sort tokens: top (with 7px line tolerance), then left
    const sorted = currentZoneSpans.slice().sort((a, b) => {
      const rA = a.getBoundingClientRect();
      const rB = b.getBoundingClientRect();
      const diffY = rA.top - rB.top;
      if (Math.abs(diffY) > 7) return diffY;
      return rA.left - rB.left;
    });

    const lines = [];
    let curLine = [];
    let curTop = null;

    for (let i = 0; i < sorted.length; i++) {
      const el = sorted[i];
      const r = el.getBoundingClientRect();
      const txt = (el.textContent || "").trim();
      if (!txt) continue;

      if (curTop === null || Math.abs(r.top - curTop) < 8) {
        curLine.push(txt);
        if (curTop === null) curTop = r.top;
      } else {
        lines.push(curLine.join(" "));
        curLine = [txt];
        curTop = r.top;
      }
    }

    if (curLine.length > 0) {
      lines.push(curLine.join(" "));
    }

    zoneSelectedText = lines.filter(Boolean).join("\n");
  }

  function getCurrentPdfPath() {
    try {
      if (window.frameElement && window.frameElement.dataset && window.frameElement.dataset.currentDoc) {
        return window.frameElement.dataset.currentDoc;
      }
    } catch (_) {}
    try {
      if (window.parent && window.parent.state && window.parent.state.view && window.parent.state.view.activeDocPath) {
        return window.parent.state.view.activeDocPath;
      }
    } catch (_) {}
    try {
      const fileParam = new URLSearchParams(window.location.search).get("file");
      if (fileParam) {
        const match = fileParam.match(/path=([^&]+)/);
        if (match && match[1]) {
          return decodeURIComponent(match[1]);
        }
      }
    } catch (_) {}
    return "";
  }

  const updateSelectionTooltip = () => {
    if (viewerToolMode === 0 && zoneBox && zoneBox.style.display !== "none") {
      const rect = zoneBox.getBoundingClientRect();
      tooltip.style.top = Math.max(10, rect.top - 44) + "px";
      tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 85) + "px";
      tooltip.style.display = "flex";
      return;
    }

    const sel = window.getSelection();
    const txt = sel ? sel.toString().trim() : "";
    if (!txt) {
      if (tooltip) tooltip.style.display = "none";
      return;
    }
    zoneSelectedText = txt;
    try {
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      if (rect && rect.width > 0 && rect.height > 0) {
        tooltip.style.top = Math.max(10, rect.top - 44) + "px";
        tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 85) + "px";
        tooltip.style.display = "flex";
      }
    } catch (_) {}
  };

  function initUI() {
    if (tooltip) return;

    // Inject high-contrast match styling, AutoCAD selection styling, and cursors
    const style = document.createElement("style");
    style.id = "launcherEnhancedStyles";
    style.textContent = `
      /* Prominent back button in PDF viewer toolbar */
      #toolbarBackBtn {
        min-width: 74px !important;
        width: auto !important;
        padding: 0 8px !important;
        margin-right: 6px !important;
        background: #f1f5f9 !important;
        border: 1px solid #94a3b8 !important;
        border-radius: 3px !important;
        color: #0f172a !important;
        cursor: pointer !important;
      }
      #toolbarBackBtn > span {
        display: inline-block !important;
        text-indent: 0 !important;
        font-size: 12px !important;
        font-weight: 700 !important;
        color: #0f172a !important;
      }
      #toolbarBackBtn:hover {
        background: #0969da !important;
        border-color: #0969da !important;
        color: #ffffff !important;
      }
      #toolbarBackBtn:hover > span {
        color: #ffffff !important;
      }

      /* 1. TextLayer display */
      .textLayer {
        opacity: 1 !important;
      }
      .textLayer :is(span:not(.highlight), br, .launcher-word) {
        color: transparent !important;
      }

      /* Critical fix: word tokens must be inline and static to flow naturally inside parent span */
      .textLayer .launcher-word {
        position: static !important;
        display: inline !important;
        color: transparent !important;
        white-space: pre !important;
        transform: none !important;
        cursor: inherit !important;
      }

      /* Prevent markedContent and endOfContent from disrupting selection */
      .textLayer span.markedContent,
      .textLayer .endOfContent {
        display: none !important;
        pointer-events: none !important;
        user-select: none !important;
      }

      /* Mode 0: AutoCAD Zone Mode (crosshair, no native selection) */
      body:not(.text-mode-active):not(.hand-mode-active) .textLayer,
      body.zone-mode-active .textLayer {
        user-select: none !important;
        -webkit-user-select: none !important;
      }
      body:not(.text-mode-active):not(.hand-mode-active) .textLayer :is(span, .launcher-word),
      body.zone-mode-active .textLayer :is(span, .launcher-word) {
        user-select: none !important;
        -webkit-user-select: none !important;
        cursor: crosshair !important;
      }

      /* Mode 2: Linear Text Mode (I-beam cursor, native selection) */
      body.text-mode-active .textLayer {
        user-select: text !important;
        -webkit-user-select: text !important;
      }
      body.text-mode-active .textLayer :is(span, .launcher-word) {
        user-select: text !important;
        -webkit-user-select: text !important;
        cursor: text !important;
      }
      body.text-mode-active .textLayer ::selection {
        background: rgba(0, 102, 255, 0.35) !important;
        color: transparent !important;
      }

      /* Mode 1: Hand Mode */
      body.hand-mode-active #viewerContainer,
      body.hand-mode-active .page,
      body.hand-mode-active .textLayer,
      body.hand-mode-active :is(span, .launcher-word) {
        cursor: grab !important;
      }

      /* AutoCAD rectangular zone selection styling with word-level precision */
      #launcherZoneBox {
        position: absolute;
        pointer-events: none;
        border: 1.5px solid #0969da;
        background-color: rgba(9, 105, 218, 0.14);
        z-index: 999999;
        border-radius: 2px;
        display: none;
      }
      .textLayer :is(span, .launcher-word).zone-selected {
        background-color: rgba(0, 102, 255, 0.35) !important;
        outline: 1px solid rgba(0, 102, 255, 0.6) !important;
        border-radius: 2px !important;
        color: transparent !important;
      }

      /* 3. All search matches: bright sunshine yellow with contrast border */
      .textLayer .highlight {
        background-color: #ffe600 !important;
        color: #000000 !important;
        opacity: 0.85 !important;
        border-radius: 3px !important;
        box-shadow: 0 0 0 1px #d97706, 0 1px 3px rgba(0, 0, 0, 0.25) !important;
        cursor: pointer !important;
      }

      /* 4. Active / Selected match: glowing electric safety orange with white outline and pulse */
      .textLayer .highlight.selected {
        background-color: #ff5722 !important;
        color: #ffffff !important;
        opacity: 0.98 !important;
        border-radius: 4px !important;
        outline: 2px solid #ffffff !important;
        box-shadow: 0 0 0 3px #bf360c, 0 0 16px rgba(255, 87, 34, 0.9) !important;
        z-index: 100 !important;
        animation: launcherMatchPulse 1.2s ease-in-out infinite alternate !important;
      }

      @keyframes launcherMatchPulse {
        0% {
          box-shadow: 0 0 0 2px #d84315, 0 0 8px rgba(255, 87, 34, 0.7);
          transform: scale(1);
        }
        100% {
          box-shadow: 0 0 0 4px #bf360c, 0 0 18px rgba(255, 109, 0, 1);
          transform: scale(1.06);
        }
      }
    `;
    document.head.appendChild(style);

    // Toolbar Back Button
    const backBtn = document.getElementById("toolbarBackBtn");
    if (backBtn) {
      backBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        try {
          if (window.parent && typeof window.parent.exitWindow3 === "function") {
            window.parent.exitWindow3();
          }
        } catch (_) {}
      };
    }

    // Floating Action Pill (Translate + CAD Export)
    tooltip = document.createElement("div");
    tooltip.id = "launcherActionPill";
    tooltip.style.cssText = `
      position: fixed;
      display: none;
      z-index: 9999999;
      background: rgba(15, 23, 42, 0.94);
      backdrop-filter: blur(10px);
      border: 1px solid rgba(255, 255, 255, 0.18);
      border-radius: 8px;
      padding: 4px 6px;
      gap: 6px;
      box-shadow: 0 6px 20px rgba(0,0,0,0.35);
      align-items: center;
    `;
    tooltip.innerHTML = `
      <button id="launcherPillTransBtn" style="background:#0969da; color:#fff; border:none; border-radius:5px; padding:6px 11px; font-size:12px; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:4px;">🌐 Перевести</button>
      <button id="launcherPillCadBtn" style="background:#10b981; color:#fff; border:none; border-radius:5px; padding:6px 11px; font-size:12px; font-weight:600; cursor:pointer; display:flex; align-items:center; gap:4px;">📐 В DWG</button>
    `;
    document.body.appendChild(tooltip);

    const btnTrans = tooltip.querySelector("#launcherPillTransBtn");
    const btnCad = tooltip.querySelector("#launcherPillCadBtn");

    if (btnTrans) {
      btnTrans.onmouseover = () => btnTrans.style.background = "#0055b3";
      btnTrans.onmouseout = () => btnTrans.style.background = "#0969da";
    }
    if (btnCad) {
      btnCad.onmouseover = () => btnCad.style.background = "#059669";
      btnCad.onmouseout = () => btnCad.style.background = "#10b981";
    }

    // CAD Export Result Card
    cadCard = document.createElement("div");
    cadCard.id = "launcherCadCard";
    cadCard.style.cssText = `
      position: fixed;
      display: none;
      z-index: 10000000;
      bottom: 24px;
      right: 24px;
      width: 360px;
      background: rgba(255, 255, 255, 0.98);
      backdrop-filter: blur(12px);
      border: 1px solid #10b981;
      border-radius: 10px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.25);
      padding: 12px 14px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    `;
    cadCard.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e5e7eb; padding-bottom:6px; font-size:12px; font-weight:700; color:#1f2328;">
        <span>📐 Чертеж DWG/DXF сформирован</span>
        <button id="launcherCadCardClose" style="border:none; background:transparent; cursor:pointer; font-size:13px; color:#6b7280; padding:2px 4px;">✕</button>
      </div>
      <div style="margin-top:8px;">
        <div id="launcherCadFileName" style="font-size:13px; font-weight:700; color:#0f172a; word-break:break-all; background:#f8fafc; padding:6px 8px; border-radius:6px; border:1px solid #e2e8f0;"></div>
        <div id="launcherCadStats" style="font-size:12px; font-weight:600; color:#10b981; margin-top:6px;"></div>
        <div id="launcherCadLayers" style="font-size:11px; color:#64748b; margin-top:3px; word-break:break-word;"></div>
      </div>
      <div style="display:flex; justify-content:flex-end; gap:6px; margin-top:12px;">
        <button id="launcherCadOpenFolder" style="background:#f1f5f9; color:#0f172a; border:1px solid #cbd5e1; border-radius:6px; font-size:12px; font-weight:600; padding:5px 10px; cursor:pointer;">📁 Папка</button>
        <button id="launcherCadOpenCad" style="background:#10b981; color:#fff; border:none; border-radius:6px; font-size:12px; font-weight:600; padding:5px 14px; cursor:pointer;">🚀 Открыть в AutoCAD</button>
      </div>
    `;
    document.body.appendChild(cadCard);

    const cadCloseBtn = cadCard.querySelector("#launcherCadCardClose");
    if (cadCloseBtn) {
      cadCloseBtn.onclick = () => { cadCard.style.display = "none"; };
    }
    const cadOpenBtn = cadCard.querySelector("#launcherCadOpenCad");
    if (cadOpenBtn) {
      cadOpenBtn.onclick = () => {
        if (!lastExportedCadPath) return;
        fetch("/api/cad/open", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: lastExportedCadPath })
        });
      };
    }
    const cadFolderBtn = cadCard.querySelector("#launcherCadOpenFolder");
    if (cadFolderBtn) {
      cadFolderBtn.onclick = () => {
        if (!lastExportedCadPath) return;
        fetch("/api/cad/show-folder", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: lastExportedCadPath })
        });
      };
    }

    // Rectangular Zone Box
    zoneBox = document.createElement("div");
    zoneBox.id = "launcherZoneBox";
    document.body.appendChild(zoneBox);

    // Translation Popover Card
    popover = document.createElement("div");
    popover.id = "launcherTransCard";
    popover.style.cssText = `
      position: fixed;
      display: none;
      z-index: 10000000;
      bottom: 24px;
      right: 24px;
      width: 330px;
      background: rgba(255, 255, 255, 0.98);
      backdrop-filter: blur(12px);
      border: 1px solid #0091ff;
      border-radius: 10px;
      box-shadow: 0 12px 32px rgba(0,0,0,0.22);
      padding: 12px 14px;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    `;
    popover.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #e5e7eb; padding-bottom:6px; font-size:12px; font-weight:700; color:#1f2328;">
        <span>🌐 Инженерный перевод</span>
        <button id="launcherTransCardClose" style="border:none; background:transparent; cursor:pointer; font-size:13px; color:#6b7280; padding:2px 4px;">✕</button>
      </div>
      <div style="margin-top:8px;">
        <div id="launcherTransOrig" style="font-size:13px; color:#4b5563; word-break:break-word; white-space:pre-wrap; background:#f9fafb; padding:6px 8px; border-radius:6px; border:1px solid #e5e7eb; max-height:110px; overflow-y:auto;"></div>
        <div style="text-align:center; color:#9ca3af; font-size:12px; margin:4px 0;">↓</div>
        <div id="launcherTransRes" style="font-size:14px; font-weight:600; color:#0969da; word-break:break-word; white-space:pre-wrap; line-height:1.45; background:#eff6ff; padding:8px 10px; border-radius:6px; border-left:3px solid #0091ff; max-height:130px; overflow-y:auto;"></div>
      </div>
      <div style="display:flex; justify-content:flex-end; gap:6px; margin-top:8px;">
        <button id="launcherTransCopy" style="background:#0969da; color:#fff; border:none; border-radius:6px; font-size:12px; font-weight:600; padding:4px 12px; cursor:pointer;">Скопировать</button>
      </div>
    `;
    document.body.appendChild(popover);

    document.getElementById("launcherTransCardClose").onclick = () => {
      popover.style.display = "none";
    };

    document.getElementById("launcherTransCopy").onclick = () => {
      const text = document.getElementById("launcherTransRes").textContent;
      if (text) {
        navigator.clipboard.writeText(text);
        const btn = document.getElementById("launcherTransCopy");
        btn.textContent = "Скопировано!";
        setTimeout(() => btn.textContent = "Скопировать", 1500);
      }
    };

    // Selection Handlers (Mode 0: AutoCAD Zone, Mode 2: Text I-beam)
    document.addEventListener("mousedown", (e) => {
      // Don't intercept toolbar controls, findbar, or popovers
      const interactive = e.target.closest("button, input, select, textarea, #toolbarViewer, #findbar, #launcherActionPill, #launcherSelectionContextMenu, #launcherTransPill, #launcherTransCard, #launcherCadCard");
      if (interactive) return;

      // Right-click or middle-click: do NOT hide the floating action pill or alter selection
      if (e.button !== 0) {
        return;
      }

      // Hide translation tooltip if clicking elsewhere with primary left click
      if (tooltip && e.target !== tooltip && !tooltip.contains(e.target)) {
        tooltip.style.display = "none";
      }

      // If in Hand mode (mode === 1) or Text mode (mode === 2): don't draw rectangular box
      if (viewerToolMode === 1 || viewerToolMode === 2) {
        isMouseDown = true;
        return;
      }

      // Zone mode (mode === 0): AutoCAD-style rectangular zone selection
      clearZoneSelection();
      window.getSelection()?.removeAllRanges();

      isMouseDown = true;
      isDragging = false;
      zoneStart = {
        clientX: e.clientX,
        clientY: e.clientY,
        target: e.target
      };

      // Halt native 1D browser text selection across columns
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!isMouseDown) return;
      if (viewerToolMode === 1 || viewerToolMode === 2) return;

      const dx = e.clientX - zoneStart.clientX;
      const dy = e.clientY - zoneStart.clientY;
      const dist = Math.hypot(dx, dy);

      if (!isDragging) {
        if (dist < 4) return;
        isDragging = true;

        if (!zoneBox) {
          zoneBox = document.createElement("div");
          zoneBox.id = "launcherZoneBox";
          document.body.appendChild(zoneBox);
        }
        zoneBox.style.position = "fixed";
        document.body.appendChild(zoneBox);
        zoneBox.style.display = "block";

        // Ensure visible text layers have word tokens ready
        document.querySelectorAll(".textLayer").forEach(tokenizeTextLayerWords);
      }

      const boxLeft = Math.min(zoneStart.clientX, e.clientX);
      const boxTop = Math.min(zoneStart.clientY, e.clientY);
      const boxWidth = Math.abs(dx);
      const boxHeight = Math.abs(dy);

      zoneBox.style.left = boxLeft + "px";
      zoneBox.style.top = boxTop + "px";
      zoneBox.style.width = boxWidth + "px";
      zoneBox.style.height = boxHeight + "px";

      const boxRect = {
        left: boxLeft,
        top: boxTop,
        right: boxLeft + boxWidth,
        bottom: boxTop + boxHeight
      };

      // Word-level precision check with 5px vertical tolerance and 2px horizontal tolerance
      const matchedTokens = [];
      const allTokens = document.querySelectorAll(
        ".textLayer .launcher-word, .textLayer span:not(.markedContent):not(.endOfContent):not(:has(.launcher-word))"
      );

      for (let i = 0; i < allTokens.length; i++) {
        const tokenEl = allTokens[i];
        const r = tokenEl.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;

        const intersects = !(
          r.right < boxRect.left - 2 ||
          r.left > boxRect.right + 2 ||
          r.bottom < boxRect.top - 5 ||
          r.top > boxRect.bottom + 5
        );

        if (intersects) {
          tokenEl.classList.add("zone-selected");
          matchedTokens.push(tokenEl);
        } else {
          tokenEl.classList.remove("zone-selected");
        }
      }
      currentZoneSpans = matchedTokens;

      e.preventDefault();
    });

    document.addEventListener("mouseup", (e) => {
      if (!isMouseDown) return;
      isMouseDown = false;

      // In Text mode (mode === 2): show tooltip over native selection
      if (viewerToolMode === 2) {
        setTimeout(updateSelectionTooltip, 30);
        return;
      }

      if (viewerToolMode === 1) return;

      if (!isDragging) {
        clearZoneSelection();
        return;
      }

      isDragging = false;

      const boxWidth = zoneBox ? parseInt(zoneBox.style.width, 10) || 0 : 0;
      const boxHeight = zoneBox ? parseInt(zoneBox.style.height, 10) || 0 : 0;

      if (boxWidth < 8 && boxHeight < 8) {
        clearZoneSelection();
        return;
      }

      // Anchor zoneBox to the active page so it scrolls seamlessly with the sheet
      const pageEl = (zoneStart.target && zoneStart.target.closest(".page")) ||
                     document.elementFromPoint(zoneStart.clientX, zoneStart.clientY)?.closest(".page") ||
                     document.elementFromPoint(e.clientX, e.clientY)?.closest(".page");
      if (pageEl && zoneBox) {
        const pageRect = pageEl.getBoundingClientRect();
        const boxLeft = Math.min(zoneStart.clientX, e.clientX);
        const boxTop = Math.min(zoneStart.clientY, e.clientY);

        zoneBox.style.position = "absolute";
        zoneBox.style.left = (boxLeft - pageRect.left) + "px";
        zoneBox.style.top = (boxTop - pageRect.top) + "px";
        zoneBox.style.width = boxWidth + "px";
        zoneBox.style.height = boxHeight + "px";
        pageEl.appendChild(zoneBox);
      }

      // Extract text strictly from inside the drawn rectangle
      extractZoneText();

      // Show floating action pill right above the rectangle
      if (tooltip && zoneBox) {
        const boxRect = zoneBox.getBoundingClientRect();
        tooltip.style.top = Math.max(10, boxRect.top - 44) + "px";
        tooltip.style.left = Math.max(10, boxRect.left + boxRect.width / 2 - 85) + "px";
        tooltip.style.display = "flex";
      }
    });

    // Double-click to select a single word/span
    document.addEventListener("dblclick", (e) => {
      if (viewerToolMode === 1) return;
      const target = e.target;
      if (target && (target.classList.contains("launcher-word") || (target.tagName === "SPAN" && target.closest(".textLayer")))) {
        clearZoneSelection();
        target.classList.add("zone-selected");
        currentZoneSpans = [target];
        extractZoneText();
        if (zoneSelectedText && tooltip) {
          const r = target.getBoundingClientRect();
          tooltip.style.top = Math.max(10, r.top - 44) + "px";
          tooltip.style.left = Math.max(10, r.left + r.width / 2 - 85) + "px";
          tooltip.style.display = "flex";
        }
      }
    });

    async function exportCurrentZoneToCad() {
      const app = window.PDFViewerApplication;
      if (!app) return;

      const cadBtn = document.getElementById("launcherPillCadBtn");
      if (cadBtn) {
        cadBtn.textContent = "⏳ Экспорт…";
        cadBtn.disabled = true;
      }

      try {
        const pageNum = app.page || 1;
        const pageView = app.pdfViewer?.getPageView(pageNum - 1);
        let pdfCrop = null;

        if (zoneBox && zoneBox.style.display !== "none") {
          const boxRect = zoneBox.getBoundingClientRect();
          const pageEl = (zoneBox.parentElement && zoneBox.parentElement.classList.contains("page"))
            ? zoneBox.parentElement
            : (document.querySelector(`.page[data-page-number="${pageNum}"]`) || zoneBox.closest(".page"));

          if (pageEl && pageView) {
            const pRect = pageEl.getBoundingClientRect();
            const rx0 = boxRect.left - pRect.left;
            const ry0 = boxRect.top - pRect.top;
            const rx1 = boxRect.right - pRect.left;
            const ry1 = boxRect.bottom - pRect.top;

            // Direct mapping to unscaled PDF points from page top-left (PyMuPDF convention)
            const scale = (pageView.viewport && pageView.viewport.scale) || (pRect.width / (pageView.width || pRect.width)) || 1.0;
            const x0 = Math.min(rx0, rx1) / scale;
            const y0 = Math.min(ry0, ry1) / scale;
            const x1 = Math.max(rx0, rx1) / scale;
            const y1 = Math.max(ry0, ry1) / scale;
            pdfCrop = [x0, y0, x1, y1];
          }
        }

        const pdfFile = getCurrentPdfPath();
        if (!pdfFile) {
          alert("Не удалось определить путь к открытому файлу PDF.");
          return;
        }

        const resp = await fetch("/api/pdf/export-cad", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            file: pdfFile,
            page: pageNum,
            crop: pdfCrop
          })
        });

        const data = await resp.json();
        if (!resp.ok || !data.success) {
          throw new Error(data.error || "Ошибка экспорта в CAD");
        }

        lastExportedCadPath = data.filePath;
        if (cadCard) {
          const fnEl = document.getElementById("launcherCadFileName");
          const stEl = document.getElementById("launcherCadStats");
          const lyEl = document.getElementById("launcherCadLayers");

          if (fnEl) fnEl.textContent = data.fileName || "чертеж.dxf";
          if (stEl) {
            stEl.textContent = `✅ ${data.entitiesCount || 0} примитивов (${data.closedLoopsCount || 0} замкнутых контуров)`;
          }
          if (lyEl) {
            const layers = data.layers ? Object.keys(data.layers) : [];
            lyEl.textContent = "Слои: " + (layers.join(", ") || "01_РАМА, 02_ШТАПИК, 03_ТЕРМОМОСТ, 04_УПЛОТНИТЕЛИ, 07_РАЗМЕРЫ");
          }
          cadCard.style.display = "block";
        }
      } catch (err) {
        alert("Ошибка экспорта в CAD: " + err.message);
      } finally {
        if (cadBtn) {
          cadBtn.textContent = "📐 В DWG";
          cadBtn.disabled = false;
        }
        if (tooltip) tooltip.style.display = "none";
      }
    }

    // Expose CAD export function inside initUI scope for context menu reuse
    window.exportCurrentZoneToCad = exportCurrentZoneToCad;

    const pillCadBtn = document.getElementById("launcherPillCadBtn");
    if (pillCadBtn) {
      pillCadBtn.onclick = (e) => {
        e.preventDefault();
        e.stopPropagation();
        exportCurrentZoneToCad();
      };
    }

    const pillTransBtn = document.getElementById("launcherPillTransBtn");
    if (pillTransBtn) {
      pillTransBtn.onclick = async (e) => {
        e.preventDefault();
        e.stopPropagation();
        tooltip.style.display = "none";
        const textToTranslate = zoneSelectedText;
        if (!textToTranslate) return;

        popover.style.display = "block";
        document.getElementById("launcherTransOrig").textContent = textToTranslate;
        document.getElementById("launcherTransRes").textContent = "Переводим…";

        try {
          const resp = await fetch("/api/translate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: textToTranslate, target: "ru" }),
          });
          const data = await resp.json();
          document.getElementById("launcherTransRes").textContent = data.translated || "—";
        } catch (err) {
          document.getElementById("launcherTransRes").textContent = "Ошибка: " + err.message;
        }
      };
    }

    // -------------------------------------------------------------------------
    // Dedicated Local Context Menu for PDF Document Selection (Task 006)
    // -------------------------------------------------------------------------
    document.addEventListener("selectionchange", () => {
      const s = window.getSelection();
      if (!s || s.isCollapsed) {
        if (!selectionMenu || selectionMenu.style.display === "none") {
          activeSelectionSnapshot = "";
        }
      } else {
        activeSelectionSnapshot = s.toString().trim();
      }
    });

    function hideSelectionContextMenu() {
      if (selectionMenu && selectionMenu.style.display !== "none") {
        selectionMenu.style.display = "none";
        return true;
      }
      return false;
    }

    function findPdfSelection(text) {
      if (!text) return;
      const app = window.PDFViewerApplication;
      if (app && app.findBar) {
        if (!app.findBar.opened) {
          app.findBar.open();
        }
        if (app.findBar.highlightAll) {
          app.findBar.highlightAll.checked = true;
        }
      }
      const findInput = document.getElementById("findInput");
      if (findInput) {
        findInput.value = text;
        findInput.focus();
        findInput.select();
        findInput.dispatchEvent(new Event("input", { bubbles: true }));
      }
    }

    function showSelectionContextMenu(clientX, clientY, snapshotText, canCadExport) {
      if (!selectionMenu) {
        selectionMenu = document.createElement("div");
        selectionMenu.id = "launcherSelectionContextMenu";
        selectionMenu.style.position = "fixed";
        selectionMenu.style.zIndex = "99999";
        selectionMenu.style.minWidth = "175px";
        selectionMenu.style.padding = "4px";
        selectionMenu.style.background = "#ffffff";
        selectionMenu.style.border = "1px solid #d1d9e0";
        selectionMenu.style.borderRadius = "4px";
        selectionMenu.style.boxShadow = "0 4px 12px rgba(15, 23, 42, 0.15)";
        selectionMenu.style.font = "12px/1.4 'Segoe UI', -apple-system, system-ui, sans-serif";
        selectionMenu.style.color = "#0F172A";
        selectionMenu.style.display = "none";
        document.body.appendChild(selectionMenu);
      }

      selectionMenu.innerHTML = "";
      const textToRun = String(snapshotText || "").trim();
      const hasText = Boolean(textToRun);

      const items = [
        {
          icon: "📋",
          label: "Скопировать",
          hint: "Ctrl+C",
          disabled: !hasText,
          run: async () => {
            if (!hasText) return;
            await copyPdfSelection(textToRun);
          }
        },
        {
          icon: "🌐",
          label: "Перевести",
          hint: "",
          disabled: !hasText,
          run: () => {
            if (!hasText) return;
            if (typeof window.launcherTranslateText === "function") {
              window.launcherTranslateText(textToRun);
            }
          }
        },
        {
          icon: "🔍",
          label: "Найти в документе",
          hint: "",
          disabled: !hasText,
          run: () => {
            if (!hasText) return;
            findPdfSelection(textToRun);
          }
        }
      ];

      if (canCadExport) {
        items.push({
          icon: "📐",
          label: "В DWG",
          hint: "",
          disabled: false,
          run: () => {
            if (typeof window.exportCurrentZoneToCad === "function") {
              window.exportCurrentZoneToCad();
            }
          }
        });
      }

      for (const it of items) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.gap = "8px";
        btn.style.width = "100%";
        btn.style.padding = "6px 10px 6px 8px";
        btn.style.border = "0";
        btn.style.borderRadius = "3px";
        btn.style.background = "transparent";
        btn.style.color = it.disabled ? "#94a3b8" : "#0F172A";
        btn.style.font = "inherit";
        btn.style.textAlign = "left";
        btn.style.cursor = it.disabled ? "default" : "pointer";
        btn.style.whiteSpace = "nowrap";

        if (!it.disabled) {
          btn.addEventListener("mouseenter", () => { btn.style.background = "#f6f8fa"; });
          btn.addEventListener("mouseleave", () => { btn.style.background = "transparent"; });
        }

        // Keep mousedown from triggering external dismiss handlers, while preserving button activation
        btn.addEventListener("mousedown", (e) => {
          e.stopPropagation();
        });

        btn.addEventListener("click", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          hideSelectionContextMenu();
          if (!it.disabled && typeof it.run === "function") {
            await it.run();
          }
        });

        const iconSpan = document.createElement("span");
        iconSpan.style.display = "inline-block";
        iconSpan.style.width = "16px";
        iconSpan.style.textAlign = "center";
        iconSpan.style.fontSize = "13px";
        iconSpan.textContent = it.icon;

        const labelSpan = document.createElement("span");
        labelSpan.style.flex = "1 1 auto";
        labelSpan.textContent = it.label;

        btn.append(iconSpan, labelSpan);

        if (it.hint) {
          const hintSpan = document.createElement("span");
          hintSpan.style.fontSize = "11px";
          hintSpan.style.color = "#64748b";
          hintSpan.style.marginLeft = "12px";
          hintSpan.textContent = it.hint;
          btn.append(hintSpan);
        }

        selectionMenu.appendChild(btn);
      }

      selectionMenu.style.display = "block";
      const menuWidth = selectionMenu.offsetWidth || 180;
      const menuHeight = selectionMenu.offsetHeight || 130;
      const x = Math.max(8, Math.min(clientX, window.innerWidth - menuWidth - 8));
      const y = Math.max(8, Math.min(clientY, window.innerHeight - menuHeight - 8));
      selectionMenu.style.left = x + "px";
      selectionMenu.style.top = y + "px";
    }

    document.addEventListener("contextmenu", (event) => {
      // 1. Pass through input, textarea, and contenteditable elements
      const targetEl = event.target instanceof Element ? event.target : null;
      if (targetEl && (targetEl.closest("input, textarea") || targetEl.isContentEditable)) {
        return;
      }

      event.preventDefault();
      event.stopPropagation();

      // Ensure any existing parent menus are dismissed
      try {
        if (window.parent && window.parent !== window && typeof window.parent.hideFileContextMenu === "function") {
          window.parent.hideFileContextMenu();
        }
      } catch (_) {}
      const findMenu = document.getElementById("launcherFindContextMenu");
      if (findMenu) findMenu.style.display = "none";

      // Snapshot text and zone context strictly at menu open
      const hasZone = Boolean(
        zoneBox && zoneBox.style.display !== "none" &&
        parseInt(zoneBox.style.width, 10) > 4 && parseInt(zoneBox.style.height, 10) > 4
      );
      const currentZoneText = String(zoneSelectedText || "").trim();

      const sel = window.getSelection();
      const liveSelText = (sel && !sel.isCollapsed) ? sel.toString().trim() : "";
      const textSnapshot = currentZoneText || liveSelText || activeSelectionSnapshot || "";
      const canCadExport = hasZone;

      showSelectionContextMenu(event.clientX, event.clientY, textSnapshot, canCadExport);
    });

    document.addEventListener("mousedown", (e) => {
      if (selectionMenu && selectionMenu.style.display !== "none" && !selectionMenu.contains(e.target)) {
        hideSelectionContextMenu();
      }
    });
    window.addEventListener("scroll", () => hideSelectionContextMenu(), true);
    window.addEventListener("blur", () => hideSelectionContextMenu());

    // Dismiss parent's context menu on any mouse click or scroll inside the PDF viewer
    const dismissParentContextMenu = (e) => {
      if (e && e.button === 2) return;
      try {
        if (window.parent && window.parent !== window && typeof window.parent.hideFileContextMenu === "function") {
          window.parent.hideFileContextMenu();
        }
      } catch (_) {}
    };

    document.addEventListener("pointerdown", dismissParentContextMenu, true);
    document.addEventListener("mousedown", dismissParentContextMenu, true);
    document.addEventListener("click", dismissParentContextMenu, true);
    window.addEventListener("scroll", dismissParentContextMenu, true);
    window.addEventListener("blur", dismissParentContextMenu);

    window.launcherTranslateText = function(text) {
      if (!text) return;
      popover.style.display = "block";
      document.getElementById("launcherTransOrig").textContent = text;
      document.getElementById("launcherTransRes").textContent = "Переводим…";

      fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, target: "ru" }),
      })
        .then((r) => r.json())
        .then((data) => {
          document.getElementById("launcherTransRes").textContent = data.translated || "—";
        })
        .catch((err) => {
          document.getElementById("launcherTransRes").textContent = "Ошибка: " + err.message;
        });
    };

    function handlePdfJsEscape() {
      // 0. Сброс локального контекстного меню выделения PDF
      if (hideSelectionContextMenu()) {
        return true;
      }
      // 1. Сброс контекстного меню родителя
      try {
        if (window.parent && window.parent !== window && typeof window.parent.hideFileContextMenu === "function") {
          if (window.parent.hideFileContextMenu()) return true;
        }
      } catch (_) {}

      // 2. Сброс карточки CAD, окна перевода или всплывающей плашки
      if (cadCard && cadCard.style.display !== "none") {
        cadCard.style.display = "none";
        return true;
      }
      if (popover && popover.style.display !== "none") {
        popover.style.display = "none";
        return true;
      }
      if (tooltip && tooltip.style.display !== "none") {
        tooltip.style.display = "none";
        return true;
      }

      // 3. Сброс прямоугольного выделения зоны AutoCAD (если активно)
      if (clearZoneSelection()) {
        return true;
      }

      // 4. Сброс выделения текста при следующем нажатии (если есть нативное)
      const sel = window.getSelection();
      if (sel && !sel.isCollapsed && sel.toString().trim()) {
        sel.removeAllRanges();
        return true;
      }

      // 5. Сброс поиска: закрытие бара, очистка поля и снятие подсветки совпадений
      const app = window.PDFViewerApplication;
      if (app) {
        const isFindOpen = Boolean(app.findBar?.opened);
        const hasSearchQuery = Boolean(app.findBar?.findField?.value);
        const hasHighlights = Boolean(document.querySelector(".textLayer .highlight"));
        if (isFindOpen || hasSearchQuery || hasHighlights) {
          if (app.findBar?.findField) {
            app.findBar.findField.value = "";
          }
          if (app.findBar?.opened) {
            app.findBar.close();
          }
          try {
            app.findController?.executeCommand("find", { query: "", highlightAll: false, phraseSearch: true, findPrevious: false });
            app.eventBus?.dispatch("find", { type: "", query: "", phraseSearch: true, highlightAll: false });
          } catch (_) {}
          document.querySelectorAll(".textLayer .highlight").forEach((el) => {
            el.classList.remove("highlight", "selected", "begin", "end", "middle");
          });
          if (app.findBar && typeof app.findBar.updateResultsCount === "function") {
            app.findBar.updateResultsCount({ current: 0, total: 0 });
          }
          return true;
        }

        if (app.secondaryToolbar?.isOpen) {
          app.secondaryToolbar.close();
          return true;
        }
      }

      return false;
    }
    window.handlePdfJsEscape = handlePdfJsEscape;
    window.clearZoneSelection = clearZoneSelection;

    // Tool mode management (0: AutoCAD Zone, 1: Hand Pan, 2: Linear Text)
    window.getViewerToolMode = function() {
      return viewerToolMode;
    };

    window.setViewerToolMode = function(mode) {
      viewerToolMode = Number(mode);
      const app = window.PDFViewerApplication;
      document.body.classList.remove("hand-mode-active", "text-mode-active", "zone-mode-active");

      if (viewerToolMode === 1) {
        // Hand mode
        clearZoneSelection();
        document.body.classList.add("hand-mode-active");
        try {
          app?.pdfCursorTools?.switchTool(1);
        } catch (_) {}
      } else if (viewerToolMode === 2) {
        // Linear text selection mode (blinking I-beam cursor)
        clearZoneSelection();
        document.body.classList.add("text-mode-active");
        try {
          app?.pdfCursorTools?.switchTool(0);
        } catch (_) {}
      } else {
        // AutoCAD rectangular zone mode (crosshair cursor)
        viewerToolMode = 0;
        clearZoneSelection();
        document.body.classList.add("zone-mode-active");
        try {
          app?.pdfCursorTools?.switchTool(0);
        } catch (_) {}
      }
      try {
        if (window.parent && typeof window.parent.updateViewerToolButton === "function") {
          window.parent.updateViewerToolButton(viewerToolMode);
        }
      } catch (_) {}
    };

    // Unified sequential copy action with cascading fallbacks (primary -> backend -> execCommand)
    async function copyPdfSelection(customText) {
      const sel = window.getSelection();
      const selText = sel ? sel.toString().trim() : "";
      const text = (customText !== undefined && customText !== null && customText !== "")
        ? String(customText).trim()
        : (zoneSelectedText || selText || "");
      if (!text) return false;

      let copied = false;

      // 1. Primary: navigator.clipboard.writeText (while user gesture is active)
      if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
        try {
          await navigator.clipboard.writeText(text);
          copied = true;
        } catch (err) {
          console.warn("[PDF copy] navigator.clipboard.writeText failed:", err);
        }
      }

      // 2. Fallback 1: backend POST /api/clipboard (only if primary failed)
      if (!copied) {
        try {
          const resp = await fetch("/api/clipboard", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text }),
          });
          if (resp.ok) {
            const data = await resp.json();
            if (data && data.ok) {
              copied = true;
            }
          }
        } catch (err) {
          console.warn("[PDF copy] backend /api/clipboard fallback failed:", err);
        }
      }

      // 3. Fallback 2: execCommand on temporary textarea (only if both above failed)
      if (!copied) {
        try {
          const ta = document.createElement("textarea");
          ta.value = text;
          ta.style.position = "fixed";
          ta.style.top = "0";
          ta.style.left = "0";
          ta.style.opacity = "0";
          document.body.appendChild(ta);
          ta.focus();
          ta.select();
          copied = document.execCommand("copy");
          document.body.removeChild(ta);
        } catch (err) {
          console.warn("[PDF copy] execCommand fallback failed:", err);
        }
      }

      // Single notification after sequence completes
      if (copied) {
        if (window.parent && window.parent !== window && typeof window.parent.showToast === "function") {
          window.parent.showToast("Текст скопирован в буфер обмена");
        }
      } else {
        if (window.parent && window.parent !== window && typeof window.parent.showToast === "function") {
          window.parent.showToast("Ошибка копирования в буфер обмена");
        }
      }

      return copied;
    }
    window.copyPdfSelection = copyPdfSelection;

    // Dedicated HTML Context Menu for #findInput (ПКМ -> Вставить)
    function initFindInputContextMenu() {
      const findInput = document.getElementById("findInput");
      if (!findInput || findInput.dataset.pkmContextBound === "true") return;
      findInput.dataset.pkmContextBound = "true";

      let menu = document.getElementById("launcherFindContextMenu");
      if (!menu) {
        menu = document.createElement("div");
        menu.id = "launcherFindContextMenu";
        menu.style.position = "fixed";
        menu.style.zIndex = "99999";
        menu.style.minWidth = "150px";
        menu.style.padding = "4px";
        menu.style.background = "#fbfcfd";
        menu.style.border = "1px solid #abadb3";
        menu.style.borderRadius = "4px";
        menu.style.boxShadow = "2px 3px 8px rgba(0, 0, 0, 0.25)";
        menu.style.font = "12px/1.4 'Segoe UI', -apple-system, system-ui, sans-serif";
        menu.style.color = "#1e293b";
        menu.style.display = "none";

        const btn = document.createElement("button");
        btn.type = "button";
        btn.style.display = "flex";
        btn.style.alignItems = "center";
        btn.style.gap = "8px";
        btn.style.width = "100%";
        btn.style.padding = "6px 10px 6px 8px";
        btn.style.border = "0";
        btn.style.borderRadius = "2px";
        btn.style.background = "transparent";
        btn.style.color = "inherit";
        btn.style.font = "inherit";
        btn.style.textAlign = "left";
        btn.style.cursor = "pointer";
        btn.style.whiteSpace = "nowrap";

        btn.innerHTML = '<span style="display:inline-block; width:16px; text-align:center; font-size:13px;">📋</span><span style="flex:1 1 auto;">Вставить</span><span style="font-size:11px; color:#6b7280; margin-left:12px;">Ctrl+V</span>';

        btn.addEventListener("mouseenter", () => { btn.style.background = "#e5f1fb"; });
        btn.addEventListener("mouseleave", () => { btn.style.background = "transparent"; });

        // Prevent mousedown from blurring findInput or dismissing prematurely
        btn.addEventListener("mousedown", (e) => {
          e.preventDefault();
          e.stopPropagation();
        });

        btn.addEventListener("click", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          menu.style.display = "none";

          let text = "";
          // 1. Primary: read actual Windows clipboard via navigator.clipboard.readText()
          if (navigator.clipboard && typeof navigator.clipboard.readText === "function") {
            try {
              text = await navigator.clipboard.readText();
            } catch (err) {
              console.warn("[PDF paste] navigator.clipboard.readText failed:", err);
            }
          }

          // 2. Parent fallback if iframe clipboard reading was restricted
          if (!text && window.parent && window.parent !== window && window.parent.navigator?.clipboard?.readText) {
            try {
              text = await window.parent.navigator.clipboard.readText();
            } catch (err) {
              console.warn("[PDF paste] parent.navigator.clipboard.readText failed:", err);
            }
          }

          if (!text) {
            if (window.parent && window.parent !== window && typeof window.parent.showToast === "function") {
              window.parent.showToast("Буфер обмена пуст или доступ заблокирован");
            }
            return;
          }

          // Insert text at saved cursor / selection
          const val = findInput.value || "";
          const start = (savedSelectionStart !== null && savedSelectionStart !== undefined) ? savedSelectionStart : val.length;
          const end = (savedSelectionEnd !== null && savedSelectionEnd !== undefined) ? savedSelectionEnd : start;
          findInput.value = val.slice(0, start) + text + val.slice(end);

          // Restore focus and cursor to end of inserted text
          const newPos = start + text.length;
          findInput.focus();
          try {
            findInput.setSelectionRange(newPos, newPos);
          } catch (_) {}

          // Single search execution: standard PDF.js 'input' event triggers dispatchEvent("") in viewer.js:4973
          findInput.dispatchEvent(new Event("input", { bubbles: true }));
        });

        menu.appendChild(btn);
        document.body.appendChild(menu);
      }

      let savedSelectionStart = null;
      let savedSelectionEnd = null;

      findInput.addEventListener("contextmenu", (e) => {
        e.preventDefault();
        e.stopPropagation();

        savedSelectionStart = typeof findInput.selectionStart === "number" ? findInput.selectionStart : findInput.value.length;
        savedSelectionEnd = typeof findInput.selectionEnd === "number" ? findInput.selectionEnd : savedSelectionStart;

        menu.style.display = "block";
        const menuWidth = menu.offsetWidth || 150;
        const menuHeight = menu.offsetHeight || 36;
        const x = Math.max(8, Math.min(e.clientX, window.innerWidth - menuWidth - 8));
        const y = Math.max(8, Math.min(e.clientY, window.innerHeight - menuHeight - 8));
        menu.style.left = x + "px";
        menu.style.top = y + "px";
      });

      document.addEventListener("mousedown", (e) => {
        if (menu && menu.style.display !== "none" && !menu.contains(e.target)) {
          menu.style.display = "none";
        }
      });
      window.addEventListener("scroll", () => {
        if (menu) menu.style.display = "none";
      }, true);
      window.addEventListener("blur", () => {
        if (menu) menu.style.display = "none";
      });
    }

    // Call initFindInputContextMenu immediately in initUI
    initFindInputContextMenu();

    window.addEventListener("keydown", (e) => {
      // 1. Escape: пошаговый сброс телодвижений в Окне 3
      if (e.key === "Escape") {
        if (handlePdfJsEscape()) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
      }
      // 2. Ctrl+C: unified copy action (same function used by context menu)
      if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C" || e.key === "с" || e.key === "С")) {
        copyPdfSelection();
      }
    });
  }

  function initPdfJsEnhancements() {
    const app = window.PDFViewerApplication;
    if (!app) return;

    let lockedScale = null;

    const setupApp = () => {
      if (!app.eventBus || !app.pdfViewer) return;

      // 1. Never let internal destination zoom override user's scale
      if (app.pdfLinkService) {
        app.pdfLinkService._ignoreDestinationZoom = true;
      }

      // 2. Default tool: ALWAYS SELECT (Рамка) on load
      try {
        app.pdfCursorTools?.switchTool(0); // CursorTool.SELECT
      } catch (_) {}

      // 3. Ensure findBar defaults to Highlight All
      if (app.findBar) {
        if (app.findBar.highlightAll) {
          app.findBar.highlightAll.checked = true;
        }
      }
      initFindInputContextMenu();

      // 4. Freeze scale into a fixed numeric scale so page transitions NEVER auto-recalculate
      const freezeScale = () => {
        const current = app.pdfViewer.currentScale;
        if (current && current > 0) {
          lockedScale = current;
          app.pdfViewer.currentScaleValue = String(current);
        }
      };

      app.eventBus.on("pagesloaded", () => {
        if (!lockedScale) {
          freezeScale();
        }
        document.querySelectorAll(".textLayer").forEach(tokenizeTextLayerWords);
      });
      app.eventBus.on("pagesinit", () => {
        activeSelectionSnapshot = "";
        hideSelectionContextMenu();
        if (!lockedScale) {
          freezeScale();
        }
      });
      app.eventBus.on("pagechanging", () => {
        activeSelectionSnapshot = "";
        hideSelectionContextMenu();
      });

      // When user zooms manually (buttons, dropdown, or Ctrl+wheel), remember new scale
      app.eventBus.on("scalechanging", (evt) => {
        if (evt && evt.scale) {
          lockedScale = evt.scale;
        }
      });

      // 5. Auto-scroll and smooth center on the active match
      const scrollToActiveMatch = () => {
        requestAnimationFrame(() => {
          const activeMatch = document.querySelector(".textLayer .highlight.selected");
          if (activeMatch) {
            activeMatch.scrollIntoView({
              behavior: "smooth",
              block: "center",
              inline: "center"
            });
          }
        });
      };

      app.eventBus.on("updatefindcontrolstate", () => {
        scrollToActiveMatch();
        setTimeout(scrollToActiveMatch, 60);
        setTimeout(scrollToActiveMatch, 180);
      });

      app.eventBus.on("textlayerrendered", (evt) => {
        try {
          const layerDiv = evt?.source?.textLayerDiv || evt?.source?.div || document.querySelector(`.page[data-page-number="${evt?.pageNumber}"] .textLayer`);
          if (layerDiv) {
            tokenizeTextLayerWords(layerDiv);
          }
        } catch (err) {
          console.warn("[Launcher] tokenizeTextLayerWords error:", err);
        }

        if (app.findController?.selected?.pageIdx !== -1) {
          scrollToActiveMatch();
          setTimeout(scrollToActiveMatch, 80);
        }
      });

      app.eventBus.on("updatetextlayermatches", () => {
        scrollToActiveMatch();
      });

      app.eventBus.on("find", (evt) => {
        if (evt) {
          evt.highlightAll = true;
        }
        if (app.findBar?.highlightAll) {
          app.findBar.highlightAll.checked = true;
        }
      });
    };

    if (app.initialized) {
      setupApp();
    } else {
      window.document.addEventListener("webviewerloaded", () => {
        if (app.initializedPromise) {
          app.initializedPromise.then(setupApp);
        } else {
          setupApp();
        }
      }, { once: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      initUI();
      initPdfJsEnhancements();
    });
  } else {
    initUI();
    initPdfJsEnhancements();
  }
})();
