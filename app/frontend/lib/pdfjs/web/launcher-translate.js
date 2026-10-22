// Floating translation pill, cursor tool toggle, and scale-lock for Mozilla PDF.js
(function() {
  let tooltip = null;
  let popover = null;

  function initUI() {
    if (tooltip) return;

    // Floating Translate Pill button
    tooltip = document.createElement("button");
    tooltip.id = "launcherTransPill";
    tooltip.textContent = "🌐 Перевести";
    tooltip.style.cssText = `
      position: fixed;
      display: none;
      z-index: 999999;
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

    // Translation Popover Card
    popover = document.createElement("div");
    popover.id = "launcherTransCard";
    popover.style.cssText = `
      position: fixed;
      display: none;
      z-index: 1000000;
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

    document.addEventListener("selectionchange", () => {
      const sel = window.getSelection();
      const txt = sel ? sel.toString().trim() : "";
      if (!txt) {
        tooltip.style.display = "none";
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
    });

    tooltip.onclick = async (e) => {
      e.preventDefault();
      e.stopPropagation();
      tooltip.style.display = "none";
      if (!selectedText) return;

      popover.style.display = "block";
      document.getElementById("launcherTransOrig").textContent = selectedText;
      document.getElementById("launcherTransRes").textContent = "Переводим…";

      try {
        const resp = await fetch("/api/translate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: selectedText, target: "ru" }),
        });
        const data = await resp.json();
        document.getElementById("launcherTransRes").textContent = data.translated || "—";
      } catch (err) {
        document.getElementById("launcherTransRes").textContent = "Ошибка: " + err.message;
      }
    };

    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        if (popover && popover.style.display !== "none") {
          popover.style.display = "none";
          return;
        }
        if (tooltip && tooltip.style.display !== "none") {
          tooltip.style.display = "none";
          return;
        }
        try {
          const app = window.PDFViewerApplication;
          if (app && !app.findBar?.opened && !app.secondaryToolbar?.isOpen) {
            if (window.parent && window.parent !== window && typeof window.parent.handleGlobalEscape === "function") {
              window.parent.handleGlobalEscape();
            }
          }
        } catch (_) {}
      }
    });
  }

  function initPdfJsEnhancements() {
    const app = window.PDFViewerApplication;
    if (!app) return;

    let lockedScale = null;
    let isEnforcingScale = false;

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

      // 3. Top toolbar toggle button for Arrow / Hand
      const toolbar = document.getElementById("toolbarViewerMiddle") || document.getElementById("toolbarViewerLeft");
      if (toolbar && !document.getElementById("launcherCursorToggle")) {
        const toggleBtn = document.createElement("button");
        toggleBtn.id = "launcherCursorToggle";
        toggleBtn.className = "toolbarButton";
        toggleBtn.title = "Инструмент: Стрелка (выделение текста) / Лапа (панорамирование)";
        toggleBtn.style.cssText = "font-size:14px; min-width:32px; cursor:pointer; margin-left:6px;";
        toggleBtn.textContent = "↖️";
        toggleBtn.onclick = () => {
          const cur = app.pdfCursorTools?.activeTool;
          const next = cur === 1 ? 0 : 1;
          app.pdfCursorTools?.switchTool(next);
        };
        toolbar.appendChild(toggleBtn);

        app.eventBus.on("cursortoolchanged", (evt) => {
          toggleBtn.textContent = evt.tool === 1 ? "🖐️" : "↖️";
          try {
            if (window.parent && typeof window.parent.updateViewerToolButton === "function") {
              window.parent.updateViewerToolButton(evt.tool === 1);
            }
          } catch (_) {}
        });
      }

      // 4. Freeze initial scale into a fixed numeric scale so page jumps NEVER recalculate zoom
      const freezeCurrentScale = () => {
        const current = app.pdfViewer.currentScale;
        if (current && current > 0) {
          lockedScale = current;
          isEnforcingScale = true;
          app.pdfViewer.currentScaleValue = String(current);
          isEnforcingScale = false;
        }
      };

      app.eventBus.on("pagesloaded", () => {
        if (!lockedScale) {
          freezeCurrentScale();
        }
      });

      // 5. When user zooms in/out manually (buttons, dropdown, or Ctrl+wheel), remember new scale
      app.eventBus.on("scalechanging", (evt) => {
        if (evt && evt.scale && !isEnforcingScale) {
          lockedScale = evt.scale;
        }
      });

      // 6. Enforce lockedScale during search navigation and page jumping
      const enforceLockedScale = () => {
        if (lockedScale && Math.abs(app.pdfViewer.currentScale - lockedScale) > 0.001) {
          isEnforcingScale = true;
          app.pdfViewer.currentScale = lockedScale;
          app.pdfViewer.currentScaleValue = String(lockedScale);
          isEnforcingScale = false;
        }
      };

      app.eventBus.on("pagechanging", enforceLockedScale);
      app.eventBus.on("updatefindcontrolstate", enforceLockedScale);

      app.eventBus.on("find", () => {
        if (!lockedScale && app.pdfViewer.currentScale) {
          lockedScale = app.pdfViewer.currentScale;
        }
        setTimeout(enforceLockedScale, 60);
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
