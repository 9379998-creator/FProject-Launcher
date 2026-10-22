// Floating translation pill, cursor tool toggle, search match navigation, scale-lock,
// and AutoCAD-style word-level rectangular zone selection with dual-mode support for Mozilla PDF.js
(function() {
  let tooltip = null;
  let popover = null;
  let zoneBox = null;
  let viewerToolMode = 0; // 0: AutoCAD Zone (Рамка), 1: Hand (Лапа), 2: Linear Text (Текст)
  let isMouseDown = false;
  let isDragging = false;
  let zoneStart = { clientX: 0, clientY: 0, target: null };
  let zoneSelectedText = "";
  let currentZoneSpans = [];

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

  const updateSelectionTooltip = () => {
    if (viewerToolMode === 0 && zoneSelectedText && zoneBox && zoneBox.style.display !== "none") {
      const rect = zoneBox.getBoundingClientRect();
      tooltip.style.top = Math.max(10, rect.top - 38) + "px";
      tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 45) + "px";
      tooltip.style.display = "block";
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
        tooltip.style.top = Math.max(10, rect.top - 38) + "px";
        tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 45) + "px";
        tooltip.style.display = "block";
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

    // Floating Translate Pill button
    tooltip = document.createElement("button");
    tooltip.id = "launcherTransPill";
    tooltip.textContent = "🌐 Перевести";
    tooltip.style.cssText = `
      position: fixed;
      display: none;
      z-index: 9999999;
      background: #0969da;
      color: #fff;
      border: none;
      border-radius: 6px;
      padding: 6px 12px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      box-shadow: 0 4px 14px rgba(0,0,0,0.25);
      transition: transform 0.1s ease;
    `;
    tooltip.onmouseover = () => tooltip.style.background = "#0055b3";
    tooltip.onmouseout = () => tooltip.style.background = "#0969da";
    document.body.appendChild(tooltip);

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
      const interactive = e.target.closest("button, input, select, textarea, #toolbarViewer, #findbar, #launcherTransPill, #launcherTransCard");
      if (interactive) return;

      // Hide translation tooltip if clicking elsewhere
      if (tooltip && e.target !== tooltip && !tooltip.contains(e.target)) {
        tooltip.style.display = "none";
      }

      // If in Hand mode (mode === 1) or Text mode (mode === 2): don't draw rectangular box
      if (viewerToolMode === 1 || viewerToolMode === 2) {
        isMouseDown = true;
        return;
      }

      // Zone mode (mode === 0): AutoCAD-style rectangular zone selection
      if (e.button === 0) {
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
      }
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

      // Show floating "🌐 Перевести" pill right above the rectangle
      if (zoneSelectedText && tooltip && zoneBox) {
        const boxRect = zoneBox.getBoundingClientRect();
        tooltip.style.top = Math.max(10, boxRect.top - 38) + "px";
        tooltip.style.left = Math.max(10, boxRect.left + boxRect.width / 2 - 45) + "px";
        tooltip.style.display = "block";
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
          tooltip.style.top = Math.max(10, r.top - 38) + "px";
          tooltip.style.left = Math.max(10, r.left + r.width / 2 - 45) + "px";
          tooltip.style.display = "block";
        }
      }
    });

    tooltip.onclick = async (e) => {
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

    // Unified Right-Click Context Menu for PDF Viewer
    document.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const sel = window.getSelection();
      const selText = sel ? sel.toString().trim() : "";
      const textToUse = zoneSelectedText || selText || "";
      try {
        if (window.parent && window.parent !== window && typeof window.parent.showPdfViewerContextMenu === "function") {
          const frameRect = window.frameElement ? window.frameElement.getBoundingClientRect() : { left: 0, top: 0 };
          window.parent.showPdfViewerContextMenu(
            frameRect.left + event.clientX,
            frameRect.top + event.clientY,
            { selectedText: textToUse }
          );
        }
      } catch (_) {}
    });

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
      // 1. Сброс контекстного меню
      try {
        if (window.parent && window.parent !== window && typeof window.parent.hideFileContextMenu === "function") {
          if (window.parent.hideFileContextMenu()) return true;
        }
      } catch (_) {}

      // 2. Сброс перевода (окно перевода или всплывающая плашка)
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

    window.addEventListener("keydown", (e) => {
      // 1. Escape: пошаговый сброс телодвижений в Окне 3
      if (e.key === "Escape") {
        if (handlePdfJsEscape()) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
      }
      // 2. Ctrl+C: copy selected zone text or native text and show toast
      if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C" || e.key === "с" || e.key === "С")) {
        const sel = window.getSelection();
        const selText = sel ? sel.toString().trim() : "";
        const text = zoneSelectedText || selText;
        if (text) {
          try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(text);
            }
          } catch (_) {}
          try {
            if (window.parent && window.parent !== window && typeof window.parent.copyTextToClipboard === "function") {
              window.parent.copyTextToClipboard(text, "Текст зоны скопирован в буфер обмена");
            }
          } catch (_) {}
        }
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
        if (!lockedScale) {
          freezeScale();
        }
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
