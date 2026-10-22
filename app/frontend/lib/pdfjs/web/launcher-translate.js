// Floating translation pill, cursor tool toggle, search match navigation, scale-lock,
// column-aware DOM text sorting, and rectangular zone selection for Mozilla PDF.js
(function() {
  let tooltip = null;
  let popover = null;
  let zoneBox = null;
  let viewerToolMode = 0; // 0: Select (Стрелка), 1: Hand (Лапа), 2: Zone (Зона)
  let isZoneSelecting = false;
  let zoneStart = { x: 0, y: 0, pageX: 0, pageY: 0 };
  let zoneSelectedText = "";
  let currentZoneSpans = [];

  function clearZoneSelection() {
    const hadSelection = Boolean(zoneSelectedText || (zoneBox && zoneBox.style.display !== "none"));
    if (zoneBox) {
      zoneBox.style.display = "none";
      zoneBox.style.width = "0px";
      zoneBox.style.height = "0px";
    }
    document.querySelectorAll(".textLayer span.zone-selected").forEach((el) => {
      el.classList.remove("zone-selected");
    });
    currentZoneSpans = [];
    zoneSelectedText = "";
    return hadSelection;
  }

  function initUI() {
    if (tooltip) return;

    // Inject high-contrast match styling, zone selection styling, and fix selection
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

      /* Prominent search button in PDF viewer toolbar */
      #viewFind {
        min-width: 76px !important;
        width: auto !important;
        padding: 0 8px !important;
        gap: 4px !important;
        background: rgba(9, 105, 218, 0.08) !important;
        border: 1px solid rgba(9, 105, 218, 0.25) !important;
        border-radius: 3px !important;
        color: #0969da !important;
      }
      #viewFind > span {
        display: inline-block !important;
        text-indent: 0 !important;
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #0969da !important;
      }
      #viewFind:hover {
        background: rgba(9, 105, 218, 0.16) !important;
        border-color: #0969da !important;
      }

      /* 1. Make textLayer fully visible and selectable */
      .textLayer {
        opacity: 1 !important;
        user-select: text !important;
        -webkit-user-select: text !important;
      }
      .textLayer :is(span:not(.highlight), br) {
        color: transparent !important;
      }
      .textLayer span {
        user-select: text !important;
        -webkit-user-select: text !important;
      }

      /* Prevent markedContent tags from disrupting Chromium multi-line text selection */
      .textLayer span.markedContent {
        display: none !important;
        pointer-events: none !important;
        user-select: none !important;
      }

      /* Prevent full-page ghost backdrop from snapping multi-column selection across columns in Chrome */
      .textLayer .endOfContent {
        display: none !important;
        pointer-events: none !important;
        user-select: none !important;
      }

      /* 2. Rectangular zone selection styling */
      .textLayer span.zone-selected {
        background-color: rgba(0, 102, 255, 0.3) !important;
        outline: 1px solid rgba(0, 102, 255, 0.6) !important;
        border-radius: 2px !important;
        color: transparent !important;
      }
      #launcherZoneBox {
        position: absolute;
        pointer-events: none;
        border: 1.5px dashed #0969da;
        background-color: rgba(9, 105, 218, 0.14);
        z-index: 999999;
        border-radius: 3px;
        display: none;
      }
      body.zone-mode-active #viewerContainer,
      body.zone-mode-active .textLayer,
      body.zone-mode-active .textLayer span {
        cursor: crosshair !important;
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

      /* 5. Text selection: natural translucent blue highlight.
         Text glyphs stay transparent so underlying vector canvas text displays directly with perfect sharp clarity,
         preventing ghost offset text, duplicate letters, or displaced lines! */
      .textLayer ::-moz-selection {
        background: rgba(0, 102, 255, 0.35) !important;
        color: transparent !important;
      }
      .textLayer ::selection {
        background: rgba(0, 102, 255, 0.35) !important;
        color: transparent !important;
      }
      .textLayer .highlight::-moz-selection {
        background: rgba(0, 102, 255, 0.5) !important;
        color: #000000 !important;
      }
      .textLayer .highlight::selection {
        background: rgba(0, 102, 255, 0.5) !important;
        color: #000000 !important;
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
      width: 320px;
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
        <div id="launcherTransOrig" style="font-size:13px; color:#4b5563; word-break:break-word; background:#f9fafb; padding:6px 8px; border-radius:6px; border:1px solid #e5e7eb;"></div>
        <div style="text-align:center; color:#9ca3af; font-size:12px; margin:4px 0;">↓</div>
        <div id="launcherTransRes" style="font-size:14px; font-weight:600; color:#0969da; word-break:break-word; background:#eff6ff; padding:8px 10px; border-radius:6px; border-left:3px solid #0091ff;"></div>
      </div>
      <div style="display:flex; justify-content:flex-end; margin-top:8px;">
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

    let selectedText = "";
    let isMouseDown = false;

    const updateSelectionTooltip = () => {
      if (zoneSelectedText) {
        selectedText = zoneSelectedText;
        if (zoneBox && zoneBox.style.display !== "none") {
          const rect = zoneBox.getBoundingClientRect();
          tooltip.style.top = Math.max(10, rect.top - 38) + "px";
          tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 45) + "px";
          tooltip.style.display = "block";
        }
        return;
      }
      const sel = window.getSelection();
      const txt = sel ? sel.toString().trim() : "";
      if (!txt) {
        if (tooltip) tooltip.style.display = "none";
        return;
      }
      selectedText = txt;
      try {
        const range = sel.getRangeAt(0);
        const rect = range.getBoundingClientRect();
        if (rect && rect.width > 0 && rect.height > 0) {
          tooltip.style.top = Math.max(10, rect.top - 38) + "px";
          tooltip.style.left = Math.max(10, rect.left + rect.width / 2 - 45) + "px";
          tooltip.style.display = "block";
        }
      } catch (e) {}
    };

    document.addEventListener("mousedown", (e) => {
      if (tooltip && e.target !== tooltip && !tooltip.contains(e.target)) {
        tooltip.style.display = "none";
      }

      // Check if starting a rectangular zone selection (Alt key held OR tool mode is Zone)
      if (e.button === 0 && (e.altKey || viewerToolMode === 2)) {
        isZoneSelecting = true;
        zoneStart = { x: e.clientX, y: e.clientY, pageX: e.pageX, pageY: e.pageY };
        clearZoneSelection();
        window.getSelection()?.removeAllRanges();

        if (zoneBox) {
          zoneBox.style.left = e.pageX + "px";
          zoneBox.style.top = e.pageY + "px";
          zoneBox.style.width = "0px";
          zoneBox.style.height = "0px";
          zoneBox.style.display = "block";
        }
        e.preventDefault();
        return;
      }

      // Normal click: if there was an active zone box, clear it if clicking outside
      if (e.button === 0 && zoneSelectedText && zoneBox && zoneBox.style.display !== "none") {
        clearZoneSelection();
      }

      isMouseDown = true;
    });

    document.addEventListener("mousemove", (e) => {
      if (!isZoneSelecting || !zoneBox) return;

      const left = Math.min(zoneStart.pageX, e.pageX);
      const top = Math.min(zoneStart.pageY, e.pageY);
      const width = Math.abs(e.pageX - zoneStart.pageX);
      const height = Math.abs(e.pageY - zoneStart.pageY);

      zoneBox.style.left = left + "px";
      zoneBox.style.top = top + "px";
      zoneBox.style.width = width + "px";
      zoneBox.style.height = height + "px";

      if (width > 6 || height > 6) {
        const boxRect = {
          left: Math.min(zoneStart.x, e.clientX),
          top: Math.min(zoneStart.y, e.clientY),
          right: Math.max(zoneStart.x, e.clientX),
          bottom: Math.max(zoneStart.y, e.clientY)
        };

        const matchedSpans = [];
        const allSpans = document.querySelectorAll(".textLayer span:not(.markedContent):not(.endOfContent)");
        for (let i = 0; i < allSpans.length; i++) {
          const span = allSpans[i];
          const r = span.getBoundingClientRect();
          if (r.width === 0 && r.height === 0) continue;
          const intersects = !(
            r.right < boxRect.left ||
            r.left > boxRect.right ||
            r.bottom < boxRect.top ||
            r.top > boxRect.bottom
          );
          if (intersects) {
            span.classList.add("zone-selected");
            matchedSpans.push(span);
          } else {
            span.classList.remove("zone-selected");
          }
        }
        currentZoneSpans = matchedSpans;
      }
      e.preventDefault();
    });

    document.addEventListener("mouseup", () => {
      if (isZoneSelecting) {
        isZoneSelecting = false;
        const width = zoneBox ? parseInt(zoneBox.style.width, 10) || 0 : 0;
        const height = zoneBox ? parseInt(zoneBox.style.height, 10) || 0 : 0;
        if (width < 8 && height < 8) {
          clearZoneSelection();
          return;
        }

        if (currentZoneSpans.length > 0) {
          // Sort zone spans line-by-line (top with 5px tolerance, then left)
          const sorted = currentZoneSpans.slice().sort((a, b) => {
            const rA = a.getBoundingClientRect();
            const rB = b.getBoundingClientRect();
            const diffY = rA.top - rB.top;
            if (Math.abs(diffY) > 5) return diffY;
            return rA.left - rB.left;
          });

          const lines = [];
          let curLine = [];
          let curTop = null;
          for (let i = 0; i < sorted.length; i++) {
            const span = sorted[i];
            const r = span.getBoundingClientRect();
            const txt = (span.textContent || "").trim();
            if (!txt) continue;
            if (curTop === null || Math.abs(r.top - curTop) < 6) {
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

          if (zoneSelectedText && tooltip && zoneBox) {
            selectedText = zoneSelectedText;
            const boxRect = zoneBox.getBoundingClientRect();
            tooltip.style.top = Math.max(10, boxRect.top - 38) + "px";
            tooltip.style.left = Math.max(10, boxRect.left + boxRect.width / 2 - 45) + "px";
            tooltip.style.display = "block";
          }
        }
        return;
      }

      isMouseDown = false;
      // Show translation pill ONLY after user finishes mouse drag selection
      setTimeout(updateSelectionTooltip, 30);
    });

    document.addEventListener("selectionchange", () => {
      if (isMouseDown || isZoneSelecting) {
        if (tooltip) tooltip.style.display = "none";
        return;
      }
      updateSelectionTooltip();
    });

    tooltip.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      tooltip.style.display = "none";
      const textToTranslate = zoneSelectedText || selectedText;
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
      const textToUse = zoneSelectedText || selText;
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

      // 3. Сброс прямоугольного выделения зоны (если активно)
      if (clearZoneSelection()) {
        return true;
      }

      // 4. Сброс выделения текста при следующем нажатии
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

    // Tool mode management
    window.getViewerToolMode = function() {
      return viewerToolMode;
    };

    window.setViewerToolMode = function(mode) {
      viewerToolMode = Number(mode) || 0;
      const app = window.PDFViewerApplication;
      if (viewerToolMode === 1) {
        // Hand tool
        clearZoneSelection();
        document.body.classList.remove("zone-mode-active");
        try {
          app?.pdfCursorTools?.switchTool(1);
        } catch (_) {}
      } else if (viewerToolMode === 2) {
        // Zone selection tool
        document.body.classList.add("zone-mode-active");
        try {
          app?.pdfCursorTools?.switchTool(0);
        } catch (_) {}
      } else {
        // Select tool
        clearZoneSelection();
        document.body.classList.remove("zone-mode-active");
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
      // 2. Ctrl+C: copy selected text (standard or zone) and show toast
      if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C" || e.key === "с" || e.key === "С")) {
        let text = zoneSelectedText;
        if (!text) {
          const sel = window.getSelection();
          text = sel ? sel.toString().trim() : "";
        }
        if (text) {
          try {
            if (navigator.clipboard && navigator.clipboard.writeText) {
              navigator.clipboard.writeText(text);
            }
          } catch (_) {}
          try {
            if (window.parent && window.parent !== window && typeof window.parent.copyTextToClipboard === "function") {
              window.parent.copyTextToClipboard(text, "Текст скопирован в буфер обмена");
            }
          } catch (_) {}
        }
      }
    });
  }

  // Column-Aware TextLayer DOM Sorting
  // Ensures spans in multi-column pages (e.g. 2, 3, or 4 columns) are arranged in natural column reading order.
  // Standard Chromium selection follows DOM order; grouping spans by column guarantees that dragging down in
  // Column 1 selects only Column 1, completely preventing bleeding across to Columns 2, 3, or 4!
  function sortTextLayerByColumns(layerDiv) {
    if (!layerDiv || layerDiv.dataset.launcherSorted) return;

    const rawSpans = Array.from(layerDiv.children).filter(
      (el) => el.tagName === "SPAN" && !el.classList.contains("markedContent") && !el.classList.contains("endOfContent")
    );
    if (rawSpans.length < 4) return;

    const layerWidth = layerDiv.offsetWidth || layerDiv.clientWidth || 800;
    const items = [];

    for (let i = 0; i < rawSpans.length; i++) {
      const el = rawSpans[i];
      const left = el.offsetLeft;
      const top = el.offsetTop;
      const width = el.offsetWidth;
      const height = el.offsetHeight || 12;
      const text = (el.textContent || "").trim();
      if (!text && width === 0) continue;

      items.push({
        el,
        left,
        top,
        width,
        height,
        right: left + width,
        bottom: top + height,
        centerX: left + width / 2,
        centerY: top + height / 2,
        text,
        origIdx: i
      });
    }

    if (items.length < 4) return;

    // Filter narrow spans (< 65% page width) to detect vertical gutters between columns
    const contentItems = items.filter((it) => it.width < layerWidth * 0.65);
    if (contentItems.length < 4) {
      sortAndReappend(layerDiv, items, () => 0);
      return;
    }

    const BIN_SIZE = 4;
    const numBins = Math.max(10, Math.ceil(layerWidth / BIN_SIZE));
    const hist = new Int16Array(numBins);

    for (let i = 0; i < contentItems.length; i++) {
      const it = contentItems[i];
      const bStart = Math.max(0, Math.floor(it.left / BIN_SIZE));
      const bEnd = Math.min(numBins - 1, Math.ceil(it.right / BIN_SIZE));
      for (let b = bStart; b <= bEnd; b++) {
        hist[b]++;
      }
    }

    // A gutter is an empty interval (count == 0) at least 12px wide, excluding margins
    const minGutterBins = Math.max(3, Math.floor(12 / BIN_SIZE));
    const marginBinsStart = Math.floor(25 / BIN_SIZE);
    const marginBinsEnd = Math.floor((layerWidth - 25) / BIN_SIZE);

    const gutters = [];
    let inGutter = false;
    let gutterStart = 0;

    for (let b = marginBinsStart; b <= marginBinsEnd; b++) {
      if (hist[b] === 0) {
        if (!inGutter) {
          inGutter = true;
          gutterStart = b;
        }
      } else {
        if (inGutter) {
          inGutter = false;
          const gutterLen = b - gutterStart;
          if (gutterLen >= minGutterBins) {
            gutters.push({
              startPx: gutterStart * BIN_SIZE,
              endPx: b * BIN_SIZE,
              midPx: ((gutterStart + b) / 2) * BIN_SIZE
            });
          }
        }
      }
    }

    function getColumnIndex(it) {
      if (it.width >= layerWidth * 0.65) {
        return -1; // Full-width element spanning across columns
      }
      for (let g = 0; g < gutters.length; g++) {
        if (it.centerX < gutters[g].midPx) {
          return g;
        }
      }
      return gutters.length;
    }

    sortAndReappend(layerDiv, items, getColumnIndex);
  }

  function sortAndReappend(layerDiv, items, getColumnIndex) {
    items.sort((a, b) => {
      const colA = getColumnIndex(a);
      const colB = getColumnIndex(b);

      if (colA >= 0 && colB >= 0) {
        if (colA !== colB) {
          return colA - colB; // Column 0 before Column 1 before Column 2, etc.
        }
        // Within same column: sort top-to-bottom, line threshold 5px
        const lineDiff = a.top - b.top;
        if (Math.abs(lineDiff) > 5) {
          return lineDiff;
        }
        return a.left - b.left;
      }

      // Headers / wide banners: sort by top
      const lineDiff = a.top - b.top;
      if (Math.abs(lineDiff) > 8) {
        return lineDiff;
      }
      return a.left - b.left;
    });

    const fragment = document.createDocumentFragment();
    for (let i = 0; i < items.length; i++) {
      fragment.appendChild(items[i].el);
    }
    const endDiv = layerDiv.querySelector(".endOfContent");
    layerDiv.appendChild(fragment);
    if (endDiv) {
      layerDiv.appendChild(endDiv);
    }
    layerDiv.dataset.launcherSorted = "true";
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

      // 2. Default tool: ALWAYS SELECT (Стрелка) on load, so user is never stuck in Hand mode!
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
            sortTextLayerByColumns(layerDiv);
          }
        } catch (err) {
          console.warn("[Launcher] sortTextLayerByColumns error:", err);
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

      // Check any already rendered text layers on setup
      setTimeout(() => {
        document.querySelectorAll(".textLayer").forEach(sortTextLayerByColumns);
      }, 100);
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
