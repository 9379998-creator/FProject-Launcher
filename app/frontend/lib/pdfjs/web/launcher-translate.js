// Floating translation pill, cursor tool toggle, search match navigation, and scale-lock for Mozilla PDF.js
(function() {
  let tooltip = null;
  let popover = null;

  function initUI() {
    if (tooltip) return;

    // Inject high-contrast match styling and style search findbar
    const style = document.createElement("style");
    style.id = "launcherEnhancedStyles";
    style.textContent = `
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

      /* 1. Make textLayer fully visible so highlight colors are bright and clear */
      .textLayer {
        opacity: 1 !important;
      }
      .textLayer :is(span:not(.highlight), br) {
        color: transparent !important;
      }

      /* 2. All search matches: bright sunshine yellow with contrast border */
      .textLayer .highlight {
        background-color: #ffe600 !important;
        color: #000000 !important;
        opacity: 0.85 !important;
        border-radius: 3px !important;
        box-shadow: 0 0 0 1px #d97706, 0 1px 3px rgba(0, 0, 0, 0.25) !important;
        cursor: pointer !important;
      }

      /* 3. Active / Selected match: glowing electric safety orange with white outline and pulse */
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

      /* 4. Text selection */
      .textLayer ::selection {
        background: #0091ff !important;
        color: #ffffff !important;
      }
    `;
    document.head.appendChild(style);

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

        // Unified Right-Click Context Menu for PDF Viewer
    document.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      const sel = window.getSelection();
      const selectedText = sel ? sel.toString().trim() : "";
      try {
        if (window.parent && window.parent !== window && typeof window.parent.showPdfViewerContextMenu === "function") {
          const frameRect = window.frameElement ? window.frameElement.getBoundingClientRect() : { left: 0, top: 0 };
          window.parent.showPdfViewerContextMenu(
            frameRect.left + event.clientX,
            frameRect.top + event.clientY,
            { selectedText }
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
      document.getElementById("launcherTransRes").textContent = "\u041F\u0435\u0440\u0435\u0432\u043E\u0434\u0438\u043C\u2026";

      fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, target: "ru" }),
      })
        .then((r) => r.json())
        .then((data) => {
          document.getElementById("launcherTransRes").textContent = data.translated || "\u2014";
        })
        .catch((err) => {
          document.getElementById("launcherTransRes").textContent = "\u041E\u0448\u0438\u0431\u043A\u0430: " + err.message;
        });
    };

    window.addEventListener("keydown", (e) => {
      // 1. Escape: dismiss parent context menu first!
      if (e.key === "Escape") {
        try {
          if (window.parent && window.parent !== window && typeof window.parent.hideFileContextMenu === "function") {
            if (window.parent.hideFileContextMenu()) {
              e.preventDefault();
              e.stopPropagation();
              return;
            }
          }
        } catch (_) {}
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
          if (app && app.findBar?.opened) {
            app.findBar.close();
            return;
          }
          if (app && app.secondaryToolbar?.isOpen) {
            app.secondaryToolbar.close();
            return;
          }
        } catch (_) {}
        try {
          if (window.parent && window.parent !== window && typeof window.parent.handleGlobalEscape === "function") {
            window.parent.handleGlobalEscape();
          }
        } catch (_) {}
      }

      // 2. Ctrl+C: copy selected text and show toast
      if ((e.ctrlKey || e.metaKey) && (e.key === "c" || e.key === "C" || e.key === "\u0441" || e.key === "\u0421")) {
        const sel = window.getSelection();
        const text = sel ? sel.toString().trim() : "";
        if (text) {
          try {
            if (window.parent && window.parent !== window && typeof window.parent.copyTextToClipboard === "function") {
              window.parent.copyTextToClipboard(text, "\u0422\u0435\u043A\u0441\u0442 \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D \u0432 \u0431\u0443\u0444\u0435\u0440 \u043E\u0431\u043C\u0435\u043D\u0430");
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

      app.eventBus.on("textlayerrendered", () => {
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
