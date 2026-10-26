// Perf-маяк в DevTools Console (замеры фронта, видны на вкладке Console, F12).
function beaconPerf(label, ms, extra = "") {
  try {
    const text = `[perf] ${label} ${Math.round(ms)}ms ${extra}`.trim();
    if (typeof console !== "undefined" && typeof console.log === "function") console.log(text);
  } catch (_) {}
}

const state = {
  objects: [],
  selectedObjectId: null,
  currentManifest: null,
  activeFilters: new Set(),
  selectedPaths: new Set(),
  lastSelectedIndex: null,
  visibleRows: [],
  collapsedFolders: new Set(),
  progressTimer: null,
  progressCancelled: false,
  renderEpoch: 0,
  activeTxtPath: "",
  operationController: null,
  operationControllers: [],
  renderedPages: [],
  activePageUrl: "",
  activePageKey: "",
  activeNativePath: "",
  appSettings: null,
  revealedPath: "",
  excelWorkbook: null,
  excelWorkbooks: [],
  excelWorkbookIndex: 0,
  excelSheetIndex: 0,
  excelScale: 1,
  wordDoc: null,
  wordDocs: [],
  wordDocIndex: 0,
  wordScale: 1,
  currentToc: null,
  activeTocPath: "",
  highQualityPages: new Map(),
  pdfPairIndex: new Map(),
  pairless: false,
  diffStatus: new Map(),
  diffRemovedNodes: [],
  diffSummary: null,
  diffFilter: false,
  diffPollTimer: null,
  dwgPollTimer: null,
  dwgStatusAbortController: null,

  activeDwgPath: "",
  viewMode: "standard",
  viewerDpi: Number(localStorage.getItem("launcher_viewer_dpi")) || 150,
  activeNavZone: "tree",
  thumbScale: 1,
  treeScale: 1,
  view: {
    scale: 1,
    fitScale: 1,
    rotation: 0,
    userZoomed: false,
    panX: 0,
    panY: 0,
    panMode: true,
    dragging: false,
    dragStartX: 0,
    dragStartY: 0,
    dragPanX: 0,
    dragPanY: 0,
  },
};

const els = {
  shell: document.querySelector(".shell"),
  sidebar: document.getElementById("sidebar"),
  load: document.getElementById("loadObject"),
  refresh: document.getElementById("refreshObject"),
  display: document.getElementById("displayObject"),
  exclude: document.getElementById("excludeObject"),
  cancel: document.getElementById("cancelOperation"),
  progressPanel: document.getElementById("progressPanel"),
  progressLabel: document.getElementById("progressLabel"),
  progressValue: document.getElementById("progressValue"),
  progressFill: document.getElementById("progressFill"),
  progressDetail: document.getElementById("progressDetail"),
  objectListState: document.getElementById("objectListState"),
  treeState: document.getElementById("treeState"),
  objectList: document.getElementById("objectList"),
  objectStats: document.getElementById("objectStats"),
  actionGrid: document.getElementById("actionGrid"),
  backToObjects: document.getElementById("backToObjects"),
  backToTree: document.getElementById("backToTree"),
  treeSearch: document.getElementById("treeSearch"),
  formatStrip: document.getElementById("formatStrip"),
  treeFilterSummary: document.getElementById("treeFilterSummary"),
  objectTree: document.getElementById("objectTree"),
  pdfThumbs: document.getElementById("pdfThumbs"),
  pdfViewer: document.getElementById("pdfViewer"),
  pdfStage: document.getElementById("pdfStage"),
  pdfDocViewer: document.getElementById("pdfDocViewer"),
  pdfDocFrame: document.getElementById("pdfDocFrame"),
  pdfPageImage: document.getElementById("pdfPageImage"),
  txtViewer: document.getElementById("txtViewer"),
  txtContent: document.getElementById("txtContent"),
  mediaVideoViewer: document.getElementById("mediaVideoViewer"),
  excelViewer: document.getElementById("excelViewer"),
  excelBookTitle: document.getElementById("excelBookTitle"),
  excelTabs: document.getElementById("excelTabs"),
  excelTabsLeft: document.getElementById("excelTabsLeft"),
  excelTabsRight: document.getElementById("excelTabsRight"),
  excelSheetFrame: document.getElementById("excelSheetFrame"),
  wordViewer: document.getElementById("wordViewer"),
  wordDocTitle: document.getElementById("wordDocTitle"),
  wordMeta: document.getElementById("wordMeta"),
  wordDocFrame: document.getElementById("wordDocFrame"),
  wordOpenNative: document.getElementById("wordOpenNative"),
  viewerEmpty: document.getElementById("viewerEmpty"),
  viewerControls: document.getElementById("viewerControls"),
  viewBackBtn: document.getElementById("viewBackBtn"),
  qualityBadge: document.getElementById("qualityBadge"),
  pagePosition: document.getElementById("pagePosition"),
  viewToggleTool: document.getElementById("viewToggleTool"),
  viewZoomOut: document.getElementById("viewZoomOut"),
  viewZoomIn: document.getElementById("viewZoomIn"),
  viewFit: document.getElementById("viewFit"),
  viewRotate: document.getElementById("viewRotate"),
  viewToggleDpi: document.getElementById("viewToggleDpi"),
  viewPrevPage: document.getElementById("viewPrevPage"),
  viewNextPage: document.getElementById("viewNextPage"),
  viewToggleToc: document.getElementById("viewToggleToc"),
  viewCopyLink: document.getElementById("viewCopyLink"),
  pdfTocDrawer: document.getElementById("pdfTocDrawer"),
  pdfTocSearch: document.getElementById("pdfTocSearch"),
  pdfTocClose: document.getElementById("pdfTocClose"),
  pdfTocList: document.getElementById("pdfTocList"),
  contextMenu: document.getElementById("contextMenu"),
  scaleWidget: document.getElementById("scaleWidget"),
  scaleResetBtn: document.getElementById("scaleResetBtn"),
  scaleMinusBtn: document.getElementById("scaleMinusBtn"),
  scalePlusBtn: document.getElementById("scalePlusBtn"),
  btnSettings: document.getElementById("btnSettings"),
  settingsModal: document.getElementById("settingsModal"),
  settingsCloseBtn: document.getElementById("settingsCloseBtn"),
  settingsCancelBtn: document.getElementById("settingsCancelBtn"),
  settingsFillEmptyBtn: document.getElementById("settingsFillEmptyBtn"),
  settingsReplaceBtn: document.getElementById("settingsReplaceBtn"),
  settingsOpenWinSettingsBtn: document.getElementById("settingsOpenWinSettingsBtn"),
  settingsDwgHint: document.getElementById("settingsDwgHint"),
  settingsSaveBtn: document.getElementById("settingsSaveBtn"),


};

function text(value, fallback = "") {
  return value == null ? fallback : String(value);
}

function formatExtensions(extensions = {}) {
  const entries = Object.entries(extensions).sort((left, right) => left[0].localeCompare(right[0], "ru"));
  return entries.length ? entries.map(([ext, count]) => `${ext}: ${count}`).join(" · ") : "форматов нет";
}

function selectedObject() {
  return state.objects.find((item) => item.id === state.selectedObjectId) || null;
}

function inTreeMode() {
  return els.treeState.classList.contains("active");
}

function setMode(mode) {
  if (mode === "objects") {
    setViewerMode("standard");
    setStageActive(false);
    els.objectListState.classList.add("active");
    els.treeState.classList.remove("active");
    els.pdfViewer.classList.add("empty");
    if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
    updateViewerBanner('Политика "Локальный компьютер"');
    if (els.backToTree) {
      els.backToTree.disabled = true;
      els.backToTree.title = "Вернуться к предыдущему состоянию дерева";
    }
  } else {
    els.objectListState.classList.remove("active");
    els.treeState.classList.add("active");
    if (els.backToTree) {
      els.backToTree.disabled = false;
    }
  }
  els.shell.classList.toggle("tree-browse", false);
  updateObjectButtons();
}

function inWindow3() {
  return Boolean(state.viewMode === "full" || els.shell?.classList.contains("full-view"));
}

function syncActionGridVisibility() {
  const isWin3 = inWindow3();
  if (els.actionGrid) els.actionGrid.hidden = isWin3;
  document.querySelector(".app-window")?.classList.toggle("in-win3", isWin3);
}

function exitWindow3() {
  if (state.viewMode === "full" || els.shell.classList.contains("full-view")) {
    setViewerMode("standard");
  }
  if (els.pdfViewer?.classList.contains("stage-active")) {
    setStageActive(false);
  }
  if (els.excelViewer) els.excelViewer.hidden = true;
  if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  els.pdfViewer?.classList.remove("empty");
  if (state.wordDocs?.length > 1) {
    renderWordDocumentRail();
  } else if (state.excelWorkbooks?.length > 1) {
    renderExcelWorkbookRail();
  }
  updateObjectButtons();
}

window.exitWindow3 = exitWindow3;

function setTreeBrowseMode(enabled) {
  els.shell.classList.toggle("tree-browse", Boolean(enabled));
}

function updateObjectButtons() {
  syncActionGridVisibility();
  const isWin3 = inWindow3();
  const tree = inTreeMode();
  const hasSelection = Boolean(state.selectedObjectId);

  if (isWin3) {
    // В окне №3 (просмотр документа/чертежа/листа):
    // АКТИВНЫ ТОЛЬКО кнопка «Назад» и масштабы. Все остальные кнопки неактивны.
    if (els.backToTree) {
      els.backToTree.disabled = false;
      els.backToTree.title = "Вернуться в ленту миниатюр (Окно 2) к дереву файлов (Окно 1)";
    }
    if (els.backToObjects) els.backToObjects.disabled = true;
    if (els.load) els.load.disabled = true;
    if (els.refresh) els.refresh.disabled = true;
    if (els.display) els.display.disabled = true;
    if (els.exclude) els.exclude.disabled = true;
    if (els.btnSettings) els.btnSettings.disabled = true;
  } else if (tree) {
    // В первых двух окнах (Окно 1 дерево + Окно 2 лента миниатюр):
    // Кнопка «Назад» неактивна (возвращаться некуда).
    // Кнопка «Объекты» активна (возврат к списку проектов).
    if (els.backToTree) {
      els.backToTree.disabled = true;
      els.backToTree.title = "Кнопка «Назад» неактивна в структуре объекта";
    }
    if (els.backToObjects) {
      els.backToObjects.disabled = false;
      els.backToObjects.title = "Вернуться к списку загруженных объектов";
    }
    if (els.load) els.load.disabled = false;
    if (els.refresh) els.refresh.disabled = false;
    if (els.display) els.display.disabled = false;
    if (els.exclude) els.exclude.disabled = false;
    if (els.btnSettings) els.btnSettings.disabled = false;
  } else {
    // В списке объектов (начальный экран):
    // Кнопка «Назад» неактивна. Кнопка «Объекты» неактивна (уже в объектах).
    if (els.backToTree) {
      els.backToTree.disabled = true;
      els.backToTree.title = "Кнопка «Назад» неактивна на начальном экране";
    }
    if (els.backToObjects) {
      els.backToObjects.disabled = true;
      els.backToObjects.title = "Вы находитесь в списке объектов";
    }
    if (els.load) els.load.disabled = false;
    if (els.refresh) els.refresh.disabled = !hasSelection;
    if (els.display) els.display.disabled = !hasSelection;
    if (els.exclude) els.exclude.disabled = !hasSelection;
    if (els.btnSettings) els.btnSettings.disabled = false;
  }
}

function updateObjectStats() {
  const object = selectedObject();
  if (!object) {
    els.objectStats.textContent = "Объект не выбран";
    return;
  }
  els.objectStats.innerHTML = [
    `<strong>${text(object.name)}</strong>`,
    `Папок: ${object.statistics?.folders || 0}`,
    `Файлов: ${object.statistics?.files || 0}`,
    formatExtensions(object.statistics?.extensions || {}),
    text(object.rootPath),
  ].join("<br>");
}

function renderObjectList() {
  els.objectList.replaceChildren();
  if (!state.objects.length) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "Объекты ещё не загружены.";
    els.objectList.append(empty);
    updateObjectStats();
    updateObjectButtons();
    return;
  }

  state.objects.forEach((object) => {
    const row = document.createElement("div");
    row.className = "object-row";
    row.dataset.objectId = object.id;
    row.classList.toggle("selected", object.id === state.selectedObjectId);
    row.title = object.rootPath;

    const main = document.createElement("div");
    main.className = "object-main";

    const icon = document.createElement("span");
    icon.className = "object-icon";
    icon.innerHTML = `<svg viewBox="0 0 16 16" width="15" height="15" fill="#f59e0b"><path d="M1.5 3A1.5 1.5 0 0 0 0 4.5v7A1.5 1.5 0 0 0 1.5 13h13a1.5 1.5 0 0 0 1.5-1.5v-5A1.5 1.5 0 0 0 14.5 5H7.707L6.354 3.646A1.5 1.5 0 0 0 5.293 3.207L1.5 3z"/></svg>`;

    const title = document.createElement("span");
    title.className = "object-title";
    title.textContent = object.name;

    const badge = document.createElement("span");
    badge.className = "object-badge";
    badge.textContent = `(${object.statistics?.files || 0})`;

    main.append(icon, title, badge);

    row.append(main);
    row.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showFileContextMenu(event.clientX, event.clientY, {
        path: object.rootPath,
        isDir: true,
        ext: "",
      });
    });

    row.addEventListener("click", (event) => {
      event.stopPropagation();
      state.selectedObjectId = state.selectedObjectId === object.id ? null : object.id;
      updateObjectListSelection();
      updateObjectButtons();
      updateObjectStats();
      if (state.selectedObjectId) {
        updateViewerBanner(object.name);
      } else {
        updateViewerBanner('Политика "Локальный компьютер"');
      }
    });
    row.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      state.selectedObjectId = object.id;
      updateObjectListSelection();
      updateObjectButtons();
      updateObjectStats();
      openSelectedObject().catch(showOperationError);
    });
    els.objectList.append(row);
  });
  updateObjectStats();
  updateObjectButtons();
}

function updateObjectListSelection() {
  [...els.objectList.querySelectorAll(".object-row")].forEach((row) => {
    row.classList.toggle("selected", row.dataset.objectId === state.selectedObjectId);
  });
}

async function loadObjectSummaries() {
  const response = await fetch("/api/objects");
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Список объектов не получен");
  state.objects = payload.items || [];
  if (state.selectedObjectId && !state.objects.some((item) => item.id === state.selectedObjectId)) {
    state.selectedObjectId = null;
  }
  renderObjectList();
}

function createOperationController() {
  if (state.operationController) state.operationController.abort();
  state.operationController = new AbortController();
  return state.operationController;
}

function startProgress(label, detail) {
  stopProgress(false, false);
  state.progressCancelled = false;
  els.progressFill.classList.remove("is-error");
  els.progressPanel.hidden = false;
  els.progressLabel.textContent = label;
  els.progressDetail.textContent = detail;
  els.progressValue.textContent = "0%";
  els.progressFill.style.width = "0%";
  // Полоса движется всегда, пока идёт операция: пакетные циклы выставляют
  // state.progressEase { base, spent0, estMs } — оценку оставшегося времени,
  // тик плавно тянет шкалу к 99 по elapsed/ETA (мёртвой зоны на 92 нет).
  // Реальные завершения выставляют точные цифры через refreshRenderProgress.
  // Строка деталей всегда честная (счётчики файлов/пачек), плюс CSS-пульс.
  state.progressShown = 0;
  state.progressEase = null;
  els.progressFill.classList.add("is-busy");
  state.progressTimer = setInterval(() => {
    if (state.progressCancelled) return;
    const ease = state.progressEase;
    let target;
    if (ease && ease.estMs > 0) {
      const spent = Date.now() - ease.spent0;
      target = ease.base + (99 - ease.base) * (spent / (spent + ease.estMs));
    } else {
      // Без оценки времени полоска медленно ползёт к 99 и не замирает на 92.
      target = Math.min(99, (state.progressShown || 0) + 0.4);
    }
    state.progressShown = Math.max(state.progressShown, Math.min(99, target));
    els.progressValue.textContent = `${Math.floor(state.progressShown)}%`;
    els.progressFill.style.width = `${state.progressShown}%`;
  }, 500);
}

// Оценка оставшегося времени пачки по измеренной скорости (мс).
// До первых завершений — дефолт 10 с/файл (облако), минимум 5 с.
function estimateBatchRemainMs(elapsedMs, doneFiles, totalFiles) {
  const remaining = Math.max(0, totalFiles - doneFiles);
  if (remaining <= 0) return 0;
  const perFile = doneFiles > 0 ? elapsedMs / doneFiles : 10000;
  return Math.min(600000, Math.max(5000, perFile * remaining));
}

function finishProgress(detail = "Готово") {
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  state.progressEase = null;
  state.operationController = null;
  els.progressFill.classList.remove("is-busy");
  els.progressDetail.textContent = detail;
  els.progressValue.textContent = "100%";
  els.progressFill.style.width = "100%";
  setTimeout(() => {
    if (!state.progressTimer) els.progressPanel.hidden = true;
  }, 1200);
}

function stopProgress(cancelled = true, abortRequest = true) {
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  state.progressEase = null;
  stopDwgStatusPolling();
  els.progressFill.classList.remove("is-busy");
  state.progressCancelled = cancelled;
  if (abortRequest) {
    if (state.operationController) {
      try { state.operationController.abort(); } catch (_) {}
      state.operationController = null;
    }
    if (state.operationControllers?.length) {
      state.operationControllers.forEach((controller) => {
        try { controller.abort(); } catch (_) {}
      });
      state.operationControllers = [];
    }
  }
  els.progressPanel.hidden = true;
  if (cancelled) {
    els.progressFill.style.width = "0%";
    els.progressValue.textContent = "";
    if (state._ribbonScrollObserver) {
      state._ribbonScrollObserver.disconnect();
      state._ribbonScrollObserver = null;
    }
    // Отмена возвращает в нейтральное состояние: снимаем выделение и фильтры,
    // чтобы не оставалось залипшей подсветки и следующий показ шёл с чистого листа.
    state.selectedPaths.clear();
    state.activeFilters.clear();
    state.revealedPath = "";
    renderFormats();
    renderTree();
  }
}

function stopDwgStatusPolling() {
  if (state.dwgPollTimer) {
    clearInterval(state.dwgPollTimer);
    state.dwgPollTimer = null;
  }
  if (state.dwgStatusAbortController) {
    try {
      state.dwgStatusAbortController.abort();
    } catch (_) {}
    state.dwgStatusAbortController = null;
  }
  state.activeDwgPath = "";
}

function startDwgStatusPolling(filePath, totalPages, epoch) {
  stopDwgStatusPolling();
  if (!filePath) return;
  state.activeDwgPath = filePath;
  // Счётчики живут в state и переживали переключение файлов: остаток от прошлого
  // чертежа сразу приближал обрыв опроса на новом. Сбрасываем на каждый старт.
  state._dwgNoWorkerCount = 0;
  state._dwgStatusErrors = 0;
  const pollController = new AbortController();
  state.dwgStatusAbortController = pollController;
  const pollStartedAt = Date.now();
  let pollInFlight = false;

  state.dwgPollTimer = setInterval(async () => {
    if (pollInFlight) return;
    if (state.renderEpoch !== epoch || state.progressCancelled || state.activeDwgPath !== filePath || pollController.signal.aborted) {
      stopDwgStatusPolling();
      return;
    }
    if (Date.now() - pollStartedAt > 15 * 60 * 1000) {
      stopDwgStatusPolling();
      showNotice("Рендеринг листов DWG занимает слишком долго - опрос остановлен.");
      return;
    }
    pollInFlight = true;
    try {
      const resp = await fetch("/api/dwg/status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: filePath }),
        signal: pollController.signal,
      });
      if (state.renderEpoch !== epoch || state.progressCancelled || state.activeDwgPath !== filePath || pollController.signal.aborted) {
        stopDwgStatusPolling();
        return;
      }
      if (!resp.ok) {
        if (resp.status >= 400) {
          // Одиночный сбой статуса не должен убивать опрос: пока идёт рендер,
          // сервер может быть занят и вернуть 4xx/5xx. Даём запас попыток,
          // иначе готовый HD-лист никогда не подхватится.
          state._dwgStatusErrors = (state._dwgStatusErrors || 0) + 1;
          if (state._dwgStatusErrors >= 20) {
            stopDwgStatusPolling();
            showOperationError(new Error(`Ошибка сервера при проверке статуса DWG (HTTP ${resp.status})`));
          }
        }
        return;
      }
      state._dwgStatusErrors = 0;
      const data = await resp.json();
      if (state.renderEpoch !== epoch || state.progressCancelled || state.activeDwgPath !== filePath) {
        stopDwgStatusPolling();
        return;
      }
      if (data.status === "error" || data.error) {
        stopDwgStatusPolling();
        showOperationError(new Error(data.error || "Ошибка рендеринга DWG"));
        return;
      }

      const readyPages = data.readyPages || [];
      const readySet = new Set(readyPages);
      const total = data.totalLayouts || totalPages || readyPages.length;

      // Отображаем живой прогресс рендеринга для пользователя
      if (total > 0 && readyPages.length < total) {
        if (data.workerActive === false) {
          if (!state._dwgNoWorkerCount) state._dwgNoWorkerCount = 0;
          state._dwgNoWorkerCount++;
          // 4 секунды — слишком мало: accoreconsole поднимается и копирует DWG
          // дольше, а в это время workerActive ещё false. Даём ~12 с запаса,
          // прежде чем считать, что рендер действительно встал.
          if (state._dwgNoWorkerCount >= 12) {
            finishProgress(`Готово ${readyPages.length} из ${total} листов`);
            stopDwgStatusPolling();
            return;
          }
        } else {
          state._dwgNoWorkerCount = 0;
        }

        els.progressLabel.textContent = "Рендеринг листов DWG";
        els.progressValue.textContent = `${readyPages.length}/${total}`;
        els.progressDetail.textContent = `Готово ${readyPages.length} из ${total} листов · AutoCAD отрисовывает следующий лист…`;
        els.progressFill.style.width = `${Math.max(5, Math.round((readyPages.length / total) * 100))}%`;
        els.progressFill.classList.add("is-busy");
        els.progressPanel.hidden = false;
      }

      const emptyPages = data.emptyPages || [];
      const emptySet = new Set(emptyPages);

      // Обновляем миниатюры в ленте (сопоставляем по cacheKey и номеру листа)
      const thumbs = els.pdfThumbs?.querySelectorAll(".pdf-thumb") || [];
      thumbs.forEach((thumb) => {
        const img = thumb.querySelector("img");
        if (!img) return;
        const pageNum = parseInt(thumb.dataset.pageNumber || (img.getAttribute("src") || "").match(/page-(\d+)\.png/)?.[1] || "0", 10);
        if (!pageNum) return;
        const src = img.getAttribute("src") || "";
        if (!src.includes(data.cacheKey) && !src.includes("dwg/")) return;
        if (readySet.has(pageNum)) {
          if (img.dataset.dwgLoaded !== "1" || src.includes(".svg") || src.includes("header_thumb.png") || img.naturalWidth <= 300) {
            img.dataset.dwgLoaded = "1";
            img.src = `/cache/dwg/${data.cacheKey}/page-${pageNum}.png?v=${Date.now()}`;
          }
          thumb.classList.toggle("is-empty-dwg-sheet", emptySet.has(pageNum));
        }
      });

      // Обновляем главное изображение на сцене, если открыт этот чертёж и данный лист готов
      if (els.pdfPageImage) {
        const stageSrc = els.pdfPageImage.getAttribute("src") || "";
        if (stageSrc.includes(data.cacheKey) || stageSrc.includes("dwg/")) {
          const activeMatch = stageSrc.match(/page-(\d+)\.png/);
          let activePageNum = activeMatch ? parseInt(activeMatch[1], 10) : null;
          if (!activePageNum && (stageSrc.includes("header_thumb.png") || stageSrc.includes("placeholder"))) {
            const activeP = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey);
            activePageNum = Number(activeP?.page) || 1;
          }
          if (activePageNum && readySet.has(activePageNum)) {
            const marker = `${data.cacheKey}|${activePageNum}`;
            const isDraft = stageSrc.includes("header_thumb.png") || stageSrc.includes("placeholder");
            if (els.pdfPageImage.dataset.dwgLoadedPage !== marker || els.pdfPageImage.naturalWidth <= 300 || isDraft) {
              els.pdfPageImage.dataset.dwgLoadedPage = marker;
              const newUrl = `/cache/dwg/${data.cacheKey}/page-${activePageNum}.png?v=${Date.now()}`;
              state.activePageUrl = newUrl;
              els.pdfPageImage.onload = () => {
                applyPageView();
              };
              els.pdfPageImage.src = newUrl;
            }
          }
        }
      }

      // Отмечаем готовность страниц в массиве состояния
      if (state.renderedPages?.length) {
        state.renderedPages.forEach((p) => {
          const docPath = p.documentPath || p.sourcePath || p.previewFor?.path || p.path || "";
          if (docPath === filePath && readySet.has(Number(p.page))) {
            p.bytes = Math.max(p.bytes || 0, 1024);
            p.isEmpty = emptySet.has(Number(p.page));
            p.url = `/cache/dwg/${data.cacheKey}/page-${p.page}.png`;
          }
        });
      }

      // Если текущий открытый лист пустой (например, Лист 1 - просто рамка без чертежа),
      // а в файле обнаружен лист с реальным чертежом (firstContentPage), и пользователь
      // еще сам вручную не выбирал конкретный лист — автоматически переключаем на лист с чертежом!
      if (!state._userNavigatedDwgPage && data.firstContentPage && data.firstContentPage > 0) {
        const activeP = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey);
        const activePageNum = Number(activeP?.page) || 1;
        if (activeP && activeP.isEmpty && activePageNum !== data.firstContentPage) {
          const contentP = state.renderedPages?.find((p) => {
            const pDoc = p.documentPath || p.sourcePath || p.previewFor?.path || p.path || "";
            return pDoc === filePath && Number(p.page) === data.firstContentPage;
          });
          if (contentP) {
            showPdfPage(contentP);
            const contentThumb = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-number="${data.firstContentPage}"]`);
            if (contentThumb) {
              contentThumb.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
            }
          }
        }
      }

      // Обновляем индикатор позиции/разрешения в шапке
      const activeP = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey);
      if (activeP) {
        updatePagePosition(activeP);
      }

      // Если все листы отрендерены — завершаем опрос и скрываем прогресс
      if (data.isComplete || (total > 0 && readyPages.length >= total)) {
        finishProgress(`Готово: все ${total} листов чертежа отрендерены`);
        stopDwgStatusPolling();
      }
    } catch (err) {
      if (err?.name === "AbortError") return;
      console.warn("DWG status poll error:", err);
    } finally {
      pollInFlight = false;
    }
  }, 1500);
}

function showOperationError(error) {
  if (error?.name === "AbortError") return;
  // Never disguise a failed render as a completed 100% operation.  Keep the
  // factual error on screen long enough for both the user and QA to see it.
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  state.operationController = null;
  els.progressLabel.textContent = "Операция не выполнена";
  els.progressDetail.textContent = `Ошибка: ${error.message || error}`;
  els.progressValue.textContent = "Ошибка";
  els.progressFill.style.width = "100%";
  els.progressFill.classList.add("is-error");
  setTimeout(() => {
    if (!state.progressTimer) {
      els.progressPanel.hidden = true;
      els.progressFill.classList.remove("is-error");
    }
  }, 8000);
}

// Non-blocking warning (not an error): shows why a command may have silently
// misbehaved, e.g. a Windows long-path limit, without failing the operation.
function showNotice(message) {
  if (state.progressTimer) clearInterval(state.progressTimer);
  state.progressTimer = null;
  els.progressFill.classList.remove("is-busy");
  els.progressLabel.textContent = "Предупреждение";
  els.progressDetail.textContent = message;
  els.progressValue.textContent = "";
  els.progressFill.style.width = "100%";
  els.progressPanel.hidden = false;
  setTimeout(() => {
    if (!state.progressTimer) {
      els.progressPanel.hidden = true;
    }
  }, 9000);
}



function getNativeAppLabel(ext = "") {
  const custom = settingsCustomExe(ext);
  if (custom) {
    const filename = custom.split(/[\\/]/).pop();
    const base = filename.replace(/\.exe$/i, "");
    const baseLower = base.toLowerCase();
    if (baseLower === "acad") return "AutoCAD";
    if (baseLower.includes("trueview")) return "DWG TrueView";
    if (baseLower === "chrome") return "Google Chrome";
    if (baseLower === "msedge") return "Microsoft Edge";
    if (baseLower === "winword") return "Word";
    if (baseLower === "excel") return "Excel";
    if (baseLower === "powerpnt") return "PowerPoint";
    if (baseLower === "acrobat" || baseLower === "acrord32") return "Adobe Acrobat";
    if (baseLower === "vlc") return "VLC";
    if (baseLower === "mspaint") return "Paint";
    if (baseLower === "notepad") return "Блокнот";
    return base;
  }
  const e = String(ext).toUpperCase().replace(/^\./, "");
  switch (e) {
    case "DWG":
    case "DXF": return "AutoCAD / DWG";
    case "PDF": return "PDF-просмотрщике";
    case "DOC":
    case "DOCX":
    case "RTF":
    case "ODT": return "Word";
    case "XLS":
    case "XLSX":
    case "XLSM":
    case "XLSB":
    case "CSV":
    case "ODS": return "Excel";
    case "PPT":
    case "PPTX":
    case "ODP": return "PowerPoint";
    case "JPG":
    case "JPEG":
    case "PNG":
    case "BMP":
    case "WEBP":
    case "SVG":
    case "TIF":
    case "TIFF":
    case "GIF":
    case "ICO": return "Просмотре фото";
    case "MP4":
    case "AVI":
    case "MOV":
    case "MKV":
    case "WMV":
    case "MP3":
    case "WAV": return "Медиаплеере";
    case "ZIP":
    case "RAR":
    case "7Z":
    case "TAR":
    case "GZ": return "Архиваторе";
    case "TXT":
    case "LOG":
    case "INI":
    case "CFG":
    case "JSON":
    case "XML": return "Блокноте";
    default: return e ? `${e}` : "программе";
  }
}


let isOpeningFile = false;
let lastOpenedPath = "";
let lastOpenedTime = 0;

async function openFileByPath(path, action) {
  if (!path) return;
  const now = Date.now();
  if (isOpeningFile && (now - lastOpenedTime < 3500)) {
    console.warn("[Launcher] openFileByPath ignored: already in progress", path);
    showToast("Файл уже открывается…");
    return;
  }
  if (lastOpenedPath === path && (now - lastOpenedTime < 3500)) {
    console.warn("[Launcher] openFileByPath ignored: rapid repeat call for same path", path);
    showToast("Файл уже открывается…");
    return;
  }
  isOpeningFile = true;
  lastOpenedPath = path;
  lastOpenedTime = now;

  const act = String(action || "explorer");
  let actLabel = "Проводнике Windows";
  if (act === "system" || act === "native") {
    actLabel = "программе по умолчанию";
  }
  showToast("Запуск в " + actLabel + "…");
  try {
    const response = await fetch("/api/open-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path, action: act }),
    });
    const payload = await response.json();
    if (!response.ok) {
      if (payload.error_code === "configured_app_missing") {
        const ext = (payload.details && payload.details.extension)
          ? payload.details.extension.toUpperCase().replace(".", "")
          : "DWG";
        const msg = `Для файлов ${ext} указано недоступное приложение. Проверьте Параметры → Приложения.`;
        showNotice(msg);
        showToast(msg);
        openSettingsModal(payload.details && payload.details.extension);
        return;
      }
      throw new Error(payload.error || "Не удалось открыть файл");
    }
    showToast("Файл запущен: " + actLabel);
    if (payload.longPathWarning) showNotice(payload.longPathWarning);
  } catch (error) {
    console.error("[Launcher] Failed to open file:", error);
    showOperationError(error);
  } finally {
    setTimeout(() => {
      isOpeningFile = false;
    }, 2500);
  }
}

function escapeHtml(value = "") {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

let isPickerOpen = false;

async function triggerSystemPicker() {
  // Единственный механизм загрузки: системный диалог выбора папки Windows.
  // Никаких самописных окон, прогресса, HTML-ответов и «запросов к агенту»:
  // один клик -> одно окно FolderBrowserDialog -> importObjectByPath.
  if (isPickerOpen) return "";
  isPickerOpen = true;
  if (els.load) els.load.disabled = true;
  try {
    const res = await fetch("/api/choose-folder", {
      method: "POST",
      headers: { Accept: "application/json" },
    });
    const contentType = res.headers.get("content-type") || "";
    if (!contentType.includes("application/json")) {
      throw new Error("Сервер вернул не JSON при выборе папки");
    }
    const data = await res.json();
    if (data && data.path) {
      await importObjectByPath(data.path);
      return data.path;
    }
    if (data && data.error) {
      showOperationError(new Error(data.error));
    }
    return "";
  } catch (err) {
    showOperationError(err);
    return "";
  } finally {
    isPickerOpen = false;
    updateObjectButtons();
  }
}

async function importObjectByPath(path, forceRefresh = false) {
  if (!path || !path.trim()) return;
  const controller = createOperationController();
  startProgress(forceRefresh ? "Обновление объекта" : "Загрузка объекта", path);
  state.progressEase = {
    base: 8,
    spent0: Date.now(),
    estMs: 120000,
  };
  try {
    const response = await fetch("/api/objects/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path: path.trim() }),
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Объект не загружен");
    if (state.progressCancelled) return;
    state.selectedObjectId = payload.id;
    await loadObjectSummaries();
    setMode("objects");
    updateObjectButtons();
    updateObjectStats();
    finishProgress(forceRefresh ? "Объект обновлён" : "Объект загружен");
  } catch (error) {
    showOperationError(error);
  }
}

async function importObject(forceRefresh = false) {
  if (forceRefresh) {
    const object = selectedObject();
    if (object?.rootPath) {
      await importObjectByPath(object.rootPath, true);
    }
    return;
  }
  // Единственный сценарий: системный диалог выбора папки Windows.
  await triggerSystemPicker().catch((err) => {
    showOperationError(err);
  });
}


async function excludeSelectedObject() {
  const object = selectedObject();
  if (!object) return;
  const controller = createOperationController();
  startProgress("Исключение объекта", object.name);
  const response = await fetch("/api/objects/exclude", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id: object.id }),
    signal: controller.signal,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Объект не исключён");
  state.selectedObjectId = null;
  state.currentManifest = null;
  await loadObjectSummaries();
  finishProgress("Объект исключён");
}

function getCachedFlatNodes() {
  if (!state.currentManifest?.tree) return [];
  if (!state.currentManifest._flatNodes) {
    state.currentManifest._flatNodes = flattenTree(state.currentManifest.tree);
  }
  return state.currentManifest._flatNodes;
}

function flattenTree(rootNode, result = []) {
  if (!rootNode) return result;
  const stack = [rootNode];
  const seen = new Set();
  while (stack.length) {
    const node = stack.pop();
    if (!node) continue;
    const key = node.path || node;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(node);
    const children = node.children;
    if (children && children.length) {
      for (let i = children.length - 1; i >= 0; i--) {
        stack.push(children[i]);
      }
    }
  }
  return result;
}

function fileStem(name = "") {
  const value = String(name);
  const dotIndex = value.lastIndexOf(".");
  return dotIndex > 0 ? value.slice(0, dotIndex) : value;
}

function normalizePairName(name = "") {
  return fileStem(name)
    .toLocaleLowerCase("ru")
    .replace(/ё/g, "е")
    .replace(/\b(?:ap|ar)\s*(?=\d)/g, "ар")
    .replace(/ар\s*(?=\d)/g, "ар ")
    .replace(/проеомв/g, "проемов")
    .replace(/срп\s*[_-]?\s*7/g, " ")
    .replace(/лист/g, " ")
    .replace(/[+]/g, " ")
    .replace(/[_\-.()[\]{},]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function pairTokens(name = "") {
  return normalizePairName(name)
    .split(" ")
    .map((token) => token.trim())
    .filter((token) => token.length > 1)
    .filter((token) => !["срп", "для", "всех", "отм", "осях", "оси", "на"].includes(token));
}

function escapeRegExp(value = "") {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function extractCodeParts(normalized = "") {
  const codeMatch = normalized.match(/(?:^|\s)ар\s*(\d)\s+(\d)\s+(\d)(?=\s|$)/u)
    || normalized.match(/(?:^|\s)ар\s*(\d)\s+(\d)(?=\s|$)/u);
  return codeMatch ? codeMatch.slice(1).filter(Boolean) : [];
}

function stripPairServiceNoise(normalized = "") {
  let value = normalized
    .replace(/\bсрп\s*7\b/g, " ")
    .replace(/\bлист\b/g, " ");
  const codeParts = extractCodeParts(value);
  if (codeParts.length) {
    const codePattern = new RegExp(`(?:^|\\s)ар\\s*${codeParts.map(escapeRegExp).join("\\s+")}(?=\\s|$)`, "g");
    value = value.replace(codePattern, " ");
  }
  return value
    .replace(/\b50\s+\d{1,3}\b/g, " ")
    .replace(/^\s*\d{1,3}\s+/, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function stemPairToken(token = "") {
  if (token.length <= 4) return token;
  return token.replace(/(иями|ями|ами|ого|его|ому|ему|ыми|ими|ых|их|ая|яя|ое|ее|ые|ие|ый|ий|ой|ую|юю|ом|ем|ах|ях|ов|ев|ей|ам|ям|а|я|ы|и|е|у|ю|о)$/u, "");
}

function semanticPairTokens(normalized = "") {
  return stripPairServiceNoise(normalized)
    .split(" ")
    .map((token) => stemPairToken(token.trim()))
    .filter((token) => token.length > 1)
    .filter((token) => !["срп", "для", "всех", "отм", "осях", "оси", "на"].includes(token));
}

function tokenBigrams(tokens = []) {
  const result = new Set();
  for (let index = 0; index < tokens.length - 1; index += 1) {
    result.add(`${tokens[index]} ${tokens[index + 1]}`);
  }
  return result;
}

function longestCommonRun(left, right) {
  if (!left?.length || !right?.length) return 0;
  let best = 0;
  const previous = new Array(right.length + 1).fill(0);
  const current = new Array(right.length + 1).fill(0);
  for (let leftIndex = 1; leftIndex <= left.length; leftIndex += 1) {
    for (let rightIndex = 1; rightIndex <= right.length; rightIndex += 1) {
      current[rightIndex] = left[leftIndex - 1] === right[rightIndex - 1] ? previous[rightIndex - 1] + 1 : 0;
      if (current[rightIndex] > best) best = current[rightIndex];
    }
    previous.splice(0, previous.length, ...current);
    current.fill(0);
  }
  return best;
}

function pairFingerprint(name = "") {
  const normalized = normalizePairName(name);
  const codeParts = extractCodeParts(normalized);
  const code = codeParts.length ? `ар${codeParts.join(".")}` : "";
  const sheetMatch = normalized.match(/\b50\s+(\d{1,3})\b/);
  const sheet = sheetMatch ? String(Number(sheetMatch[1])) : "";
  const codeNumberPattern = codeParts.length
    ? new RegExp(`(?:^|\\s)ар\\s*${codeParts.join("\\s+")}\\s+(\\d{1,3})(?=\\s|$)`, "u")
    : /(?:^|\s)ар\s*(?:\d\s*)+\s+(\d{1,3})(?=\s|$)/u;
  const codeNumberMatch = normalized.match(codeNumberPattern);
  const codeNumber = codeNumberMatch ? String(Number(codeNumberMatch[1])) : "";
  const detailMatches = [...normalized.matchAll(/(?:^|\s)(узел|сечение|часть)\s+([a-zа-я0-9]+(?:\s*[-–]\s*[a-zа-я0-9]+)?)(?=\s|$)/gu)]
    .map((match) => `${match[1]} ${match[2].replace(/\s+/g, "")}`);
  const details = new Set(detailMatches);
  const floorMatch = normalized.match(/\b(\d+\s*[-–]\s*\d+|\d+)\s+(?:го\s+)?этаж/u);
  const floor = floorMatch ? floorMatch[1].replace(/\s+/g, "") : "";
  const technical = /техническ|тех\s*пространств/u.test(normalized);
  const types = new Set();
  if (/маркировочный\s+план/u.test(normalized)) types.add("маркировочный план");
  if (/общие\s+данные/u.test(normalized)) types.add("общие данные");
  if (/ведомост/u.test(normalized) && /отделк/u.test(normalized)) types.add("ведомость отделки");
  if (/экспликац/u.test(normalized) && /полов/u.test(normalized)) types.add("экспликация полов");
  if (/схем/u.test(normalized) && /двер/u.test(normalized)) types.add("схемы дверей");
  if (/колористическ/u.test(normalized)) types.add("колористическое решение");
  if (/фасад/u.test(normalized)) types.add("фасад");
  const axisTokens = new Set([...normalized.matchAll(/\b7\s+2\s+[0-9а-я]+\b/gu)].map((match) => match[0].replace(/\s+/g, ".")));
  const tokens = new Set(pairTokens(name));
  const semanticText = stripPairServiceNoise(normalized);
  const semanticTokensList = semanticPairTokens(normalized);
  const semanticTokensSet = new Set(semanticTokensList);
  return {
    normalizedName: normalized,
    semanticText,
    semanticTokensList,
    semanticTokensSet,
    semanticBigrams: tokenBigrams(semanticTokensList),
    code,
    sheet: sheet || codeNumber,
    details,
    floor,
    technical,
    types,
    axisTokens,
    tokens,
  };
}

function buildPdfPairIndex(nodes) {
  const list = [];
  const byName = new Map();
  for (const node of nodes) {
    if (node.type === "file" && node.extension === "PDF") {
      const normalizedName = normalizePairName(node.name || "");
      const entry = {
        node,
        normalizedName,
        _fingerprint: null,
        get fingerprint() {
          if (!this._fingerprint) {
            this._fingerprint = pairFingerprint(this.node.name);
          }
          return this._fingerprint;
        },
      };
      list.push(entry);
      if (normalizedName) {
        let arr = byName.get(normalizedName);
        if (!arr) {
          arr = [];
          byName.set(normalizedName, arr);
        }
        arr.push(entry);
      }
    }
  }
  list.byName = byName;
  return list;
}

// Сколько хвостовых сегментов папок совпадает у DWG и кандидата PDF.
// DVG/5.1/КМД/x.dwg + PDF/5.1/КМД/x.pdf → 2, чужой каталог → 0.
function mirrorScore(dwgPath = "", pdfPath = "") {
  const dw = String(dwgPath).replace(/\//g, "\\").toLowerCase().split("\\").slice(0, -1);
  const pf = String(pdfPath).replace(/\//g, "\\").toLowerCase().split("\\").slice(0, -1);
  let score = 0;
  while (score < dw.length && score < pf.length
    && dw[dw.length - 1 - score] === pf[pf.length - 1 - score]) {
    score += 1;
  }
  return score;
}

// Общий бюджет нечёткого сопоставления DWG→PDF (мс) на один проход
// подбора превью. Полный перебор на объекте вида «2687 DWG × 6195 PDF» —
// это ~16 млн сравнений ≈ 9 минут мёртвого окна (замер 20:32, объект 03_ЖК МОД).
const PAIR_FUZZY_BUDGET_MS = 2500;
let pairFuzzyBudgetUntil = Infinity;

function intersectionSize(left, right) {
  let count = 0;
  for (const item of left) {
    if (right.has(item)) count += 1;
  }
  return count;
}

function comparePairFingerprints(dwg, pdf) {
  if (dwg.normalizedName === pdf.normalizedName) return { score: 100, confidence: "exact" };
  if (dwg.code && pdf.code && dwg.code !== pdf.code) return null;
  const detailOverlap = intersectionSize(dwg.details, pdf.details);
  if (dwg.details.size && pdf.details.size && detailOverlap === 0) return null;

  let score = 0;
  if (dwg.code && pdf.code && dwg.code === pdf.code) score += 32;
  if (dwg.sheet && pdf.sheet && dwg.sheet === pdf.sheet) score += 8;
  if (dwg.sheet && pdf.sheet && dwg.sheet !== pdf.sheet) score -= 4;
  if (detailOverlap) score += 34;
  if (dwg.floor && pdf.floor && dwg.floor === pdf.floor) score += 28;
  if (dwg.technical && pdf.technical) score += 28;

  const typeOverlap = intersectionSize(dwg.types, pdf.types);
  score += typeOverlap * 16;

  const axisOverlap = intersectionSize(dwg.axisTokens, pdf.axisTokens);
  score += Math.min(18, axisOverlap * 6);

  const sharedTokens = intersectionSize(dwg.tokens, pdf.tokens);
  const tokenRatio = sharedTokens / Math.max(dwg.tokens.size, pdf.tokens.size, 1);
  score += Math.round(tokenRatio * 28);

  const semanticOverlap = intersectionSize(dwg.semanticTokensSet, pdf.semanticTokensSet);
  const semanticRatio = semanticOverlap / Math.max(dwg.semanticTokensSet.size, pdf.semanticTokensSet.size, 1);
  score += Math.round(semanticRatio * 46);

  const bigramOverlap = intersectionSize(dwg.semanticBigrams, pdf.semanticBigrams);
  score += Math.min(36, bigramOverlap * 12);

  const commonRun = longestCommonRun(dwg.semanticTokensList, pdf.semanticTokensList);
  if (commonRun >= 5) score += 42;
  else if (commonRun >= 4) score += 32;
  else if (commonRun >= 3) score += 22;

  const commonSubstring = longestCommonRun(dwg.semanticText, pdf.semanticText);
  if (commonSubstring >= 32) score += 32;
  else if (commonSubstring >= 22) score += 22;
  else if (commonSubstring >= 16) score += 12;

  if (dwg.semanticText && pdf.semanticText && dwg.semanticText === pdf.semanticText) score += 52;

  const hasSemanticAnchor = Boolean(
    detailOverlap
    || (dwg.floor && pdf.floor && dwg.floor === pdf.floor)
    || (dwg.technical && pdf.technical)
    || typeOverlap >= 1
    || axisOverlap >= 2
    || semanticRatio >= 0.5
    || bigramOverlap >= 1
    || commonRun >= 3
    || commonSubstring >= 22
  );
  if (!hasSemanticAnchor && score < 82) return null;
  if (score < 68) return null;
  return { score, confidence: score >= 78 ? "strong" : "probable" };
}

function findPdfPairForDwg(dwgNode, pdfIndex, options = {}) {
  if (!dwgNode || dwgNode.extension !== "DWG") return null;
  const list = Array.isArray(pdfIndex) ? pdfIndex : [];
  if (!list.length) return null;
  // Точное имя ищется по всему объекту, папка не важна:
  // пара обычно в соседней папке PDF. Среди тёзок — зеркальный путь.
  const key = normalizePairName(dwgNode.name || "");
  const candidates = (key && pdfIndex?.byName?.get(key)) || [];
  if (candidates.length) {
    let pick = candidates[0];
    if (candidates.length > 1) {
      let bestScore = -1;
      for (const cand of candidates) {
        const sc = mirrorScore(dwgNode.path, cand.node?.path);
        if (sc > bestScore) { bestScore = sc; pick = cand; }
      }
    }
    return { node: pick.node, score: 100, confidence: "exact" };
  }
  // Массовый показ: только точные пары (быстро и детерминированно).
  // Нечёткий поиск оставлен одиночным файлам — там он занимает ~0,2 с.
  if (options.fuzzy === false) return null;
  const dwgFingerprint = pairFingerprint(dwgNode.name);
  // Нечёткий поиск — в пределах общего бюджета. Когда бюджет исчерпан
  // (гигантский объект), возвращаем лучшее из найденного или null:
  // тогда файл пойдёт по честному пути DWG_MODEL, а не повесит окно.
  let best = null;
  const budgetUntil = Number.isFinite(pairFuzzyBudgetUntil) ? pairFuzzyBudgetUntil : Date.now() + 100;
  for (let i = 0; i < list.length; i++) {
    if ((i & 63) === 0 && Date.now() > budgetUntil) break;
    const comparison = comparePairFingerprints(dwgFingerprint, list[i].fingerprint);
    if (comparison && (!best || comparison.score > best.score)) best = { node: list[i].node, ...comparison };
  }
  return best;
}

let nodeMatchCache = null;

function nodeMatches(node, visiting = new Set()) {
  if (!node) return false;
  const query = els.treeSearch.value.trim().toLocaleLowerCase("ru");
  const hasFormatFilter = state.activeFilters.size > 0;
  // Если поиск не ведётся и фильтры отключены — любой узел подходит сразу без рекурсии
  if (!query && !hasFormatFilter && !state.diffFilter) {
    return true;
  }
  if (nodeMatchCache && nodeMatchCache.has(node)) {
    return nodeMatchCache.get(node);
  }
  if (visiting.has(node)) {
    return false;
  }
  visiting.add(node);

  const value = `${node.name} ${node.extension || ""} ${node.path || ""}`.toLocaleLowerCase("ru");
  const searchOk = !query || value.includes(query);
  const formatOk = !hasFormatFilter || node.type === "folder" || state.activeFilters.has(node.extension);
  if (node.type === "file") {
    if (state.diffFilter && !state.diffStatus.has(node.path)) {
      if (nodeMatchCache) nodeMatchCache.set(node, false);
      visiting.delete(node);
      return false;
    }
    const res = searchOk && formatOk;
    if (nodeMatchCache) nodeMatchCache.set(node, res);
    visiting.delete(node);
    return res;
  }

  // Для папок: если имя совпало с поиском (и нет фильтра расширений), сразу подходит
  if (!state.diffFilter && searchOk && !hasFormatFilter) {
    if (nodeMatchCache) nodeMatchCache.set(node, true);
    visiting.delete(node);
    return true;
  }

  const childMatch = (node.children || []).some((child) => nodeMatches(child, visiting));
  const res = state.diffFilter ? childMatch : (childMatch || searchOk);
  if (nodeMatchCache) nodeMatchCache.set(node, res);
  visiting.delete(node);
  return res;
}

const folderMatchedFilesCache = new Map();
function countMatchedFilesCached(node) {
  if (!node || node.type !== "folder") return 0;
  if (folderMatchedFilesCache.has(node)) return folderMatchedFilesCache.get(node);
  let count = 0;
  for (const child of node.children || []) {
    if (child.type === "file") {
      if (nodeMatches(child)) count++;
    } else if (child.type === "folder") {
      count += countMatchedFilesCached(child);
    }
  }
  folderMatchedFilesCache.set(node, count);
  return count;
}

function countDiffDescendants(node, result = { added: 0, changed: 0, removed: 0 }) {
  if (!node) return result;
  const stack = [node];
  const seen = new Set();
  while (stack.length) {
    const current = stack.pop();
    if (!current || seen.has(current)) continue;
    seen.add(current);
    for (const child of current.children || []) {
      if (child.type === "file") {
        const status = state.diffStatus.get(child.path);
        if (status && status in result) result[status] += 1;
      } else {
        stack.push(child);
      }
    }
  }
  return result;
}

const diffCountsCache = new Map();
function countDiffDescendantsCached(node) {
  if (diffCountsCache.has(node.path)) return diffCountsCache.get(node.path);
  const counts = countDiffDescendants(node);
  diffCountsCache.set(node.path, counts);
  return counts;
}

function diffStatusText(status) {
  return status === "added" ? "новый" : status === "changed" ? "изменён" : "удалён";
}

function buildDiffState(manifest, previousManifest) {
  diffCountsCache.clear();
  pdfPairCache.clear();
  if (previousManifest) state.pdfPairIndex = null;
  state.diffStatus.clear();
  state.diffRemovedNodes = [];
  state.diffSummary = null;
  const diff = manifest?.lastDiff;
  if (!diff) return;
  for (const path of diff.added || []) state.diffStatus.set(path, "added");
  for (const path of diff.changed || []) state.diffStatus.set(path, "changed");
  const removedSet = new Set(diff.removed || []);
  if (previousManifest?.tree && removedSet.size) {
    flattenTree(previousManifest.tree, []).forEach((node) => {
      if (node.type === "file" && removedSet.has(node.path)) {
        state.diffStatus.set(node.path, "removed");
        state.diffRemovedNodes.push(node);
      }
    });
  }
  state.diffSummary = {
    added: (diff.added || []).length,
    changed: (diff.changed || []).length,
    removed: state.diffRemovedNodes.length,
    unchanged: (diff.unchanged || []).length,
  };
}

function startDiffPolling() {
  stopDiffPolling();
  if (!state.selectedObjectId) return;
  state.diffPollTimer = setInterval(async () => {
    if (!inTreeMode() || !state.currentManifest) return;
    try {
      const controller = new AbortController();
      const response = await fetch("/api/objects/diff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: state.selectedObjectId }),
        signal: controller.signal,
      });
      const payload = await response.json();
      if (!response.ok || state.progressCancelled) return;
      const diff = payload.lastDiff;
      const hasChanges = diff && ((diff.added || []).length || (diff.changed || []).length || (diff.removed || []).length);
      if (hasChanges) await refreshObjectInPlace({ reRender: false });
    } catch (error) {
      if (error.name === "AbortError") return;
    }
  }, DIFF_POLL_INTERVAL_MS);
}

function stopDiffPolling() {
  if (state.diffPollTimer) {
    clearInterval(state.diffPollTimer);
    state.diffPollTimer = null;
  }
}

async function refreshObjectInPlace(options = {}) {
  const object = selectedObject();
  if (!object) return;
  const previousManifest = state.currentManifest;
  const controller = createOperationController();
  startProgress("Проверка изменений", object.name);
  const response = await fetch("/api/objects/import", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: object.rootPath }),
    signal: controller.signal,
  });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error || "Объект не обновлён");
  if (state.progressCancelled) return;
  state.selectedObjectId = payload.id;
  state.currentManifest = payload;
  const removedPaths = new Set((previousManifest?.lastDiff?.removed || []).map((p) => p.casefold ? p.toLocaleLowerCase("ru") : p));
  state.selectedPaths = new Set([...state.selectedPaths].filter((path) => !removedPaths.has(path.toLocaleLowerCase("ru"))));
  buildDiffState(payload, previousManifest);
  await loadObjectSummaries();
  renderFormats();
  renderTree();
  finishProgress(hasDiffChanges(payload) ? "Обнаружены изменения" : "Изменений нет");
  if (options.reRender !== false && state.renderedPages.length && state.selectedPaths.size) {
    renderSelectedFiles({ force: true }).catch(showOperationError);
  }
}

function hasDiffChanges(manifest) {
  const diff = manifest?.lastDiff;
  return Boolean(diff && ((diff.added || []).length || (diff.changed || []).length || (diff.removed || []).length));
}

function selectNode(node, event = {}, options = {}) {
  const index = state.visibleRows.findIndex((item) => item.path === node.path);
  if (event.shiftKey && state.lastSelectedIndex !== null) {
    const start = Math.min(state.lastSelectedIndex, index);
    const end = Math.max(state.lastSelectedIndex, index);
    state.selectedPaths.clear();
    state.visibleRows.slice(start, end + 1).forEach((item) => state.selectedPaths.add(item.path));
  } else if (event.ctrlKey || event.metaKey) {
    if (state.selectedPaths.has(node.path)) state.selectedPaths.delete(node.path);
    else state.selectedPaths.add(node.path);
    state.lastSelectedIndex = index;

  } else {
    state.selectedPaths.clear();
    state.selectedPaths.add(node.path);
    state.lastSelectedIndex = index;
  }
  if (state.selectedPaths.size === 1) {
    const selectedPath = Array.from(state.selectedPaths)[0];
    const selectedItem = state.visibleRows.find((item) => item.path === selectedPath) || node;
    if (selectedItem && selectedItem.type === "file") {
      setActiveNativePath(selectedItem.path);
      state.revealedPath = selectedItem.path;
      if (!options.deferPreview) syncSelectionToPreview(selectedItem);
    } else {
      setActiveNativePath("");
      state.revealedPath = "";
    }
  } else {
    setActiveNativePath("");
    state.revealedPath = "";
  }
  updateTreeSelectionHighlight();
}

// Выбор из ленты миниатюр: та же логика, что в дереве (одиночный /
// Shift-диапазон / Ctrl), но без автооткрытия превью — его запускает
// сам обработчик карточки. Якорь общий (state.lastSelectedIndex).
function selectRailPath(path, event = {}) {
  if (!path) return false;
  const norm = String(path).replace(/\//g, "\\").toLowerCase();
  const node = state.visibleRows.find(
    (item) => String(item.path || "").replace(/\//g, "\\").toLowerCase() === norm
  ) || null;
  if (!node) {
    // Файла нет в видимых строках: честная одиночная метка без якоря.
    if (!event.shiftKey && !event.ctrlKey && !event.metaKey) {
      state.selectedPaths.clear();
      state.selectedPaths.add(path);
      state.lastSelectedIndex = null;
      setActiveNativePath(path);
      state.revealedPath = path;
      updateTreeSelectionHighlight();
    }
    return true;
  }
  selectNode(node, event, { deferPreview: true });
  return true;
}

function syncSelectionToPreview(fileNode) {
  if (!fileNode || fileNode.type !== "file") return;
  const path = fileNode.path;
  const norm = path.replace(/\//g, "\\").toLowerCase();

  // 1. Проверяем уже отрендеренные страницы PDF / Word / DWG / изображений
  if (state.renderedPages?.length) {
    const matchedPage = state.renderedPages.find((p) => {
      const pPath = (p.previewFor?.path || p.sourcePath || p.documentPath || p.path || "").replace(/\//g, "\\").toLowerCase();
      return pPath === norm;
    });

    if (matchedPage) {
      const isStage = Boolean(els.pdfViewer?.classList.contains("stage-active"));
      showPdfPage(matchedPage, { skipTreeScroll: true, activateStage: isStage });
      const key = pageKey(matchedPage);
      let thumbEl = Array.from(els.pdfThumbs?.querySelectorAll(".pdf-thumb") || []).find(
        (el) => el.dataset.pageKey === key
      );
      if (!thumbEl) {
        thumbEl = Array.from(els.pdfThumbs?.querySelectorAll(".pdf-thumb") || []).find((el) => {
          const p = state.renderedPages.find((x) => {
            try { return pageKey(x) === el.dataset.pageKey; } catch (_) { return false; }
          });
          if (!p) return false;
          const pPath = (p.previewFor?.path || p.sourcePath || p.documentPath || p.path || "").replace(/\//g, "\\").toLowerCase();
          return pPath === norm;
        });
      }
      if (thumbEl) {
        thumbEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      }
      return;
    }
  }

  // 2. Проверяем открытые книги Excel
  if (state.excelWorkbooks?.length) {
    const wbIndex = state.excelWorkbooks.findIndex((wb) => {
      const wbPath = (wb.path || wb.sourcePath || "").replace(/\//g, "\\").toLowerCase();
      return wbPath === norm;
    });
    if (wbIndex >= 0) {
      activateExcelWorkbook(wbIndex);
      const wbThumb = els.pdfThumbs?.querySelector(`.excel-book-thumb[data-workbook-index="${wbIndex}"]`);
      if (wbThumb) {
        wbThumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      }
      return;
    }
  }

  // 2a. Проверяем открытые документы Word
  if (state.wordDocs?.length) {
    const docIndex = state.wordDocs.findIndex((doc) => {
      const docPath = (doc.path || doc.sourcePath || "").replace(/\//g, "\\").toLowerCase();
      return docPath === norm;
    });
    if (docIndex >= 0) {
      activateWordDocument(docIndex);
      const docThumb = els.pdfThumbs?.querySelector(`.word-doc-thumb[data-doc-index="${docIndex}"]`);
      if (docThumb) {
        docThumb.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
      }
      return;
    }
  }

  // 3. Если файл ещё не отрендерен — не блокируем дерево фоновым рендером.
  // Для полного открытия файла служит двойной щелчок, а для пакета — кнопка «Отобразить».
}

async function previewFileDirectly(node, options = {}) {
  if (!node || node.type !== "file") return;
  setActiveNativePath(node.path);
  state.revealedPath = node.path;
  const ext = (node.extension || "").toUpperCase();

  els.pdfViewer.classList.remove("empty");
  // Позиции: 1 (дерево) -> 2 (лента), 2 -> 3 (большое окно).
  // Одиночка всегда открывается в ленте, кроме явного fullView.
  // TXT — как все: сначала миниатюра в ленте, крупно — только по двойному
  // клику на миниатюре.
  if (options.fullView) setViewerMode("full");
  else setViewerMode("standard");

  // 1. Excel: мгновенное открытие таблицы в просмотрщике
  if (["XLS", "XLSX", "XLSM", "CSV"].includes(ext)) {
    const excelItem = {
      ...node,
      previewType: "EXCEL",
      previewFor: {
        type: ext,
        name: node.name,
        path: node.path,
      },
    };
    await renderExcelWorkbooks([excelItem], { singleFile: true, fullView: options.fullView });
    if (options.fullView) setViewerMode("full");
    return;
  }

  // 1a. Word (.docx, .doc, .rtf): быстрый HTML через ядро rendering (Word-HTML).
  if (["DOCX", "DOC", "RTF"].includes(ext)) {
    const wordItem = {
      ...node,
      previewType: "WORD",
      previewFor: {
        type: ext,
        name: node.name,
        path: node.path,
      },
    };
    await renderWordDocuments([wordItem], { singleFile: true, fullView: options.fullView });
    if (options.fullView) setViewerMode("full");
    return;
  }

  // 2. Если файл уже отрендерен в памяти ЦЕЛИКОМ — мгновенно переключаемся.
  // Если в памяти только титульник (рендер из папки), проваливаемся ниже
  // к полному рендеру, иначе пользователь навсегда останется на 1-й странице.
  const norm = node.path.replace(/\//g, "\\").toLowerCase();
  if (state.renderedPages?.length) {
    const matchedPage = state.renderedPages.find((p) => {
      const pPath = (p.previewFor?.path || p.sourcePath || p.documentPath || p.path || "").replace(/\//g, "\\").toLowerCase();
      return pPath === norm;
    });
    if (matchedPage) {
      const total = matchedPage.totalPages || 1;
      const mDoc = matchedPage.documentPath || "";
      const mSrc = matchedPage.sourcePath || "";
      const loaded = state.renderedPages.filter((p) => (mDoc && p.documentPath === mDoc) || (mSrc && p.sourcePath === mSrc)).length;
      if (loaded >= total) {
        showPdfPage(matchedPage, { skipTreeScroll: true });
        if (options.fullView) setViewerMode("full");
        const key = pageKey(matchedPage);
        const thumbEl = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(key)}"]`);
        if (thumbEl) thumbEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
        return;
      }
    }
  }

  // 3. Подготовка элемента для рендеринга одиночного документа (DWG/PDF/изображения/TXT)
  let item = null;
  if (ext === "DWG") {
    if (!state.pairless && !state.pdfPairIndex && state.currentManifest?.tree) {
      state.pdfPairIndex = buildPdfPairIndex(getCachedFlatNodes());
    }
    const pair = findPdfPairForDwg(node, state.pdfPairIndex || new Map(), { fuzzy: false });
    if (pair) {
      item = {
        ...pair.node,
        previewFor: { type: "DWG", name: node.name, path: node.path, confidence: pair.confidence },
      };
    } else {
      item = {
        ...node,
        previewType: "DWG_MODEL",
        previewFor: { type: "DWG", name: node.name, path: node.path },
      };
    }
  } else if (["JPG", "JPEG", "PNG", "BMP", "WEBP", "SVG", "GIF", "JFIF", "TIF", "TIFF", "ICO"].includes(ext)) {
    item = {
      ...node,
      previewType: "IMAGE",
      url: `/api/file/raw?path=${encodeURIComponent(node.path)}`,
      previewFor: { type: ext, name: node.name, path: node.path },
    };
  } else if (["MOV", "MP4", "M4V", "WEBM", "AVI", "MKV"].includes(ext)) {
    item = {
      ...node,
      previewType: "VIDEO",
      url: `/api/file/raw?path=${encodeURIComponent(node.path)}`,
      previewFor: { type: ext, name: node.name, path: node.path },
    };
  } else if (ext === "PDF") {
    item = node;
  } else if (ext === "TXT") {
    item = {
      ...node,
      previewType: "TXT",
      sourcePath: node.path,
      previewFor: { type: "TXT", name: node.name, path: node.path },
    };
  } else {
    // Нативный формат: карточка с метаданными ядра + кнопка открытия.
    await showNativeAppCard(node, options);
    return;
  }

  await renderSelectedPdfFiles([item], { singleFile: true, fullView: options.fullView });
  if (options.fullView) setViewerMode("full");
}

function updateTreeSelectionHighlight() {
  if (!els.objectTree) return;
  const revealedNorm = (state.revealedPath || "").replace(/\//g, "\\").toLowerCase();
  const selectedNorms = new Set(Array.from(state.selectedPaths).map((p) => (p || "").replace(/\//g, "\\").toLowerCase()));
  const rows = els.objectTree.querySelectorAll(".tree-row");
  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const pNorm = (r.dataset.path || "").replace(/\//g, "\\").toLowerCase();
    const isSelected = selectedNorms.has(pNorm);
    const isRevealed = Boolean(revealedNorm && pNorm === revealedNorm);
    r.classList.toggle("selected", isSelected);
    r.classList.toggle("thumb-reveal", isRevealed);
  }
  updateRailSelectionHighlight();
}

// В Окне 2 каждый отдельный лист или документ выделяется индивидуально.
// Синим цветом подсвечивается только текущий активный лист/книга (.active).
// Массовое выделение (.selected) снято со всех миниатюр, чтобы не заливать
// синим цветом все сотни листов каталога.
function updateRailSelectionHighlight() {
  if (!els.pdfThumbs) return;
  els.pdfThumbs.querySelectorAll(".pdf-thumb").forEach((thumb) => {
    thumb.classList.remove("selected");
  });
  updateActivePdfThumb();
}

function rebuildVisibleRows() {
  state.visibleRows = [];
  if (!state.currentManifest?.tree) return;
  const isFiltering = treeFilteringActive();
  const stack = [state.currentManifest.tree];
  const seen = new Set();
  while (stack.length) {
    const node = stack.pop();
    if (!node || seen.has(node)) continue;
    seen.add(node);
    if (!nodeMatches(node)) continue;
    state.visibleRows.push(node);
    const isFolderExpanded = !state.collapsedFolders.has(node.path) || isFiltering;
    if (node.type === "folder" && isFolderExpanded && node.children) {
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push(node.children[i]);
      }
    }
  }
  if (state.diffRemovedNodes?.length && !state.diffFilter) {
    state.diffRemovedNodes.forEach((node) => state.visibleRows.push(node));
  }
}

let toastTimer = null;
function showToast(message) {
  let toast = document.getElementById("toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    document.body.append(toast);
  }
  toast.innerHTML = `<svg viewBox="0 0 16 16" width="14" height="14" fill="none" stroke="#34d399" stroke-width="2"><path d="M3 8.5l3.5 3.5 6.5-7.5"/></svg><span>${escapeHtml(message)}</span>`;
  toast.hidden = false;
  requestAnimationFrame(() => {
    toast.classList.add("visible");
  });
  if (toastTimer) clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    toast.classList.remove("visible");
    setTimeout(() => {
      if (!toast.classList.contains("visible")) toast.hidden = true;
    }, 200);
  }, 2200);
}

async function copyTextToClipboard(rawText, successToast = "Текст скопирован") {
  if (!rawText) return false;
  const text = String(rawText);
  let success = false;

  // 1. Primary: navigator.clipboard.writeText (while user gesture is fresh)
  if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
    try {
      await navigator.clipboard.writeText(text);
      success = true;
    } catch (err) {
      console.warn("[app copy] navigator.clipboard.writeText failed:", err?.name || "Error");
    }
  }

  // 2. Fallback 1: backend POST /api/clipboard (only if primary failed)
  if (!success) {
    try {
      const resp = await fetch("/api/clipboard", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (resp.ok) {
        const data = await resp.json();
        if (data && data.ok === true) {
          success = true;
        }
      }
    } catch (err) {
      console.warn("[app copy] backend /api/clipboard fallback failed:", err?.name || "Error");
    }
  }

  // 3. Fallback 2: execCommand on temporary textarea (only if both above failed)
  if (!success) {
    let textarea = null;
    try {
      textarea = document.createElement("textarea");
      textarea.value = text;
      textarea.style.position = "fixed";
      textarea.style.top = "0";
      textarea.style.left = "0";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, text.length);
      success = document.execCommand("copy");
    } catch (err) {
      console.warn("[app copy] execCommand fallback failed:", err?.name || "Error");
    } finally {
      if (textarea && textarea.parentNode) {
        textarea.parentNode.removeChild(textarea);
      }
    }
  }

  if (success && successToast) {
    showToast(successToast);
  } else if (!success) {
    showToast("Ошибка копирования в буфер обмена");
  }
  return success;
}
window.copyTextToClipboard = copyTextToClipboard;

async function copyPathToClipboard(rawPath) {
  if (!rawPath) return;
  // Убеждаемся, что системный путь Windows использует обратные слэши
  const path = String(rawPath).replace(/\//g, "\\");
  let success = false;

  // 1. Попытка через нативный Win32 API бэкенда (работает везде без ограничений webview)
  try {
    const resp = await fetch("/api/clipboard", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: path }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.ok) success = true;
    }
  } catch (err) {
  }

  // 2. Если бэкенд недоступен — пробуем современный navigator.clipboard
  if (!success && navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(path);
      success = true;
    } catch (e) {
    }
  }

  // 3. Резервный браузерный фоллбэк через textarea без readonly и с явным фокусом
  if (!success) {
    try {
      const textarea = document.createElement("textarea");
      textarea.value = path;
      textarea.style.position = "fixed";
      textarea.style.top = "0";
      textarea.style.left = "0";
      textarea.style.width = "2em";
      textarea.style.height = "2em";
      textarea.style.padding = "0";
      textarea.style.border = "none";
      textarea.style.outline = "none";
      textarea.style.boxShadow = "none";
      textarea.style.background = "transparent";
      document.body.appendChild(textarea);
      textarea.focus();
      textarea.select();
      textarea.setSelectionRange(0, path.length);
      success = document.execCommand("copy");
      document.body.removeChild(textarea);
    } catch (e) {
    }
  }

  if (success) {
    const preview = path.length > 55 ? "..." + path.slice(-52) : path;
    showToast(`Путь скопирован:\n${preview}`);
  } else {
    showToast("Не удалось скопировать путь");
  }
}

function revealPathInTree(path, options = {}) {
  // Файл активной миниатюры в дереве подсвечен постоянно, пока стоим на нём:
  // одна запись в дереве — один подсвеченный файл, сколько бы страниц
  // у него ни было в ленте. Маркер синхронизируем с просмотром,
  // при этом выделение (state.selectedPaths) связываем с текущим документом!
  if (!path) return;
  const shouldUpdateSelection = options.updateSelection !== false;
  state.revealedPath = path;
  if (shouldUpdateSelection) {
    state.selectedPaths.clear();
    state.selectedPaths.add(path);
  }

  const fileName = path.split(/[\\/]/).pop();
  if (fileName) updateViewerBanner(fileName);

  if (!state.currentManifest?.tree || !els.objectTree) return;

  const norm = String(path).replace(/\//g, "\\").toLowerCase();
  const nodeIndex = state.visibleRows.findIndex((item) => String(item.path || "").replace(/\//g, "\\").toLowerCase() === norm);
  if (nodeIndex >= 0 && shouldUpdateSelection) state.lastSelectedIndex = nodeIndex;

  let row = null;
  const pathFileName = path.split(/[\/\\]/).pop().toLowerCase().trim();
  const rows = els.objectTree.querySelectorAll(".tree-row");
  for (const r of rows) {
    const rPath = String(r.dataset.path || "").replace(/\//g, "\\").toLowerCase();
    if (rPath === norm) {
      row = r;
      break;
    }
  }
  if (!row && pathFileName) {
    for (const r of rows) {
      const rPath = String(r.dataset.path || "").replace(/\//g, "\\").toLowerCase();
      const rName = rPath.split(/[\/\\]/).pop().toLowerCase().trim();
      if (rName === pathFileName) {
        row = r;
        break;
      }
    }
  }

  // Если строка ещё не в DOM (родительская папка свёрнута) — раскрываем только нужных родителей
  // Раскрытие свёрнутых папок — только для явной навигации (клик, стрелки,
  // показ страницы). Наведение мыши на миниатюры дерево не трогает вообще,
  if (!row) {
    let uncollapsedAny = false;
    for (const folderPath of [...state.collapsedFolders]) {
      const folderNorm = String(folderPath).replace(/\//g, "\\").toLowerCase();
      if (norm.startsWith(folderNorm + "\\")) {
        state.collapsedFolders.delete(folderPath);
        uncollapsedAny = true;
      }
    }
    if (uncollapsedAny) {
      renderTree();
      try {
        row = els.objectTree.querySelector(`.tree-row[data-path="${CSS.escape(path)}"]`);
        if (!row) {
          const rows = els.objectTree.querySelectorAll(".tree-row");
          for (const r of rows) {
            if (String(r.dataset.path || "").replace(/\//g, "\\").toLowerCase() === norm) {
              row = r;
              break;
            }
          }
        }
      } catch {
        row = null;
      }
    }
  }

  updateTreeSelectionHighlight();

  if (row && !options.skipScroll) {
    row.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

const FOLDER_ICON_SVG = `<svg viewBox="0 0 16 16" width="15" height="15"><path fill="#d89e13" d="M1.5 2A1.5 1.5 0 0 0 0 3.5v9A1.5 1.5 0 0 0 1.5 14h13a1.5 1.5 0 0 0 1.5-1.5v-7A1.5 1.5 0 0 0 14.5 4H7.5L6.146 2.646A1.5 1.5 0 0 0 5.086 2.207L1.5 2z"/><path fill="#ffcb30" d="M1 5h14v7.5a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 1 12.5V5z"/><path fill="#ffe277" d="M1 5h14v1H1z"/></svg>`;

function getFileIconSvg(ext = "") {
  const e = String(ext).toUpperCase();
  if (e === "PDF") {
    return `<svg viewBox="0 0 16 16" width="15" height="15" fill="#dc2626"><path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-7.5A1.5 1.5 0 0 1 3 14.5v-13zm6.5.5v3h3l-3-3z"/><text x="3.8" y="12" font-size="5" font-weight="bold" fill="#ffffff" font-family="Segoe UI, sans-serif">PDF</text></svg>`;
  }
  if (e === "DWG" || e === "DXF") {
    return `<svg viewBox="0 0 16 16" width="15" height="15" fill="#2563eb"><path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-7.5A1.5 1.5 0 0 1 3 14.5v-13zm6.5.5v3h3l-3-3z"/><text x="3" y="12" font-size="4.5" font-weight="bold" fill="#ffffff" font-family="Segoe UI, sans-serif">DWG</text></svg>`;
  }
  if (e === "XLSX" || e === "XLS" || e === "CSV" || e === "GSHEET") {
    return `<svg viewBox="0 0 16 16" width="15" height="15" fill="#16a34a"><path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-7.5A1.5 1.5 0 0 1 3 14.5v-13zm6.5.5v3h3l-3-3z"/><text x="3.8" y="12" font-size="5" font-weight="bold" fill="#ffffff" font-family="Segoe UI, sans-serif">XLS</text></svg>`;
  }
  if (e === "DOCX" || e === "DOC" || e === "GDOC") {
    return `<svg viewBox="0 0 16 16" width="15" height="15" fill="#1d4ed8"><path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-7.5A1.5 1.5 0 0 1 3 14.5v-13zm6.5.5v3h3l-3-3z"/><text x="3.2" y="12" font-size="4.5" font-weight="bold" fill="#ffffff" font-family="Segoe UI, sans-serif">DOC</text></svg>`;
  }
  return `<svg viewBox="0 0 16 16" width="15" height="15" fill="#94a3b8"><path d="M3 1.5A1.5 1.5 0 0 1 4.5 0h5l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-7.5A1.5 1.5 0 0 1 3 14.5v-13zm6.5.5v3h3l-3-3z"/></svg>`;
}

const pdfPairCache = new Map();
function getPdfPairForDwgCached(node) {
  if (!node || node.extension !== "DWG") return null;
  if (pdfPairCache.has(node.path)) return pdfPairCache.get(node.path);
  if (state.pairless) return null;
  if (!state.pdfPairIndex && state.currentManifest?.tree) {
    state.pdfPairIndex = buildPdfPairIndex(getCachedFlatNodes());
  }
  const pair = findPdfPairForDwg(node, state.pdfPairIndex, { fuzzy: false });
  pdfPairCache.set(node.path, pair);
  return pair;
}

function toggleFolderNode(node, nodeEl) {
  if (!node || node.type !== "folder" || !nodeEl) return;
  const isCurrentlyExpanded = nodeEl.classList.contains("expanded");
  const willBeCollapsed = isCurrentlyExpanded;

  if (willBeCollapsed) {
    state.collapsedFolders.add(node.path);
  } else {
    state.collapsedFolders.delete(node.path);
  }

  const chevron = nodeEl.querySelector(":scope > .tree-row .tree-chevron");
  if (chevron) {
    chevron.classList.toggle("expanded", !willBeCollapsed);
    chevron.title = willBeCollapsed ? "Развернуть папку" : "Свернуть папку";
  }
  nodeEl.classList.toggle("expanded", !willBeCollapsed);

  let childrenEl = nodeEl.querySelector(":scope > .tree-children");
  if (!willBeCollapsed) {
    if (!childrenEl && node.children?.length) {
      childrenEl = document.createElement("div");
      childrenEl.className = "tree-children";
      node.children.forEach((child) => renderTreeNode(child, childrenEl));
      nodeEl.append(childrenEl);
    } else if (childrenEl) {
      childrenEl.classList.remove("collapsed");
    }
  } else {
    if (childrenEl) {
      childrenEl.classList.add("collapsed");
    }
  }

  state.selectedPaths.clear();
  state.selectedPaths.add(node.path);
  updateTreeSelectionHighlight();
  rebuildVisibleRows();
  if (state.currentManifest?.name) {
    updateViewerBanner(state.currentManifest.name);
  }
}

function treeFilteringActive() {
  // Поиск, фильтр расширений или фильтр изменений: дерево показываем
  // раскрытым, иначе совпадения внутри свёрнутых папок не найти.
  return Boolean(els.treeSearch.value.trim() || state.activeFilters.size || state.diffFilter);
}

function updateTreeFilterSummary() {
  if (!els.treeFilterSummary) return;
  const totalFiles = state.currentManifest?.statistics?.files || 0;
  const isFiltering = treeFilteringActive();

  if (!isFiltering || !state.currentManifest?.tree) {
    els.treeFilterSummary.classList.remove("visible");
    els.treeFilterSummary.replaceChildren();
    return;
  }

  // Считаем отфильтрованные файлы и уникальные папки среди видимых строк
  let matchedFilesCount = 0;
  let matchedFoldersCount = 0;
  for (const node of state.visibleRows) {
    if (node.type === "file") matchedFilesCount++;
    else if (node.type === "folder") matchedFoldersCount++;
  }

  const query = els.treeSearch.value.trim();
  const filterExts = Array.from(state.activeFilters);
  const titleParts = [];
  if (filterExts.length) titleParts.push(filterExts.join(", "));
  if (query) titleParts.push(`"${query}"`);
  if (state.diffFilter) titleParts.push("изменения");
  const filterDesc = titleParts.join(" + ") || "Фильтр";

  const contentSpan = document.createElement("span");
  contentSpan.innerHTML = `<strong>${escapeHtml(filterDesc)}:</strong> <span class="filter-count-badge">${matchedFilesCount.toLocaleString("ru")}</span> файл. в ${matchedFoldersCount.toLocaleString("ru")} папк. <span style="color:#64748b;">(Всего: ${totalFiles.toLocaleString("ru")})</span>`;

  const resetBtn = document.createElement("span");
  resetBtn.className = "filter-reset-hint";
  resetBtn.textContent = "Сбросить";
  resetBtn.title = "Сбросить текущий фильтр и поиск";
  resetBtn.addEventListener("click", () => {
    state.activeFilters.clear();
    els.treeSearch.value = "";
    state.diffFilter = false;
    renderFormats();
    renderTree();
  });

  els.treeFilterSummary.replaceChildren(contentSpan, resetBtn);
  els.treeFilterSummary.classList.add("visible");
}

function collapseAllFolders() {
  state.collapsedFolders.clear();
  if (!state.currentManifest?.tree) return;
  const stack = [state.currentManifest.tree];
  const seen = new Set();
  while (stack.length) {
    const node = stack.pop();
    if (!node || seen.has(node)) continue;
    seen.add(node);
    for (const child of node.children || []) {
      if (child.type === "folder") {
        state.collapsedFolders.add(child.path);
        stack.push(child);
      }
    }
  }
}

function renderTreeNode(rootNode, rootParent) {
  // Итеративный обход: стек хранит {node, parent} — что вставить и куда.
  const stack = [{ node: rootNode, parent: rootParent }];
  while (stack.length) {
    const { node, parent } = stack.pop();
    if (!nodeMatches(node)) continue;

    const nodeEl = document.createElement("div");
    nodeEl.className = "tree-node";
    const collapsed = state.collapsedFolders.has(node.path) && !treeFilteringActive();
    if (node.type === "folder" && !collapsed) {
      nodeEl.classList.add("expanded");
    }

    const row = document.createElement("div");
    row.className = `tree-row ${node.type}`;
    row.dataset.path = node.path;
    if (node.path === state.revealedPath) row.classList.add("thumb-reveal");
    row.classList.toggle("selected", state.selectedPaths.has(node.path));
    row.title = node.path;

    const content = document.createElement("div");
    content.className = "tree-row-content";

    const chevron = document.createElement("span");
    chevron.className = "tree-chevron";
    if (node.type === "folder") {
      chevron.textContent = "›";
      if (!collapsed) chevron.classList.add("expanded");
      chevron.title = collapsed ? "Развернуть папку" : "Свернуть папку";
      chevron.addEventListener("click", ((n, el) => (e) => {
        e.stopPropagation();
        toggleFolderNode(n, el);
      })(node, nodeEl));
    } else {
      chevron.classList.add("leaf");
      chevron.innerHTML = "&nbsp;";
    }
    content.append(chevron);

    const iconEl = document.createElement("span");
    iconEl.className = "tree-icon";
    if (node === state.currentManifest?.tree) {
      iconEl.innerHTML = `<svg viewBox="0 0 16 16" width="15" height="15"><path fill="#ffffff" stroke="#718096" stroke-width="0.9" d="M3 1.5A1.5 1.5 0 0 1 4.5 0h6l4 4v10.5a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 3 14.5v-13z"/><path fill="#3b82f6" d="M5 6h6v1.2H5zm0 3h6v1.2H5zm0 3h4v1.2H5z"/></svg>`;
    } else if (node.type === "folder") {
      iconEl.innerHTML = FOLDER_ICON_SVG;
    } else {
      iconEl.innerHTML = getFileIconSvg(node.extension);
    }
    content.append(iconEl);

    const nameEl = document.createElement("span");
    nameEl.className = "tree-name";
    nameEl.textContent = node.name;

    const diffStatus = state.diffStatus.get(node.path);
    if (node.type === "file" && diffStatus) {
      const diffBadge = document.createElement("span");
      diffBadge.className = `diff-badge diff-${diffStatus}`;
      diffBadge.textContent = diffStatusText(diffStatus);
      nameEl.append(" ", diffBadge);
    }
    if (node.type === "folder" && state.diffSummary) {
      const counts = countDiffDescendantsCached(node);
      const parts = [];
      if (counts.added) parts.push(`+${counts.added}`);
      if (counts.changed) parts.push(`~${counts.changed}`);
      if (counts.removed) parts.push(`-${counts.removed}`);
      if (parts.length) {
        const diffFolderBadge = document.createElement("span");
        diffFolderBadge.className = "diff-badge diff-folder";
        diffFolderBadge.textContent = parts.join(" ");
        nameEl.append(" ", diffFolderBadge);
      }
    }
    if (node.type === "file" && node.extension === "DWG") {
      const pdfPair = getPdfPairForDwgCached(node);
      if (pdfPair) {
        const pairBadge = document.createElement("span");
        pairBadge.className = "pair-badge";
        pairBadge.textContent = "↔";
        pairBadge.title = `Связан с PDF-превью: ${pdfPair.node.name}${pdfPair.confidence === "probable" ? " (вероятная пара)" : ""}`;
        nameEl.append(" ", pairBadge);
      }
    }
    content.append(nameEl);

    if (node.type === "folder" && node.children) {
      const metaEl = document.createElement("span");
      metaEl.className = "tree-meta";
      if (treeFilteringActive()) {
        const matchedCount = countMatchedFilesCached(node);
        metaEl.textContent = `(${matchedCount})`;
        metaEl.title = `Файлов, подходящих под текущий фильтр в этой папке: ${matchedCount}`;
      } else {
        metaEl.textContent = `(${node.children.length})`;
      }
      content.append(metaEl);
    }

    row.append(content);
    row.addEventListener("contextmenu", ((n) => (event) => {
      event.preventDefault();
      event.stopPropagation();
      showFileContextMenu(event.clientX, event.clientY, {
        path: n.path,
        isDir: n.type === "folder",
        ext: n.extension || "",
      });
    })(node));

    row.addEventListener("click", ((n, el) => (event) => {
      event.stopPropagation();
      if (n.type === "folder") {
        const isCollapsed = !el.classList.contains("expanded");
        if (isCollapsed && !event.shiftKey && !event.ctrlKey && !event.metaKey) {
          toggleFolderNode(n, el);
        }
        selectNode(n, event);
        return;
      }
      selectNode(n, event);
    })(node, nodeEl));

    row.addEventListener("dblclick", ((n) => (event) => {
      event.stopPropagation();
      if (n.type === "folder") {
        toggleFolderNode(n, nodeEl);
        return;
      }
      const index = state.visibleRows.findIndex((item) => item.path === n.path);
      state.selectedPaths.clear();
      state.selectedPaths.add(n.path);
      state.lastSelectedIndex = index;
      updateTreeSelectionHighlight();
      previewFileDirectly(n, { fullView: false }).catch(showOperationError);
    })(node));

    nodeEl.append(row);
    state.visibleRows.push(node);

    if (node.type === "folder" && node.children?.length && !collapsed) {
      const children = document.createElement("div");
      children.className = "tree-children";
      nodeEl.append(children);
      // Дочерние элементы добавляем в стек в обратном порядке,
      // чтобы при извлечении из стека порядок остался правильным
      for (let i = node.children.length - 1; i >= 0; i--) {
        stack.push({ node: node.children[i], parent: children });
      }
    }

    parent.append(nodeEl);
  }
}

function renderFormats() {
  els.formatStrip.replaceChildren();
  const extensions = state.currentManifest?.statistics?.extensions || {};
  const preferred = ["PDF", "DWG", "XLSX", "XLS", "XLSM", "GSHEET", "DOCX", "DOC", "GDOC", "TXT", "PNG", "JPG", "JPEG", "PPTX", "SVG"];
  const all = Object.keys(extensions).sort((a, b) => a.localeCompare(b, "ru"));
  const formats = [...new Set([...preferred.filter((ext) => ext in extensions), ...all])];
  if (!formats.length) {
    const empty = document.createElement("span");
    empty.className = "format-empty";
    empty.textContent = "Форматов нет";
    els.formatStrip.append(empty);
    return;
  }
  formats.forEach((ext) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "format-chip";
    button.classList.toggle("active", state.activeFilters.has(ext));
    button.textContent = `${ext} ${extensions[ext] || 0}`;
    let chipClickTimer = null;
    button.addEventListener("click", () => {
      if (chipClickTimer) {
        clearTimeout(chipClickTimer);
        chipClickTimer = null;
        return;
      }
      chipClickTimer = setTimeout(() => {
        chipClickTimer = null;
      }, 260);

      // Одиночный клик по чипу формата: фильтрация дерева по расширению.
      // Не выделяем все файлы скопом (все файлы выделяет и рендерит только двойной клик по чипу).
      const wasSoloActive = state.activeFilters.size === 1 && state.activeFilters.has(ext);
      state.activeFilters.clear();
      state.selectedPaths.clear();
      if (!wasSoloActive) {
        state.activeFilters.add(ext);
      }
      renderFormats();
      renderTree();
      // Якорь для Shift+клика: первый выделенный файл в видимых строках.
      // Без этого Shift сразу после фильтра брал бы старый якорь.
      const firstChipSel = Array.from(state.selectedPaths)[0];
      const firstChipIdx = firstChipSel
        ? state.visibleRows.findIndex((item) => item.path === firstChipSel)
        : -1;
      state.lastSelectedIndex = firstChipIdx >= 0 ? firstChipIdx : null;
      updateRailSelectionHighlight();
    });
    button.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      event.preventDefault();
      if (chipClickTimer) {
        clearTimeout(chipClickTimer);
        chipClickTimer = null;
      }
      state.activeFilters.clear();
      state.activeFilters.add(ext);
      state.selectedPaths.clear();
      if (state.currentManifest?.tree) {
        getCachedFlatNodes()
          .filter((node) => node.type === "file" && node.extension === ext)
          .forEach((node) => state.selectedPaths.add(node.path));
      }
      renderFormats();
      renderTree();
      // Якорь для Shift+клика: первый выделенный файл в видимых строках.
      const firstDblSel = Array.from(state.selectedPaths)[0];
      const firstDblIdx = firstDblSel
        ? state.visibleRows.findIndex((item) => item.path === firstDblSel)
        : -1;
      state.lastSelectedIndex = firstDblIdx >= 0 ? firstDblIdx : null;
      updateRailSelectionHighlight();
      renderSelectedFiles().catch(showOperationError);
    });
    els.formatStrip.append(button);
  });
}

function updateViewerBanner(title) {
  const el = document.getElementById("viewerBannerTitle");
  const banner = document.getElementById("viewerHeaderBanner");
  if (!banner) return;
  banner.style.display = "flex";
  if (!title) {
    if (el) el.textContent = state.currentManifest?.name || 'Политика "Локальный компьютер"';
    return;
  }
  if (el) el.textContent = title;
}

function renderTree() {
  state.visibleRows = [];
  if (!state.currentManifest?.tree) {
    els.objectTree.replaceChildren();
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "Дерево ещё не открыто.";
    els.objectTree.append(empty);
    return;
  }
  nodeMatchCache = new Map();
  if (!state.pairless && !state.pdfPairIndex) {
    state.pdfPairIndex = buildPdfPairIndex(getCachedFlatNodes());
  }
  const fragment = document.createDocumentFragment();
  renderTreeNode(state.currentManifest.tree, fragment);
  if (state.diffRemovedNodes.length && !state.diffFilter) {
    const removedTitle = document.createElement("div");
    removedTitle.className = "diff-removed-title";
    removedTitle.textContent = "Удалённые файлы";
    fragment.append(removedTitle);
    state.diffRemovedNodes.forEach((node) => {
      const row = document.createElement("div");
      row.className = "tree-row file diff-removed-row";
      row.dataset.path = node.path;
      row.title = `${node.path}\nФайл удалён из исходной папки, но превью сохранено.`;

      const content = document.createElement("div");
      content.className = "tree-row-content";

      const chevron = document.createElement("span");
      chevron.className = "tree-chevron leaf";
      chevron.innerHTML = "&nbsp;";
      content.append(chevron);

      const iconEl = document.createElement("span");
      iconEl.className = "tree-icon";
      iconEl.innerHTML = getFileIconSvg(node.extension);
      content.append(iconEl);

      const nameEl = document.createElement("span");
      nameEl.className = "tree-name";
      nameEl.textContent = node.name;

      const badge = document.createElement("span");
      badge.className = "diff-badge diff-removed";
      badge.textContent = "удалён";
      nameEl.append(" ", badge);
      content.append(nameEl);

      row.append(content);
      row.addEventListener("click", (event) => {
        event.stopPropagation();
        selectNode(node, event);
      });
      row.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        showFileContextMenu(event.clientX, event.clientY, {
          path: node.path,
          isDir: false,
          ext: node.extension || "",
        });
      });
      fragment.append(row);
      state.visibleRows.push(node);
    });
  }
  if (!state.visibleRows.length) {
    const empty = document.createElement("div");
    empty.className = "empty-note";
    empty.textContent = "Поиск или фильтр ничего не нашли.";
    fragment.append(empty);
  }
  els.objectTree.replaceChildren(fragment);
  nodeMatchCache = null;
  folderMatchedFilesCache.clear();
  updateTreeSelectionHighlight();
  updateTreeFilterSummary();
}

async function openSelectedObject() {
  const object = selectedObject();
  if (!object) return;
  const controller = createOperationController();
  startProgress("Открытие структуры", object.name);
  const _ooT0 = performance.now();
  const response = await fetch(`/api/objects/${encodeURIComponent(object.id)}`, { signal: controller.signal });
  const manifest = await response.json();
  beaconPerf("object-open", performance.now() - _ooT0, `id=${object.id}`);
  if (!response.ok) throw new Error(manifest.error || "Объект не открыт");
  state.currentManifest = manifest;
  state.selectedPaths.clear();
  state.revealedPath = "";
  state.activeFilters.clear();
  state.diffFilter = false;
  collapseAllFolders();
  state.renderedPages = [];
  pdfPairCache.clear();
  diffCountsCache.clear();
  // Pairless (ситуация 2): в объекте нет PDF вовсе — индекс пар не нужен,
  // все DWG сразу пойдут по пути DWG_MODEL. Проверка по статистике O(1),
  // без обхода дерева. Иначе индекс строится один раз при открытии объекта
  // (~0,3 с на 14 тыс. файлов), дальше все показы и дерево его переиспользуют.
  buildDiffState(manifest, null);
  const _pairExts = (manifest.statistics || {}).extensions || {};
  const _pdfCount = Number(_pairExts.PDF ?? _pairExts.pdf ?? 0);
  state.pairless = _pdfCount === 0;
  const _piT0 = performance.now();
  state.pdfPairIndex = state.pairless ? null : buildPdfPairIndex(getCachedFlatNodes());
  beaconPerf("pair-index", performance.now() - _piT0, `files=${(manifest.statistics || {}).files || 0} pdf=${_pdfCount} pairless=${state.pairless}`);
  setViewerMode("standard");
  setMode("tree");
  updateViewerBanner(manifest.name || object.name);
  setTreeBrowseMode(true);
  renderFormats();
  const _trT0 = performance.now();
  renderTree();
  beaconPerf("tree-render", performance.now() - _trT0, `rows=${state.visibleRows.length}`);
  startDiffPolling();
  finishProgress("Структура открыта");
}

function collectPreviewFilesForDisplay() {
  if (!state.currentManifest?.tree) return [];
  const allNodes = getCachedFlatNodes();
  const selectedNodes = allNodes.filter((node) => state.selectedPaths.has(node.path));
  // Индекс один на объект (построен при открытии), не пересобираем при каждом показе.
  // Pairless-объекты (без PDF) индекс не строят вовсе.
  if (!state.pairless && !state.pdfPairIndex) state.pdfPairIndex = buildPdfPairIndex(allNodes);
  const pdfIndex = state.pdfPairIndex;
  const result = [];
  const directPdfPaths = new Set();
  const directSourcePaths = new Set();

  function addPreviewFile(node) {
    if (!node || node.type !== "file") return;
    if (node.name.startsWith("~$") || node.name.startsWith(".~")) return;
    const ext = (node.extension || "").toUpperCase();

    if (ext === "PDF" && !directPdfPaths.has(node.path)) {
      directPdfPaths.add(node.path);
      result.push(node);
    } else if (["DOC", "DOCX", "RTF"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        ...node,
        previewType: "WORD",
        previewFor: {
          type: ext,
          name: node.name,
          path: node.path,
        },
      });
    } else if (["XLS", "XLSX", "XLSM", "CSV"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        ...node,
        previewType: "EXCEL",
        previewFor: {
          type: ext,
          name: node.name,
          path: node.path,
        },
      });
    } else if (ext === "DWG") {
      if (directSourcePaths.has(node.path)) return;
      directSourcePaths.add(node.path);
      // Массовый показ: только точные пары (папка не важна — пара обычно
      // в соседней папке PDF). При отсутствии пары используем мгновенный thumbnail.
      const pair = findPdfPairForDwg(node, pdfIndex, { fuzzy: false });
      if (pair) {
        result.push({
          ...pair.node,
          previewFor: {
            type: "DWG",
            name: node.name,
            path: node.path,
            confidence: pair.confidence,
          },
        });
      } else {
        result.push({
          ...node,
          previewType: "DWG_MODEL",
          previewFor: {
            type: "DWG",
            name: node.name,
            path: node.path,
          },
        });
      }
    } else if (ext === "TXT" && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        ...node,
        previewType: "TXT",
        sourcePath: node.path,
        previewFor: { type: "TXT", name: node.name, path: node.path },
      });
    } else if (["JPG", "JPEG", "PNG", "BMP", "WEBP", "SVG", "GIF", "JFIF", "TIF", "TIFF", "ICO"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        ...node,
        previewType: "IMAGE",
        url: `/api/file/raw?path=${encodeURIComponent(node.path)}`,
        previewFor: {
          type: ext,
          name: node.name,
          path: node.path,
        },
      });
    } else if (["MOV", "MP4", "M4V", "WEBM", "AVI", "MKV"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        ...node,
        previewType: "VIDEO",
        url: `/api/file/raw?path=${encodeURIComponent(node.path)}`,
        previewFor: {
          type: ext,
          name: node.name,
          path: node.path,
        },
      });
    } else if (["GDOC", "GSHEET", "GSLIDES"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      const isSheet = ext === "GSHEET";
      const isSlides = ext === "GSLIDES";
      const label = isSheet ? "Google Sheets" : (isSlides ? "Google Slides" : "Google Docs");
      result.push({
        type: "native-file",
        name: node.name,
        documentPath: node.path,
        sourcePath: node.path,
        sourceType: ext,
        message: `${label}: документ Google Drive. Нажмите кнопку, чтобы открыть в браузере.`,
      });
    } else if (["ZIP", "RAR", "7Z", "TAR", "GZ"].includes(ext) && !directSourcePaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        type: "native-file",
        name: node.name,
        documentPath: node.path,
        sourcePath: node.path,
        sourceType: ext,
        message: `Архив ${ext}: нажмите кнопку, чтобы открыть в Проводнике Windows или архиваторе.`,
      });
    // Дубликат PDF (папка + файл внутри неё выбраны вместе): путь уже занят
    // directPdfPaths выше, но провалился бы в native-карточку — отсекаем.
    } else if (!directSourcePaths.has(node.path) && !directPdfPaths.has(node.path)) {
      directSourcePaths.add(node.path);
      result.push({
        type: "native-file",
        name: node.name,
        documentPath: node.path,
        sourcePath: node.path,
        sourceType: ext,
        message: `Файл .${ext.toLowerCase()}: нажмите кнопку для открытия в программе Windows по умолчанию.`,
      });
    }
  }

  // Bulk pairing guard: cap fuzzy DWG->PDF search (see PAIR_FUZZY_BUDGET_MS).
  pairFuzzyBudgetUntil = Date.now() + PAIR_FUZZY_BUDGET_MS;
  try {
    if (selectedNodes.length) {
      selectedNodes.forEach((node) => {
        if (node.type === "file") addPreviewFile(node);
        if (node.type === "folder") {
          // Строго внутри папки: через разделитель, иначе папка «Договор»
          // захватывала бы соседнюю папку «Договор №2» как свою часть.
          const prefixBack = `${node.path}\\`;
          const prefixSlash = `${node.path}/`;
          allNodes
            .filter((candidate) => candidate.path !== node.path
              && (candidate.path.startsWith(prefixBack) || candidate.path.startsWith(prefixSlash)))
            .forEach(addPreviewFile);
        }
      });
    }
  } finally {
    pairFuzzyBudgetUntil = Infinity;
  }

  return result;
}

function clearExcelViewer() {
  state.excelWorkbook = null;
  state.excelWorkbooks = [];
  state.excelWorkbookIndex = 0;
  state.excelSheetIndex = 0;
  state.excelScale = 1;
  state.view.rotation = 0;
  els.excelViewer.hidden = true;
  els.excelBookTitle.textContent = "";
  els.excelBookTitle.title = "";
  els.excelTabs.replaceChildren();
  els.excelSheetFrame.removeAttribute("src");
  clearWordViewer();
}

function clearWordViewer() {
  state.wordDoc = null;
  state.wordDocs = [];
  state.wordDocIndex = 0;
  state.wordScale = 1;
  if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  if (els.wordDocTitle) { els.wordDocTitle.textContent = ""; els.wordDocTitle.title = ""; }
  if (els.wordMeta) els.wordMeta.replaceChildren();
  if (els.wordDocFrame) els.wordDocFrame.removeAttribute("src");
}

function formatFileSize(bytes) {
  const n = Number(bytes);
  if (!Number.isFinite(n) || n < 0) return "";
  if (n >= 1048576) return `${(n / 1048576).toFixed(2)} МБ`;
  if (n >= 1024) return `${(n / 1024).toFixed(1)} КБ`;
  return `${n} Б`;
}

function nativeTypeLabel(ext) {
  const e = String(ext || "").toUpperCase();
  if (["MPP", "MPT"].includes(e)) return "Проект Microsoft Project";
  if (["MOV", "MP4", "M4V", "AVI", "MKV", "WEBM", "MPEG", "MPG"].includes(e)) return "Видеофайл";
  if (["ZIP", "RAR", "7Z", "TAR", "GZ"].includes(e)) return "Архив";
  if (["RVT", "RFA", "NWC", "NWD", "IFC"].includes(e)) return "BIM-модель";
  if (["PPT", "PPTX"].includes(e)) return "Презентация";
  if (["VSD", "VSDX"].includes(e)) return "Схема Visio";
  return `Файл .${e.toLowerCase()}`;
}


async function showNativeAppCard(node, options = {}) {
  // Карточка нативного формата: метаданные из ядра (/api/preview),
  // открытие — через /api/open-file. При недоступности ядра — generic-карточка.
  resetPdfPreview();
  let card = {
    type: "native-file",
    name: node.name,
    sourcePath: node.path,
    documentPath: node.path,
    sourceType: (node.extension || "").toUpperCase(),
    message: "Файл открывается через ассоциации Windows или настроенную нативную программу.",
  };
  try {
    const response = await fetch("/api/preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: node.path }),
    });
    const info = await response.json();
    const native = response.ok && info
      ? (info.type === "native_app" ? info : info.fallback || null)
      : null;
    if (native) {
      const label = nativeTypeLabel(native.extension);
      card = {
        type: "native-file",
        name: native.name || node.name,
        sourcePath: node.path,
        documentPath: node.path,
        sourceType: String(native.extension || node.extension || "").toUpperCase(),
        message: `${label} · ${formatFileSize(native.bytes)}. ${native.hint || "Нажмите кнопку, чтобы открыть."}`,
      };
    }
  } catch (error) {
    console.warn("[Launcher] /api/preview unavailable, generic native card:", error);
  }
  showPdfPage(card);
  if (options.fullView) setViewerMode("full");
}

function resetPdfPreview() {
  stopDwgStatusPolling();
  state._userNavigatedDwgPage = false;
  state.view.userZoomed = false;
  state.activePageKey = "";
  state.activePageUrl = "";
  state.renderedPages = [];
  state.activeTxtPath = "";
  state.wordDoc = null;
  state.wordDocs = [];
  state.wordDocIndex = 0;
  if (els.txtViewer) els.txtViewer.hidden = true;
  if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  if (els.mediaVideoViewer) {
    try { els.mediaVideoViewer.pause(); } catch (_) {}
    els.mediaVideoViewer.hidden = true;
    els.mediaVideoViewer.removeAttribute("src");
  }
  // Новый показ стирает ленту целиком: старые миниатюры не смешиваются с новыми.
  els.pdfThumbs.replaceChildren();
  els.pdfPageImage.hidden = true;
  els.pdfPageImage.removeAttribute("src");
  els.viewerEmpty.hidden = true;
  els.viewerEmpty.textContent = "";
  updatePagePosition(null);
  updateViewTransform();
  updateViewerBanner("");
}

async function activateExcelSheet(index) {
  const workbook = state.excelWorkbook;
  const sheet = workbook?.sheets?.[index];
  if (!sheet) return;
  if (sheet.warming) await sheet.warming;
  if (!sheet.url) {
    const response = await fetch("/api/excel/sheet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: workbook.path, sheetIndex: index }),
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Лист Excel не подготовлен");
    Object.assign(sheet, payload);
  }
  state.excelSheetIndex = index;
  [...els.excelTabs.querySelectorAll(".excel-tab")].forEach((tab) => {
    tab.classList.toggle("active", Number(tab.dataset.sheetIndex) === index);
  });
  els.excelSheetFrame.src = sheet.url;
  forwardExcelSheetContextMenu();
}

// ПКМ внутри таблицы: события из same-origin iframe не всплывают в основной
// документ, поэтому меню исходного файла пробрасываем вручную. На чужом
// документе тихо выходим — там остаётся обычное меню браузера.
function forwardExcelSheetContextMenu() {
  let doc = null;
  try {
    doc = els.excelSheetFrame?.contentDocument;
  } catch (_) {
    return;
  }
  if (!doc || doc.__launcherCtxForwarded) return;
  try {
    doc.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      try { event.stopPropagation(); } catch (_) {}
      hideFileContextMenu();
      const info = getActiveSourceInfo();
      const wb = state.excelWorkbook;
      const path = (info && info.path) || (wb && wb.path) || "";
      if (!path) return;
      const rect = els.excelSheetFrame ? els.excelSheetFrame.getBoundingClientRect() : { left: 0, top: 0 };
      showFileContextMenu(rect.left + event.clientX, rect.top + event.clientY, { path, isDir: false, ext: extOfPath(path) });
    });
    doc.__launcherCtxForwarded = true;
  } catch (_) {}
}

// Ждём первой отрисовки листа во фрейме (с таймаутом): иначе большое окно
// открывается пустым раньше таблицы, а прогресс уже погашен. Метка
// data-painted-url отличает свежую навигацию от повторного показа того же URL.
function waitForExcelSheetPaint(timeoutMs = 20000) {
  return new Promise((resolve) => {
    const frame = els.excelSheetFrame;
    const want = frame?.getAttribute("src") || "";
    if (!frame || !want) {
      resolve(false);
      return;
    }
    let settled = false;
    const done = (ok) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try { frame.removeEventListener("load", onLoad); } catch (_) {}
      if (ok) {
        try { frame.dataset.paintedUrl = want; } catch (_) {}
      }
      resolve(ok);
    };
    const onLoad = () => done(true);
    const timer = setTimeout(() => done(false), timeoutMs);
    let painted = "";
    try { painted = frame.dataset.paintedUrl || ""; } catch (_) {}
    try {
      const doc = frame.contentDocument;
      if (doc && doc.readyState === "complete" && painted === want) {
        done(true);
        return;
      }
    } catch (_) {}
    try {
      frame.addEventListener("load", onLoad, { once: true });
    } catch (_) {
      done(false);
    }
  });
}

let _activeExcelWarmingWorkbook = null;

async function warmExcelWorkbook(workbook, activeIndex) {
  _activeExcelWarmingWorkbook = workbook;
  const totalSheets = (workbook.sheets || []).length;
  // Прогреваем в фоне только ближайшие соседние вкладки последовательно,
  // чтобы не подвешивать сервер и не тратить гигабайты памяти на тяжелых файлах.
  const candidates = [activeIndex + 1, activeIndex - 1].filter((idx) => idx >= 0 && idx < totalSheets);
  for (const index of candidates) {
    if (_activeExcelWarmingWorkbook !== workbook || state.excelWorkbook !== workbook || els.excelViewer?.hidden) {
      return;
    }
    const sheet = workbook.sheets[index];
    if (!sheet || sheet.url || sheet.warming) continue;
    sheet.warming = fetch("/api/excel/sheet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: workbook.path, sheetIndex: index }),
    })
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || "Excel sheet preparation failed");
        Object.assign(sheet, payload);
      })
      .catch(() => {})
      .finally(() => { delete sheet.warming; });
    try {
      await sheet.warming;
    } catch (_) {}
  }
}

function renderExcelWorkbookRail() {
  const existingThumbs = els.pdfThumbs.querySelectorAll(".excel-book-thumb");
  if (existingThumbs.length === state.excelWorkbooks.length && existingThumbs.length > 0) {
    // Карточки уже построены: обновляем только активную рамку и не трогаем работающие iframes
    existingThumbs.forEach((thumb, index) => {
      thumb.classList.toggle("active", index === state.excelWorkbookIndex);
    });
    updateRailSelectionHighlight();
    return;
  }
  els.pdfThumbs.replaceChildren();
  state.excelWorkbooks.forEach((workbook, index) => {
    const wrap = document.createElement("div");
    wrap.className = "thumb-wrap";
    const thumb = document.createElement("button");
    thumb.type = "button";
    thumb.className = "pdf-thumb excel-book-thumb";
    thumb.dataset.workbookIndex = String(index);
    thumb.classList.toggle("active", index === state.excelWorkbookIndex);
    thumb.title = workbook.name;
    const preview = document.createElement("div");
    preview.className = "excel-book-preview";
    const frame = document.createElement("iframe");
    frame.src = workbook.thumbnailUrl || "about:blank";
    frame.title = `Миниатюра ${workbook.name}`;
    frame.tabIndex = -1;
    preview.append(frame);
    const label = document.createElement("span");
    label.textContent = workbook.name;
    thumb.append(preview, label);
    let excelClickTimer = null;
    thumb.addEventListener("mouseenter", () => {
      state.activeNavZone = "thumbs";
      if (workbook.path) {
        revealPathInTree(workbook.path, { skipScroll: false });
      }
    });
    thumb.addEventListener("click", (event) => {
      event.stopPropagation();
      state.activeNavZone = "thumbs";
      thumb.focus();
      // Выбор как в дереве; превью — только по обычному клику (как раньше).
      if (workbook.path) selectRailPath(workbook.path, event);
      if (event.shiftKey || event.ctrlKey || event.metaKey) return;
      if (excelClickTimer) return;
      excelClickTimer = setTimeout(() => {
        excelClickTimer = null;
        activateExcelWorkbook(index).catch(showOperationError);
      }, 220);
    });
    thumb.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      if (excelClickTimer) {
        clearTimeout(excelClickTimer);
        excelClickTimer = null;
      }
      activateExcelWorkbook(index).catch(showOperationError);
      setViewerMode("full");
    });
    wrap.append(thumb);
    wrap.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showFileContextMenu(event.clientX, event.clientY, {
        path: workbook.path || "",
        isDir: false,
        ext: workbook.extension || "",
      });
    });
    els.pdfThumbs.append(wrap);
  });
  updateRailSelectionHighlight();
}

async function activateExcelWorkbook(index) {
  const workbook = state.excelWorkbooks[index];
  if (!workbook) return;
  setStageActive(true);
  state.excelWorkbook = workbook;
  state.excelWorkbookIndex = index;
  state.excelSheetIndex = 0;
  state.excelScale = 1;
  els.excelBookTitle.textContent = workbook.name;
  els.excelBookTitle.title = workbook.name;
  renderExcelWorkbookRail();
  els.pdfViewer.classList.remove("empty");
  els.pdfPageImage.hidden = true;
  els.pdfPageImage.removeAttribute("src");
  els.viewerEmpty.hidden = true;
  els.qualityBadge.hidden = true;
  els.excelTabs.replaceChildren();
  (workbook.sheets || []).forEach((sheet) => {
    const tab = document.createElement("button");
    tab.type = "button";
    tab.className = "excel-tab";
    tab.dataset.sheetIndex = String(sheet.index);
    tab.title = `${sheet.name} · ${sheet.rows} строк · ${sheet.columns} столбцов`;
    tab.textContent = sheet.name;
    tab.addEventListener("click", () => activateExcelSheet(sheet.index).catch(showOperationError));
    els.excelTabs.append(tab);
  });
  els.excelViewer.hidden = false;
  if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  els.viewerControls.hidden = false;
  setActiveNativePath(workbook.path);
  revealPathInTree(workbook.path);
  updateViewTransform();
  await activateExcelSheet(0);
  window.setTimeout(() => warmExcelWorkbook(workbook, 0), 250);
}

async function showExcelWorkbooks(workbooks, options = {}) {
  state.excelWorkbooks = workbooks;
  renderExcelWorkbookRail();
  els.pdfViewer?.classList.remove("empty");
  if (els.viewerEmpty) els.viewerEmpty.hidden = true;
  if (options.isSingle || workbooks.length === 1) {
    setStageActive(true);
    await activateExcelWorkbook(0);
    if (options.fullView) setViewerMode("full");
  } else {
    setStageActive(false);
    if (els.excelViewer) els.excelViewer.hidden = true;
    if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  }
}

function renderWordDocumentRail() {
  const existingThumbs = els.pdfThumbs.querySelectorAll(".word-doc-thumb");
  if (existingThumbs.length === state.wordDocs.length && existingThumbs.length > 0) {
    existingThumbs.forEach((thumb, index) => {
      thumb.classList.toggle("active", index === state.wordDocIndex);
    });
    updateRailSelectionHighlight();
    return;
  }
  els.pdfThumbs.replaceChildren();
  state.wordDocs.forEach((docItem, index) => {
    const wrap = document.createElement("div");
    wrap.className = "thumb-wrap";
    const thumb = document.createElement("button");
    thumb.type = "button";
    thumb.className = "pdf-thumb word-doc-thumb";
    thumb.dataset.docIndex = String(index);
    thumb.classList.toggle("active", index === state.wordDocIndex);
    thumb.title = docItem.name;
    const preview = document.createElement("div");
    preview.className = "word-doc-preview";
    const frame = document.createElement("iframe");
    frame.src = docItem.thumbnailUrl || docItem.url || "about:blank";
    frame.title = `Миниатюра ${docItem.name}`;
    frame.tabIndex = -1;
    preview.append(frame);
    const label = document.createElement("span");
    label.textContent = docItem.name;
    thumb.append(preview, label);
    let wordClickTimer = null;
    thumb.addEventListener("mouseenter", () => {
      state.activeNavZone = "thumbs";
      if (docItem.path) {
        revealPathInTree(docItem.path, { skipScroll: false });
      }
    });
    thumb.addEventListener("click", (event) => {
      event.stopPropagation();
      state.activeNavZone = "thumbs";
      thumb.focus();
      if (docItem.path) selectRailPath(docItem.path, event);
      if (event.shiftKey || event.ctrlKey || event.metaKey) return;
      if (wordClickTimer) return;
      wordClickTimer = setTimeout(() => {
        wordClickTimer = null;
        activateWordDocument(index).catch(showOperationError);
      }, 220);
    });
    thumb.addEventListener("dblclick", (event) => {
      event.stopPropagation();
      if (wordClickTimer) {
        clearTimeout(wordClickTimer);
        wordClickTimer = null;
      }
      activateWordDocument(index).catch(showOperationError);
      setViewerMode("full");
    });
    wrap.append(thumb);
    wrap.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      event.stopPropagation();
      showFileContextMenu(event.clientX, event.clientY, {
        path: docItem.path || "",
        isDir: false,
        ext: extOfPath(docItem.path || ""),
      });
    });
    els.pdfThumbs.append(wrap);
  });
  updateRailSelectionHighlight();
}

function forwardWordDocContextMenu() {
  let doc = null;
  try {
    doc = els.wordDocFrame?.contentDocument;
  } catch (_) {
    return;
  }
  if (!doc || doc.__launcherCtxForwarded) return;
  try {
    doc.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      try { event.stopPropagation(); } catch (_) {}
      hideFileContextMenu();
      const info = getActiveSourceInfo();
      const currentDoc = state.wordDoc;
      const path = (info && info.path) || (currentDoc && currentDoc.path) || "";
      if (!path) return;
      const rect = els.wordDocFrame ? els.wordDocFrame.getBoundingClientRect() : { left: 0, top: 0 };
      showFileContextMenu(rect.left + event.clientX, rect.top + event.clientY, { path, isDir: false, ext: extOfPath(path) });
    });
    doc.__launcherCtxForwarded = true;
  } catch (_) {}
}

async function activateWordDocument(index) {
  const docItem = state.wordDocs[index];
  if (!docItem) return;
  setStageActive(true);
  state.wordDoc = docItem;
  state.wordDocIndex = index;
  state.wordScale = 1;
  if (els.wordDocTitle) {
    els.wordDocTitle.textContent = docItem.name;
    els.wordDocTitle.title = docItem.name;
  }
  renderWordDocumentRail();
  els.pdfViewer.classList.remove("empty");
  els.pdfPageImage.hidden = true;
  els.pdfPageImage.removeAttribute("src");
  els.viewerEmpty.hidden = true;
  els.qualityBadge.hidden = true;
  if (els.wordMeta) {
    els.wordMeta.replaceChildren();
    const chip = document.createElement("span");
    chip.className = "excel-tab";
    chip.textContent = `${docItem.paragraphs ?? "?"} абз. · ${docItem.tables ?? "?"} табл. · ${formatFileSize(docItem.bytes)}`;
    els.wordMeta.append(chip);
  }

  if (els.excelViewer) els.excelViewer.hidden = true;
  els.wordViewer.hidden = false;
  els.viewerControls.hidden = false;
  setActiveNativePath(docItem.path);
  if (els.wordOpenNative) {
    els.wordOpenNative.onclick = () => openFileByPath(docItem.path, "native");
  }
  revealPathInTree(docItem.path);
  updateViewTransform();

  els.wordDocFrame.src = docItem.url;
  forwardWordDocContextMenu();
}

async function showWordDocuments(documents, options = {}) {
  state.wordDocs = documents;
  renderWordDocumentRail();
  els.pdfViewer?.classList.remove("empty");
  if (els.viewerEmpty) els.viewerEmpty.hidden = true;
  if (options.isSingle || documents.length === 1) {
    setStageActive(true);
    await activateWordDocument(0);
    if (options.fullView) setViewerMode("full");
  } else {
    setStageActive(false);
    if (els.excelViewer) els.excelViewer.hidden = true;
    if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  }
}

function createPageThumbElement(page) {
  const key = pageKey(page);
  const wrap = document.createElement("div");
  wrap.className = "thumb-wrap";
  const thumb = document.createElement("button");
  thumb.type = "button";
  thumb.className = "pdf-thumb";
  thumb.classList.toggle("missing-preview", page.type === "missing-preview");
  thumb.classList.toggle("is-empty-dwg-sheet", Boolean(page.isEmpty));
  thumb.dataset.pageKey = key;
  thumb.dataset.pageNumber = String(page.page || 1);
  thumb.dataset.docPath = page.documentPath || page.sourcePath || page.previewFor?.path || page.path || "";
  thumb.classList.toggle("active", key === state.activePageKey);
  thumb.title = `${page.name} · клик — выбор листа, двойной клик — на весь экран`;

  if (page.previewType === "TXT") {
    const prev = document.createElement("div");
    prev.className = "txt-thumb-preview";
    prev.textContent = "TXT…";
    thumb.append(prev);
    fillTxtThumbPreview(page, prev);
  } else if (page.previewType === "VIDEO") {
    const missing = document.createElement("div");
    missing.className = "missing-preview-card";
    const ext = (page.previewFor?.type || "VIDEO").toUpperCase();
    missing.textContent = `🎬 ${ext}`;
    thumb.append(missing);
  } else if (page.type === "missing-preview" || page.type === "native-file") {
    const missing = document.createElement("div");
    missing.className = "missing-preview-card";
    const ext = (page.sourceType || "").toUpperCase();
    let icon = "📄";
    if (ext === "GDOC") icon = "🌐";
    else if (ext === "GSHEET") icon = "📊";
    else if (ext === "GSLIDES") icon = "📽️";
    else if (["ZIP", "RAR", "7Z"].includes(ext)) icon = "📦";
    else if (["MPP", "MPT"].includes(ext)) icon = "📊";
    else if (["MOV", "MP4", "M4V", "AVI", "MKV", "WEBM", "MPEG", "MPG"].includes(ext)) icon = "🎬";
    else if (["RVT", "RFA", "NWC", "NWD", "IFC"].includes(ext)) icon = "🏗️";
    else if (["PPT", "PPTX"].includes(ext)) icon = "📽️";
    else if (["VSD", "VSDX"].includes(ext)) icon = "📝";
    else if (ext === "DWG") icon = "📐";
    else if (["DOC", "DOCX"].includes(ext)) icon = "📘";
    else if (["XLS", "XLSX"].includes(ext)) icon = "📗";
    missing.textContent = `${icon} ${ext || "Файл"}`;
    thumb.append(missing);
  } else {
    const img = document.createElement("img");
    img.loading = "eager";
    img.src = page.url;
    img.alt = page.name;
    img.draggable = false;
    if (page.url && page.url.includes("/dwg/")) {
      const isReady = (page.bytes > 0) && !page.url.includes("header_thumb.png") && !page.url.includes("placeholder");
      img.dataset.dwgLoaded = isReady ? "1" : "0";
    }
    img.onerror = () => {
      const retries = Number(img.dataset.retries || "0");
      if (retries < 2) {
        img.dataset.retries = String(retries + 1);
        setTimeout(() => {
          img.src = `${page.url}?retry=${Date.now()}`;
        }, 1200);
      }
    };
    thumb.append(img);
  }
  const label = document.createElement("span");
  label.textContent = page.name;
  thumb.append(label);

  thumb.addEventListener("mouseenter", () => {
    state.activeNavZone = "thumbs";
    const docPath = thumbPathForPage(page);
    if (docPath && state.revealedPath !== docPath) {
      revealPathInTree(docPath, { updateSelection: false, skipScroll: false });
    }
  });

  thumb.addEventListener("click", (event) => {
    event.stopPropagation();
    state._userNavigatedDwgPage = true;
    state.activeNavZone = "thumbs";
    showPdfPage(page);
    const docPath = thumbPathForPage(page);
    if (docPath) {
      revealPathInTree(docPath, { updateSelection: true, skipScroll: false });
    }
    thumb.focus();
    thumb.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
  });

  thumb.addEventListener("dblclick", (event) => {
    event.stopPropagation();
    state._userNavigatedDwgPage = true;
    state.activeNavZone = "thumbs";
    showPdfPage(page);
    const docPath = thumbPathForPage(page);
    if (docPath) {
      revealPathInTree(docPath, { updateSelection: true, skipScroll: false });
    }
    setViewerMode("full");
  });
  wrap.append(thumb);
  wrap.addEventListener("contextmenu", (event) => {
    event.preventDefault();
    event.stopPropagation();
    const menuPath = thumbPathForPage(page);
    showFileContextMenu(event.clientX, event.clientY, {
      path: menuPath,
      isDir: false,
      ext: extOfPath(menuPath),
    });
  });
  return wrap;
}

async function appendPagesToViewer(pages, insertAfterKey = null, epoch = null) {
  if (!pages || !pages.length) return;
  if (epoch !== null && state.renderEpoch !== epoch) return;
  clearExcelViewer();
  els.pdfViewer.classList.toggle("empty", false);
  els.viewerEmpty.hidden = true;

  // Снимки существующих ключей один раз: проверка каждого нового
  // элемента идёт за O(1), а не сканированием всего DOM и массива.
  const knownStateKeys = new Set();
  for (const p of state.renderedPages) {
    try { knownStateKeys.add(pageKey(p)); } catch (_) {}
  }
  const existingDomKeys = new Set();
  els.pdfThumbs.querySelectorAll(".pdf-thumb").forEach((el) => {
    if (el.dataset.pageKey) existingDomKeys.add(el.dataset.pageKey);
  });

  // Якорь вставки вычисляем один раз на весь вызов.
  let anchorNode = null;
  let appendAtEnd = true;
  if (insertAfterKey) {
    const afterThumb = els.pdfThumbs.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(insertAfterKey)}"]`);
    const afterWrap = afterThumb ? (afterThumb.closest(".thumb-wrap") || afterThumb) : null;
    if (afterWrap && afterWrap.nextSibling) {
      anchorNode = afterWrap.nextSibling;
      appendAtEnd = false;
    } else if (!afterWrap) {
      const loadMoreBtn = els.pdfThumbs.querySelector(".ribbon-load-more");
      if (loadMoreBtn) { anchorNode = loadMoreBtn; appendAtEnd = false; }
    }
  } else {
    const loadMoreBtn = els.pdfThumbs.querySelector(".ribbon-load-more");
    if (loadMoreBtn) { anchorNode = loadMoreBtn; appendAtEnd = false; }
  }

  // Строим DOM порциями и отдаём управление между ними, чтобы страница
  // не висела на сотнях миниатюр. Отмена прерывает добавление.
  const CHUNK_PAGES = 60;
  for (let start = 0; start < pages.length; start += CHUNK_PAGES) {
    if (state.progressCancelled) return;
    if (epoch !== null && state.renderEpoch !== epoch) return;
    const fragment = document.createDocumentFragment();
    let lastInserted = null;
    const slice = pages.slice(start, start + CHUNK_PAGES);
    for (const page of slice) {
      let key = "";
      try { key = pageKey(page); } catch (_) { continue; }
      if (!knownStateKeys.has(key)) {
        knownStateKeys.add(key);
        if (insertAfterKey) {
          const afterIdx = state.renderedPages.findIndex((p) => { try { return pageKey(p) === insertAfterKey; } catch (_) { return false; } });
          if (afterIdx >= 0) {
            state.renderedPages.splice(afterIdx + 1, 0, page);
          } else {
            state.renderedPages.push(page);
          }
        } else {
          state.renderedPages.push(page);
        }
      }
      if (existingDomKeys.has(key)) {
        continue;
      }
      existingDomKeys.add(key);
      let wrap = null;
      try {
        wrap = createPageThumbElement(page);
      } catch (_) {
        continue;
      }
      fragment.append(wrap);
      lastInserted = wrap;
    }
    if (lastInserted) {
      if (appendAtEnd || !anchorNode) {
        els.pdfThumbs.append(fragment);
      } else {
        els.pdfThumbs.insertBefore(fragment, anchorNode);
      }
      anchorNode = lastInserted.nextSibling;
      appendAtEnd = !anchorNode;
    }
    if (start + CHUNK_PAGES < pages.length) {
      await new Promise((resolve) => setTimeout(resolve, 0));
    }
  }

  if ((!state.activePageKey || !knownStateKeys.has(state.activePageKey)) && state.renderedPages.length) {
    const targetPage = (!state._userNavigatedDwgPage ? state.renderedPages.find((p) => p.bytes > 0 && !p.isEmpty) : null) || state.renderedPages[0];
    showPdfPage(targetPage);
  } else {
    updateActivePdfThumb();
  }
  updateRailSelectionHighlight();
}

function updateRibbonLoadMore() {
  const existing = els.pdfThumbs.querySelector(".ribbon-load-more");
  if (existing) existing.remove();

  // Убираем старый observer
  if (state._ribbonScrollObserver) {
    state._ribbonScrollObserver.disconnect();
    state._ribbonScrollObserver = null;
  }

  if (state.remainingPreviewItems && state.remainingPreviewItems.length > 0) {
    const sentinel = document.createElement("div");
    sentinel.className = "ribbon-load-more";
    const shown = state.totalPreviewCount - state.remainingPreviewItems.length;
    sentinel.textContent = `Загружено ${shown} из ${state.totalPreviewCount} · прокрутите для подгрузки...`;
    els.pdfThumbs.append(sentinel);

    const LOAD_MORE_SIZE = 200;
    let loading = false;
    // Страж принадлежит текущему показу: если пользователь тем временем
    // начал новый показ, молча снимаемся, чтобы не подмешивать старые страницы.
    const obsEpoch = state.renderEpoch || 0;

    const observer = new IntersectionObserver(async (entries) => {
      if (!entries[0]?.isIntersecting || loading) return;
      if (state.progressCancelled) return;
      if (state.renderEpoch !== obsEpoch) {
        observer.disconnect();
        sentinel.remove();
        return;
      }
      if (!state.remainingPreviewItems || !state.remainingPreviewItems.length) {
        observer.disconnect();
        sentinel.remove();
        return;
      }
      loading = true;
      sentinel.textContent = `Подгрузка следующих ${Math.min(LOAD_MORE_SIZE, state.remainingPreviewItems.length)} файлов...`;
      const nextBatch = state.remainingPreviewItems.splice(0, LOAD_MORE_SIZE);
      await loadMorePdfFiles(nextBatch);
      loading = false;
    }, { root: els.pdfThumbs, rootMargin: "0px 300px 0px 0px", threshold: 0 });

    observer.observe(sentinel);
    state._ribbonScrollObserver = observer;
  }
}

function pageKey(page) {
  if (!page) return "";
  if (page.type === "missing-preview" || page.type === "native-file") return `native|${page.sourcePath || page.documentPath || page.name}`;
  if (page.previewType === "IMAGE") return `image|${page.previewFor?.path || page.path || page.url || page.name}`;
  if (page.previewType === "VIDEO") return `video|${page.previewFor?.path || page.path || page.url || page.name}`;
  if (page.previewType === "TXT") return `txt|${page.previewFor?.path || page.path || page.name}`;
  const docPath = page.documentPath || page.sourcePath || page.previewFor?.path || page.path || "";
  return `${docPath}|${page.page || 1}`;
}

function updateActivePdfThumb() {
  const activeKey = state.activePageKey;
  [...els.pdfThumbs.querySelectorAll(".pdf-thumb")].forEach((thumb) => {
    let isAct = false;
    if (thumb.dataset.pageKey) {
      isAct = Boolean(activeKey && thumb.dataset.pageKey === activeKey);
    } else if (thumb.classList.contains("excel-book-thumb") && thumb.dataset.workbookIndex !== undefined) {
      isAct = Number(thumb.dataset.workbookIndex) === state.excelWorkbookIndex;
    } else if (thumb.classList.contains("word-doc-thumb") && thumb.dataset.docIndex !== undefined) {
      isAct = Number(thumb.dataset.docIndex) === state.wordDocIndex;
    }
    thumb.classList.toggle("active", isAct);
    if (!isAct) thumb.classList.remove("selected");
  });
}

function updatePagePosition(page, currentDpiInfo = null) {
  if (els.pagePosition) {
    els.pagePosition.hidden = true;
    els.pagePosition.style.display = "none";
  }
  return;
  // Счётчик «Стр. N из M» слева вверху сцены: всегда видно лист, DPI и точные пиксели
  if (!els.pagePosition) return;
  const num = Number(page?.page) || 0;
  const total = Number(page?.totalPages) || 0;
  if (!num && !total) {
    els.pagePosition.hidden = true;
    return;
  }
  els.pagePosition.hidden = false;
  const pageText = total >= 2 ? `Стр. ${num} из ${total}` : (num ? `Стр. ${num}` : "");
  
  const natW = els.pdfPageImage?.naturalWidth || 0;
  const natH = els.pdfPageImage?.naturalHeight || 0;
  let dpiLabel = "";
  if (currentDpiInfo) {
    dpiLabel = ` · ${currentDpiInfo}`;
  } else {
    const dpi = page?.dpi || state.viewerDpi || 150;
    if (natW && natH) {
      dpiLabel = ` · ${dpi} DPI (${natW}×${natH} px)`;
    } else {
      dpiLabel = ` · ${dpi} DPI`;
    }
  }
  let emptyTag = "";
  if (page?.isEmpty) {
    emptyTag = " · Пустой лист в DWG (оформлен только штамп)";
  }
  els.pagePosition.textContent = `${pageText}${dpiLabel}${emptyTag}`.trim();
}

function setActiveNativePath(path) {
  state.activeNativePath = path || "";
  if (els.viewerControls && state.activeNativePath) els.viewerControls.hidden = false;
}

function thumbPathForPage(page) {
  if (!page) return "";
  return page.previewFor?.path || page.sourcePath || page.documentPath || page.path || "";
}

// Источник текущего кадра для ПКМ в полном экране: всегда исходный файл,
// никогда PNG-кэш. DWG через пару -> путь DWG, Word -> .docx и т.д.
function getActiveSourceInfo() {
  if (els.wordViewer && !els.wordViewer.hidden) {
    const wordPath = (state.wordDoc && state.wordDoc.path) || state.activeNativePath || "";
    if (wordPath) return { path: wordPath, ext: extOfPath(wordPath) };
  }
  if (els.excelViewer && !els.excelViewer.hidden) {
    const excelPath = (state.excelWorkbook && state.excelWorkbook.path) || state.activeNativePath || "";
    if (excelPath) return { path: excelPath, ext: extOfPath(excelPath) };
  }
  if (els.mediaVideoViewer && !els.mediaVideoViewer.hidden && state.activeNativePath) {
    return { path: state.activeNativePath, ext: extOfPath(state.activeNativePath) };
  }
  if (state.activeTxtPath) return { path: state.activeTxtPath, ext: "TXT" };
  const page = (state.renderedPages || []).find((p) => {
    try { return pageKey(p) === state.activePageKey; } catch (_) { return false; }
  });
  const filePath = thumbPathForPage(page);
  if (filePath) return { path: filePath, ext: extOfPath(filePath) };
  if (state.activeNativePath) return { path: state.activeNativePath, ext: extOfPath(state.activeNativePath) };
  if (state.activeDwgPath) return { path: state.activeDwgPath, ext: "DWG" };
  if (state.revealedPath) return { path: state.revealedPath, ext: extOfPath(state.revealedPath) };
  return { path: "", ext: "" };
}

function extOfPath(path) {
  const base = String(path || "").split(/[/\\]/).pop() || "";
  const dot = base.lastIndexOf(".");
  return dot > 0 ? base.slice(dot + 1).toUpperCase() : "";
}

function updateViewerDpiButton(loading = false) {
  if (!els.viewToggleDpi) return;
  const dpi = state.viewerDpi || 150;
  els.viewToggleDpi.textContent = loading ? `${dpi} DPI…` : `${dpi} DPI`;
  els.viewToggleDpi.classList.toggle("dpi-300", dpi === 300);
  els.viewToggleDpi.classList.toggle("dpi-150", dpi === 150);
  els.viewToggleDpi.classList.toggle("dpi-72", dpi === 72);
  els.viewToggleDpi.classList.toggle("loading", loading);
  const nextDpi = dpi === 72 ? 150 : (dpi === 150 ? 300 : 72);
  els.viewToggleDpi.title = `Разрешение окна: ${dpi} DPI. Нажмите для переключения на ${nextDpi} DPI (режимы 72 → 150 → 300)`;
}

let activeHighQualityController = null;

async function requestHighQualityPage(page, targetDpi = (state.viewerDpi || 150)) {
  const sourceDocPath = page.documentPath || page.sourcePath || page.previewFor?.path || page.path || "";
  const pageNum = Number(page.page) || 1;
  if (!sourceDocPath || !pageNum) return;

  const baseKey = pageKey(page);
  const cacheKey = `${baseKey}@${targetDpi}`;
  if (state.highQualityPages.has(cacheKey)) {
    const cached = state.highQualityPages.get(cacheKey);
    if (state.activePageKey === baseKey) {
      state.activePageUrl = cached.url;
      els.pdfPageImage.src = cached.url;
      updateViewerDpiButton(false);
    }
    return;
  }

  if (activeHighQualityController) {
    activeHighQualityController.abort();
    activeHighQualityController = null;
  }
  const controller = new AbortController();
  activeHighQualityController = controller;
  updateViewerDpiButton(true);

  try {
    const isDwg = page.previewType === "DWG_MODEL" || page.previewType === "DWG" || page.sourceType === "DWG" || (page.url && page.url.includes("/dwg/"));
    const endpoint = isDwg ? "/api/dwg/model-page" : "/api/pdf/page";
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: sourceDocPath, page: pageNum, dpi: targetDpi }),
      signal: controller.signal,
    });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || "Page render failed");
    const highPage = {
      ...page,
      ...payload.item,
      documentPath: payload.path || sourceDocPath,
      dpi: payload.dpi || targetDpi,
      cacheHit: payload.cacheHit,
    };
    state.highQualityPages.set(cacheKey, highPage);
    page.bytes = Math.max(page.bytes || 0, payload.bytes || payload.item?.bytes || 1024);
    if (state.activePageKey === baseKey) {
      state.activePageUrl = highPage.url;
      const freshUrl = `${highPage.url}?v=${Date.now()}`;
      els.pdfPageImage.src = freshUrl;
      els.pdfPageImage.onload = () => {
        applyPageView();
        updatePagePosition(highPage);
      };
    }
    // Также сразу обновляем миниатюру в ленте при успешном ответе
    const thumbEl = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(baseKey)}"]`);
    if (thumbEl) {
      const img = thumbEl.querySelector("img");
      if (img) {
        img.dataset.dwgLoaded = "1";
        img.src = `${highPage.url}?v=${Date.now()}`;
      }
    }
  } catch (error) {
    if (error.name === "AbortError") return;
    // Молча оставляем базовое разрешение, если не удалось подгрузить высокое
  } finally {
    if (activeHighQualityController === controller) {
      activeHighQualityController = null;
      updateViewerDpiButton(false);
    }
  }
}

// Текстовый кэш TXT (маленькие файлы целиком, не более ~20 штук).
const txtCache = new Map();

function decodeTxtBytes(buf) {
  const bytes = new Uint8Array(buf);
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch (_) {
    return new TextDecoder("windows-1251").decode(bytes);
  }
}

async function fetchTxtText(sourcePath) {
  let text = txtCache.get(sourcePath);
  if (text !== undefined) return text;
  const response = await fetch(`/api/file/raw?path=${encodeURIComponent(sourcePath)}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const buf = await response.arrayBuffer();
  if (buf.byteLength > 1000000) throw new Error("Файл больше 1 МБ — откройте в программе.");
  text = decodeTxtBytes(buf);
  if (txtCache.size > 20) txtCache.clear();
  txtCache.set(sourcePath, text);
  return text;
}

async function showTxtContent(sourcePath) {
  const box = els.txtContent;
  const view = els.txtViewer;
  if (!box || !view || !sourcePath) return;
  view.hidden = false;
  box.textContent = "Загрузка текста…";
  try {
    const text = await fetchTxtText(sourcePath);
    if (state.activeTxtPath !== sourcePath) return;
    box.textContent = text;
  } catch (error) {
    if (state.activeTxtPath !== sourcePath) return;
    box.textContent = `Не удалось показать текст: ${error?.message || error}`;
  }
}

async function fillTxtThumbPreview(page, el) {
  const src = page.previewFor?.path || page.path || page.sourcePath;
  if (!src) return;
  try {
    const text = await fetchTxtText(src);
    if (!el.isConnected) return;
    const snippet = text.split(/\r?\n/).slice(0, 3).join("\n").slice(0, 180);
    el.textContent = snippet || page.name;
  } catch (_) {
    // Остаётся заглушка «TXT…», вид не ломаем.
  }
}

const pdfjsCache = new Map();
let activePdfRenderTask = null;
let viewerGeneration = 0;

async function getPdfjsDocument(path) {
  if (pdfjsCache.has(path)) {
    return pdfjsCache.get(path).docPromise;
  }
  const rawUrl = `/api/file/raw?path=${encodeURIComponent(path)}`;
  const loadingTask = pdfjsLib.getDocument({
    url: rawUrl,
    isEvalSupported: false // SECURITY (CVE-2024-4367) bypass
  });
  const docPromise = loadingTask.promise;
  pdfjsCache.set(path, { docPromise, lastUsed: Date.now() });
  
  if (pdfjsCache.size > 5) {
    let oldest = null;
    let oldestTime = Infinity;
    for (const [k, v] of pdfjsCache.entries()) {
      if (v.lastUsed < oldestTime) {
        oldestTime = v.lastUsed;
        oldest = k;
      }
    }
    if (oldest && oldest !== path) {
      pdfjsCache.get(oldest).docPromise.then(doc => doc.destroy()).catch(()=>{});
      pdfjsCache.delete(oldest);
    }
  }
  return docPromise;
}

async function renderPdfJsPage(pageObj) {
  const currentGen = ++viewerGeneration;
  const sourcePath = [pageObj.documentPath, pageObj.sourcePath, pageObj.previewFor?.path, state.activeTocPath]
    .find((p) => p && String(p).toLowerCase().endsWith(".pdf")) || pageObj.documentPath || pageObj.sourcePath || pageObj.path;
  const pageNum = Number(pageObj.page) || 1;
  const canvas = document.getElementById("pdfPageCanvas");
  if (!canvas) return;
  
  try {
    const pdfDoc = await getPdfjsDocument(sourcePath);
    if (currentGen !== viewerGeneration) return;
    
    if (pdfjsCache.has(sourcePath)) {
      pdfjsCache.get(sourcePath).lastUsed = Date.now();
    }
    
    const page = await pdfDoc.getPage(pageNum);
    if (currentGen !== viewerGeneration) return;
    
    if (activePdfRenderTask) {
      try {
        await activePdfRenderTask.cancel();
      } catch (e) {}
      activePdfRenderTask = null;
    }
    
    // Dynamic scale to prevent 5GB memory crashes on heavy architectural sheets
    const dpr = window.devicePixelRatio || 1;
    let targetScale = (state.view.scale || 1.0) * dpr;
    if (targetScale < 1.5) targetScale = 1.5; // Baseline quality
    
    const baseViewport = page.getViewport({ scale: 1.0 });
    canvas.dataset.naturalWidth = baseViewport.width;
    canvas.dataset.naturalHeight = baseViewport.height;
    let viewport = page.getViewport({ scale: targetScale });
    
    // Max safe limits (16M pixels area or 8000px side)
    const MAX_PIXELS = 16777216;
    const MAX_DIM = 8000;
    let area = viewport.width * viewport.height;
    
    if (area > MAX_PIXELS || viewport.width > MAX_DIM || viewport.height > MAX_DIM) {
      const scaleDown = Math.min(
        Math.sqrt(MAX_PIXELS / area),
        MAX_DIM / viewport.width,
        MAX_DIM / viewport.height
      );
      targetScale = targetScale * scaleDown;
      viewport = page.getViewport({ scale: targetScale });
    }
    
    canvas.width = viewport.width;
    canvas.height = viewport.height;
    canvas.style.width = baseViewport.width + "px";
    canvas.style.height = baseViewport.height + "px";
    
    const renderContext = {
      canvasContext: canvas.getContext("2d"),
      viewport: viewport
    };
    
    activePdfRenderTask = page.render(renderContext);
    await activePdfRenderTask.promise;
    
    if (currentGen === viewerGeneration) {
      els.pdfPageImage.hidden = true;
      canvas.hidden = false;
      applyPageView();
    }
  } catch (err) {
    if (err.name === 'RenderingCancelledException') return;
    console.error("PDF.js render error:", err);
  }
}

function showPdfPage(page, options = {}) {
  const key = pageKey(page);
  state.activePageKey = key;
  const skipTreeScroll = Boolean(options?.skipTreeScroll);
  if (els.txtViewer) els.txtViewer.hidden = true;
  state.activeTxtPath = "";
  if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  if (els.mediaVideoViewer && page?.previewType !== "VIDEO") {
    try { els.mediaVideoViewer.pause(); } catch (_) {}
    els.mediaVideoViewer.hidden = true;
    els.mediaVideoViewer.removeAttribute("src");
  }

  if (page.previewType === "IMAGE") {
    clearExcelViewer();
    if (els.mediaVideoViewer) {
      try { els.mediaVideoViewer.pause(); } catch (_) {}
      els.mediaVideoViewer.hidden = true;
      els.mediaVideoViewer.removeAttribute("src");
    }
    const sourcePath = page.previewFor?.path || page.path || page.sourcePath;
    setActiveNativePath(sourcePath);
    revealPathInTree(sourcePath, { skipScroll: skipTreeScroll });
    state.activePageUrl = page.url;
    els.pdfPageImage.hidden = false;
    const canvas = document.getElementById("pdfPageCanvas");
    if (canvas) canvas.hidden = true;
    els.viewerEmpty.hidden = true;
    els.pdfViewer.classList.remove("empty");
    els.viewerControls.hidden = false;
    updateActivePdfThumb();
    els.pdfPageImage.onload = () => {
      applyPageView();
      updatePagePosition(page);
    };
    els.pdfPageImage.src = page.url;
    if (els.pdfPageImage.complete && els.pdfPageImage.naturalWidth) {
      applyPageView();
      updatePagePosition(page);
    }
    return;
  }

  if (page.previewType === "VIDEO") {
    clearExcelViewer();
    const sourcePath = page.previewFor?.path || page.path || page.sourcePath;
    setActiveNativePath(sourcePath);
    revealPathInTree(sourcePath, { skipScroll: skipTreeScroll });
    state.activePageUrl = "";
    els.pdfPageImage.hidden = true;
    els.pdfPageImage.removeAttribute("src");
    const canvas = document.getElementById("pdfPageCanvas");
    if (canvas) canvas.hidden = true;
    els.viewerEmpty.hidden = true;
    els.pdfViewer.classList.remove("empty");
    els.viewerControls.hidden = true;
    updateActivePdfThumb();
    updatePagePosition(null);
    if (els.mediaVideoViewer) {
      els.mediaVideoViewer.hidden = false;
      els.mediaVideoViewer.src = page.url;
      els.mediaVideoViewer.onerror = () => {
        showNativeAppCard({ name: page.name, path: sourcePath, extension: extOfPath(sourcePath) });
      };
    }
    return;
  }

  if (page.previewType === "TXT") {
    clearExcelViewer();
    if (els.mediaVideoViewer) {
      try { els.mediaVideoViewer.pause(); } catch (_) {}
      els.mediaVideoViewer.hidden = true;
      els.mediaVideoViewer.removeAttribute("src");
    }
    const sourcePath = page.previewFor?.path || page.path || page.sourcePath;
    setActiveNativePath(sourcePath);
    state.activeTxtPath = sourcePath;
    revealPathInTree(sourcePath, { skipScroll: skipTreeScroll });
    state.activePageUrl = "";
    els.pdfPageImage.hidden = true;
    els.pdfPageImage.removeAttribute("src");
    const canvas = document.getElementById("pdfPageCanvas");
    if (canvas) canvas.hidden = true;
    els.viewerEmpty.hidden = true;
    els.pdfViewer.classList.remove("empty");
    els.viewerControls.hidden = false;
    updateActivePdfThumb();
    updatePagePosition(null);
    showTxtContent(sourcePath);
    return;
  }

  if (page.type === "missing-preview" || page.type === "native-file") {
    clearExcelViewer();
    const sourcePath = page.previewFor?.path || page.sourcePath || page.documentPath || "";
    setActiveNativePath(sourcePath);
    revealPathInTree(sourcePath, { skipScroll: skipTreeScroll });
    state.activePageUrl = "";
    els.pdfPageImage.hidden = true;
    els.pdfPageImage.removeAttribute("src");
    const canvas = document.getElementById("pdfPageCanvas");
    if (canvas) canvas.hidden = true;
    els.viewerEmpty.hidden = false;

    const ext = (page.sourceType || "").toUpperCase();
    let icon = "📄";
    if (ext === "GDOC") icon = "🌐";
    else if (ext === "GSHEET") icon = "📊";
    else if (ext === "GSLIDES") icon = "📽️";
    else if (["ZIP", "RAR", "7Z"].includes(ext)) icon = "📦";
    else if (["MPP", "MPT"].includes(ext)) icon = "📊";
    else if (["MOV", "MP4", "M4V", "AVI", "MKV", "WEBM", "MPEG", "MPG"].includes(ext)) icon = "🎬";
    else if (["RVT", "RFA", "NWC", "NWD", "IFC"].includes(ext)) icon = "🏗️";
    else if (["PPT", "PPTX"].includes(ext)) icon = "📽️";
    else if (["VSD", "VSDX"].includes(ext)) icon = "📝";
    else if (ext === "DWG") icon = "📐";
    else if (["DOC", "DOCX"].includes(ext)) icon = "📘";
    else if (["XLS", "XLSX"].includes(ext)) icon = "📗";

    els.viewerEmpty.innerHTML = `
      <div class="native-file-card">
        <div class="native-file-icon">${icon}</div>
        <div class="native-file-name">${escapeHtml(page.name)}</div>
        <div class="native-file-message">${escapeHtml(page.message || "")}</div>
        <div class="native-file-path" title="${escapeHtml(sourcePath)}">${escapeHtml(sourcePath)}</div>
        <button type="button" class="native-card-open-btn" id="nativeCardOpenBtn">Открыть в программе по умолчанию</button>
        <div class="native-file-hint">Правая кнопка мыши: открыть в программе по умолчанию · открыть в проводнике · скопировать путь</div>
      </div>
    `;

    const nativeCard = els.viewerEmpty.querySelector(".native-file-card");
    if (nativeCard) {
      const openBtn = nativeCard.querySelector("#nativeCardOpenBtn");
      if (openBtn) {
        openBtn.addEventListener("click", () => openFileByPath(sourcePath, "native"));
      }
      nativeCard.addEventListener("contextmenu", (event) => {
        event.preventDefault();
        event.stopPropagation();
        showFileContextMenu(event.clientX, event.clientY, {
          path: sourcePath,
          isDir: false,
          ext: extOfPath(sourcePath),
        });
      });
    }

    els.pdfViewer.classList.remove("empty");
    els.viewerControls.hidden = false;
    updateActivePdfThumb();
    updatePagePosition(null);
    return;
  }

    clearExcelViewer();
  const targetDocPath = thumbPathForPage(page);
  const isPdf = Boolean(targetDocPath && targetDocPath.toLowerCase().endsWith(".pdf") &&
    page.previewType !== "IMAGE" &&
    page.previewType !== "VIDEO" &&
    page.previewType !== "TXT" &&
    page.type !== "missing-preview" &&
    page.type !== "native-file");

  if (isPdf) {
    if (els.mediaVideoViewer) {
      try { els.mediaVideoViewer.pause(); } catch (_) {}
      els.mediaVideoViewer.hidden = true;
      els.mediaVideoViewer.removeAttribute("src");
    }
    if (els.txtViewer) els.txtViewer.hidden = true;
    if (els.wordViewer) els.wordViewer.hidden = true;
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
    if (els.pdfPageImage) {
      els.pdfPageImage.hidden = true;
      els.pdfPageImage.removeAttribute("src");
    }
    const canvas = document.getElementById("pdfPageCanvas");
    if (canvas) canvas.hidden = true;
    els.viewerEmpty.hidden = true;
    els.pdfViewer.classList.remove("empty");
    els.viewerControls.hidden = false;
    if (els.viewToggleDpi) els.viewToggleDpi.hidden = true;
    updateViewerToolButton(false);

    setActiveNativePath(targetDocPath);
    revealPathInTree(targetDocPath, { updateSelection: true, skipScroll: skipTreeScroll });

    if (els.pdfDocViewer) els.pdfDocViewer.hidden = false;
    syncActionGridVisibility();

    const rawUrl = "/api/file/raw?path=" + encodeURIComponent(targetDocPath);
    const targetPageNum = Number(page.page) || 1;

    if (els.pdfDocFrame.dataset.currentDoc === targetDocPath) {
      const win = els.pdfDocFrame.contentWindow;
      if (win && win.PDFViewerApplication && win.PDFViewerApplication.initialized) {
        win.PDFViewerApplication.page = targetPageNum;
      } else {
        els.pdfDocFrame.dataset.targetPage = String(targetPageNum);
      }
    } else {
      els.pdfDocFrame.dataset.currentDoc = targetDocPath;
      els.pdfDocFrame.dataset.targetPage = String(targetPageNum);
      const viewerUrl = "/lib/pdfjs/web/viewer.html?file=" + encodeURIComponent(rawUrl) + "#page=" + targetPageNum;
      els.pdfDocFrame.src = viewerUrl;
    }

    updateActivePdfThumb();
    updatePagePosition(page);
    return;
  }

  // Non-PDF documents (DWG, images, fallback)
  if (els.pdfDocViewer) els.pdfDocViewer.hidden = true;
  if (els.pdfDocFrame) {
    els.pdfDocFrame.dataset.currentDoc = "";
    els.pdfDocFrame.dataset.targetPage = "";
  }
  if (els.viewToggleDpi) els.viewToggleDpi.hidden = false;
  updateViewerToolButton(state.view.panMode);

  const currentDpi = state.viewerDpi || 150;
  const highPage = state.highQualityPages.get(`${key}@${currentDpi}`);
  const displayPage = highPage || page;
  setActiveNativePath(targetDocPath);
  revealPathInTree(targetDocPath, { updateSelection: true, skipScroll: skipTreeScroll });
  state.activePageUrl = displayPage.url;
  els.pdfPageImage.onload = () => {
    applyPageView();
  };
  els.pdfPageImage.src = displayPage.url;
  els.pdfPageImage.hidden = false;
  if (displayPage.url && displayPage.url.includes("/dwg/")) {
    const pNum = Number(displayPage.page) || 1;
    const isReady = (displayPage.bytes > 0) && !displayPage.url.includes("header_thumb.png") && !displayPage.url.includes("placeholder");
    els.pdfPageImage.dataset.dwgLoadedPage = isReady ? `${targetDocPath}|${pNum}` : "";
    if (!isReady && !state.dwgPollTimer && targetDocPath) {
      startDwgStatusPolling(targetDocPath, page.totalPages || 0, state.renderEpoch);
    }
  } else if (els.pdfPageImage) {
    delete els.pdfPageImage.dataset.dwgLoadedPage;
  }
  const canvas = document.getElementById("pdfPageCanvas");
  if (canvas) canvas.hidden = true;
  els.viewerEmpty.hidden = true;
  els.pdfViewer.classList.remove("empty");
  els.viewerControls.hidden = false;
  updateActivePdfThumb();
  updateViewerDpiButton();
  if (els.pdfPageImage.complete && els.pdfPageImage.naturalWidth) {
    applyPageView();
  }
  
  requestHighQualityPage(page, currentDpi);
  
  updatePagePosition(page);
  const hasMultiplePages = (state.renderedPages?.length || 0) > 1 || (Number(page.totalPages) || 0) > 1;
  if (els.viewPrevPage) els.viewPrevPage.hidden = !hasMultiplePages;
  if (els.viewNextPage) els.viewNextPage.hidden = !hasMultiplePages;
  checkAndShowPdfToc(targetDocPath, page.page);
}

function clampPan() {
  const view = state.view;
  const canvas = document.getElementById("pdfPageCanvas");
  const isCanvasActive = canvas && !canvas.hidden;
  if (els.pdfPageImage.hidden && !isCanvasActive) return;
  const naturalWidth = isCanvasActive ? Number(canvas.dataset.naturalWidth || 1000) : els.pdfPageImage.naturalWidth;
  const naturalHeight = isCanvasActive ? Number(canvas.dataset.naturalHeight || 1000) : els.pdfPageImage.naturalHeight;
  if (!naturalWidth || !naturalHeight) return;
  const stage = els.pdfStage.getBoundingClientRect();
  if (!stage.width || !stage.height) return;
  const rotated = Math.abs(view.rotation % 180) === 90;
  const width = (rotated ? naturalHeight : naturalWidth) * view.scale;
  const height = (rotated ? naturalWidth : naturalHeight) * view.scale;
  // Запас видимости края: как минимум 70px или половина размера листа
  const marginX = Math.min(70, width / 2);
  const marginY = Math.min(70, height / 2);
  const maxX = Math.max(0, width / 2 + stage.width / 2 - marginX);
  const maxY = Math.max(0, height / 2 + stage.height / 2 - marginY);
  view.panX = Math.min(maxX, Math.max(-maxX, view.panX));
  view.panY = Math.min(maxY, Math.max(-maxY, view.panY));
}

function updateViewTransform() {
  const view = state.view;
  clampPan();
  const transform = [
    "translate(-50%, -50%)",
    `translate(${view.panX}px, ${view.panY}px)`,
    `rotate(${view.rotation}deg)`,
    `scale(${view.scale})`,
  ].join(" ");
  els.pdfPageImage.style.transform = transform;
  
  const canvas = document.getElementById("pdfPageCanvas");
  if (canvas) canvas.style.transform = transform;



  els.pdfStage.classList.toggle("pan-mode", view.panMode);
  els.pdfStage.classList.toggle("dragging", view.dragging);
  if (state.excelWorkbook) {
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-hand", value: view.panMode }, "*");
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-rotate", value: view.rotation }, "*");
  }
}

function fitPdfPage() {
  if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
    const win = els.pdfDocFrame?.contentWindow;
    if (win && win.PDFViewerApplication && win.PDFViewerApplication.pdfViewer) {
      win.PDFViewerApplication.pdfViewer.currentScaleValue = "page-fit";
      setTimeout(() => {
        const cur = win.PDFViewerApplication.pdfViewer.currentScale;
        if (cur) win.PDFViewerApplication.pdfViewer.currentScaleValue = String(cur);
      }, 100);
    }
    return;
  }
  if (state.excelWorkbook) {
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-fit" }, "*");
    return;
  }
  
  const canvas = document.getElementById("pdfPageCanvas");
  const isCanvasActive = canvas && !canvas.hidden;
  const contentWidth = isCanvasActive ? Number(canvas.dataset.naturalWidth || 1000) : els.pdfPageImage.naturalWidth;
  const contentHeight = isCanvasActive ? Number(canvas.dataset.naturalHeight || 1000) : els.pdfPageImage.naturalHeight;
  
  if (!contentWidth || !contentHeight) {
    state.view.scale = 1;
    state.view.fitScale = 1;
    state.view.panX = 0;
    state.view.panY = 0;
    updateViewTransform();
    return;
  }
  
  
  const stage = els.pdfStage.getBoundingClientRect();
  // Сцена ещё не разложена (нулевые размеры): не портим масштаб крошечным
  // вписыванием, дождёмся следующего кадра.
  if (stage.width < 10 || stage.height < 10) {
    requestAnimationFrame(() => requestAnimationFrame(fitPdfPage));
    return;
  }
  const rotated = Math.abs(state.view.rotation % 180) === 90;
  const imageWidth = rotated ? contentHeight : contentWidth;
  const imageHeight = rotated ? contentWidth : contentHeight;
  const availableWidth = Math.max(100, stage.width - 36);
  const availableHeight = Math.max(100, stage.height - 86);
  const fit = Math.min(availableWidth / imageWidth, availableHeight / imageHeight);
  state.view.fitScale = fit || 1;
  state.view.scale = state.view.fitScale;
  state.view.panX = 0;
  state.view.panY = 0;
  state.view.userZoomed = false;
  updateViewTransform();
}

function zoomPdf(factor, originX = null, originY = null) {
  if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
    const win = els.pdfDocFrame?.contentWindow;
    if (win && win.PDFViewerApplication) {
      if (factor > 1) {
        win.PDFViewerApplication.zoomIn();
      } else {
        win.PDFViewerApplication.zoomOut();
      }
    }
    return;
  }
  const isStageViewing = state.viewMode === "full" || els.pdfViewer?.classList.contains("stage-active");
  if (!isStageViewing) {
    zoomThumbs(factor);
    return;
  }
  if (state.excelWorkbook) {
    state.excelScale = Math.min(3, Math.max(0.35, state.excelScale * factor));
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-zoom", value: state.excelScale }, "*");
    return;
  }
  if (state.wordDoc) {
    state.wordScale = Math.min(3, Math.max(0.35, (state.wordScale || 1) * factor));
    els.wordDocFrame.contentWindow?.postMessage({ type: "launcher-sheet-zoom", value: state.wordScale }, "*");
    return;
  }
  const canvas = document.getElementById("pdfPageCanvas");
  const isCanvasActive = canvas && !canvas.hidden;
  if (els.pdfPageImage.hidden && !isCanvasActive) return;
  const oldScale = state.view.scale;
  const newScale = Math.min(8, Math.max(0.05, oldScale * factor));
  if (newScale === oldScale) return;

  // Если переданы координаты курсора относительно экрана, масштабируем относительно этой точки
  if (originX !== null && originY !== null && els.pdfStage) {
    const stageRect = els.pdfStage.getBoundingClientRect();
    if (stageRect.width > 0 && stageRect.height > 0) {
      const cx = originX - (stageRect.left + stageRect.width / 2);
      const cy = originY - (stageRect.top + stageRect.height / 2);
      const ratio = newScale / oldScale;
      state.view.panX = cx - (cx - state.view.panX) * ratio;
      state.view.panY = cy - (cy - state.view.panY) * ratio;
    }
  }

  state.view.scale = newScale;
  state.view.userZoomed = true;
  updateViewTransform();
}

function updateScaleIndicator() {
  if (els.scaleResetBtn) {
    const pct = Math.round((state.treeScale || 1) * 100);
    els.scaleResetBtn.textContent = `${pct}%`;
  }
}

function zoomThumbs(factor) {
  state.thumbScale = Math.min(5, Math.max(0.4, Number((state.thumbScale * factor).toFixed(2))));
  els.pdfThumbs.style.setProperty("--thumb-scale", String(state.thumbScale));
  try {
    localStorage.setItem("launcher_thumb_scale", String(state.thumbScale));
  } catch {}
  updateScaleIndicator();
}

function zoomTree(factor) {
  state.treeScale = Math.min(2.5, Math.max(0.75, Number(((state.treeScale || 1) * factor).toFixed(2))));
  document.documentElement.style.setProperty("--tree-scale", String(state.treeScale));
  try {
    localStorage.setItem("launcher_tree_scale", String(state.treeScale));
  } catch {}
  updateScaleIndicator();
}

function applyPageView() {
  if (state.view.userZoomed) {
    updateViewTransform();
    return;
  }
  fitPdfPage();
}

function setStageActive(active) {
  const isAct = Boolean(active);
  if (els.pdfViewer) els.pdfViewer.classList.toggle("stage-active", isAct);
  if (els.pdfStage) els.pdfStage.classList.toggle("active-stage", isAct);
  const showControls = state.viewMode === "full" || isAct;
  if (els.viewerControls) els.viewerControls.hidden = !showControls;
  updateObjectButtons();
  if (isAct) {
    requestAnimationFrame(() => requestAnimationFrame(fitPdfPage));
  }
}

function setViewerMode(mode) {
  const wasFull = state.viewMode === "full";
  state.viewMode = mode;
  state.view.userZoomed = false;
  els.shell.classList.toggle("full-view", mode === "full");
  if (mode === "full") {
    setStageActive(true);
    if (els.viewerControls) els.viewerControls.hidden = false;
  } else {
    setStageActive(false);
    if (els.pdfTocDrawer) els.pdfTocDrawer.hidden = true;
    if (els.viewerControls) els.viewerControls.hidden = true;
  }
  updateObjectButtons();
  const showControls = mode === "full" || els.pdfViewer?.classList.contains("stage-active");
  if (els.viewerControls) els.viewerControls.hidden = !showControls;
  const hasMultiplePages = (state.renderedPages?.length || 0) > 1 || (Number(state.renderedPages?.[0]?.totalPages) || 0) > 1;
  if (els.viewPrevPage) els.viewPrevPage.hidden = !hasMultiplePages;
  if (els.viewNextPage) els.viewNextPage.hidden = !hasMultiplePages;

  // Возврат из полноэкранного (Окно 3 -> Окно 2 -> Окно 1):
  // 1. В Окне 1 (дереве) гарантированно подсвечивается и выбирается этот файл!
  // 2. В Окне 2 (ленте) гарантированно центрируется и подсвечивается миниатюра текущего листа!
  if (wasFull && mode !== "full") {
    state.activeNavZone = "thumbs";
    const activePage = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey) || state.renderedPages?.[0];
    const docPath = (activePage && (thumbPathForPage(activePage) || activePage.documentPath || activePage.sourcePath)) || state.revealedPath || "";
    if (docPath) {
      revealPathInTree(docPath, { updateSelection: true, skipScroll: false });
    }
    if (state.activePageKey) {
      updateActivePdfThumb();
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          try {
            const thumbEl = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(state.activePageKey)}"]`);
            if (thumbEl) {
              thumbEl.focus();
              thumbEl.scrollIntoView({ behavior: "smooth", block: "center" });
            }
          } catch (e) {}
        });
      });
    }
  } else if (state.revealedPath) {
    revealPathInTree(state.revealedPath);
  }
  requestAnimationFrame(() => requestAnimationFrame(() => {
    fitPdfPage();
  }));
}

function chunkPreviewItems(items) {
  const chunks = [];
  let currentChunk = [];
  let currentType = null;
  const maxForType = (type) => (type === "DWG_MODEL" ? 1 : type === "WORD" ? 1 : type === "EXCEL" ? 1 : 10);

  for (const item of items) {
    const type = item.previewType || "PDF";
    if (currentChunk.length > 0 && (currentType !== type || currentChunk.length >= maxForType(type))) {
      chunks.push(currentChunk);
      currentChunk = [];
    }
    currentType = type;
    currentChunk.push(item);
  }
  if (currentChunk.length > 0) {
    chunks.push(currentChunk);
  }
  return chunks;
}

const PDF_RENDER_CONCURRENCY = 3;
// DWG рендерится через общий AutoCAD COM: параллельные запуски дерутся
// за CAD-процесс, поэтому пачки DWG_MODEL идут строго по одной, а PDF —
// по-прежнему до трёх параллельно. Семафор общий на все показы: эпохи
// и отмена проверяются внутри renderBatch, зависший слот отдаётся в finally.
const DWG_RENDER_CONCURRENCY = 1;
let dwgActiveCount = 0;
const dwgWaiters = [];
function acquireDwgSlot() {
  if (dwgActiveCount < DWG_RENDER_CONCURRENCY) {
    dwgActiveCount += 1;
    return Promise.resolve();
  }
  return new Promise((resolve) => dwgWaiters.push(resolve));
}
function releaseDwgSlot() {
  dwgActiveCount = Math.max(0, dwgActiveCount - 1);
  const next = dwgWaiters.shift();
  if (next) {
    dwgActiveCount += 1;
    next();
  }
}
const PDF_FETCH_TIMEOUT_MS = 300000;
// 15 секунд молотили /api/objects/diff каждые 15 с (живое облако H:, полный
// скан на каждое изменение) и могли перезагружать дерево под руками. 10 минут.
const DIFF_POLL_INTERVAL_MS = 600000;
const PDF_PREVIEW_DPI = 72;
const PDF_QUALITY_DPI = 300;

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "";
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} КБ`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} МБ`;
}

function formatEta(ms) {
  if (!ms || ms < 0) return "";
  const sec = Math.ceil(ms / 1000);
  if (sec < 60) return `~${sec} сек.`;
  const min = Math.ceil(sec / 60);
  return `~${min} мин.`;
}

async function renderExcelWorkbooks(excelFiles, options = {}) {
  stopProgress(false, true);
  const myEpoch = (state.renderEpoch = (state.renderEpoch || 0) + 1);
  setTreeBrowseMode(false);
  const isSingle = Boolean(options.singleFile) || excelFiles.length === 1;
  if (options.fullView) {
    setViewerMode("full");
  } else if (state.viewMode !== "full") {
    setViewerMode("standard");
  }
  setStageActive(isSingle);
  resetPdfPreview();
  startProgress("Подготовка Excel", `${excelFiles.length} книг · HTML-просмотр без редактирования`);
  // Долгое чтение: полоска не должна замирать на 92.
  // Цифры на шкале — только движение, не обещание «почти готово».
  state.progressEase = {
    base: 8,
    spent0: Date.now(),
    estMs: 90000,
  };
  const workbooks = [];
  const failed = [];
  for (let index = 0; index < excelFiles.length; index += 1) {
    if (state.progressCancelled || state.renderEpoch !== myEpoch) {
      beaconPerf("excel-open-cancelled", 0, `before-fetch ${excelFiles.length} files`);
      return;
    }
    const excelFile = excelFiles[index];
    els.progressDetail.textContent = `Книга ${index + 1} из ${excelFiles.length}: ${excelFile.name} — читается…`;
    const controller = createOperationController();
    const timeoutSec = 300;
    const timeoutId = setTimeout(() => controller.abort(), timeoutSec * 1000);
    try {
      const response = await fetch("/api/excel/workbook", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: excelFile.path }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `Не удалось прочитать файл: ${excelFile.name}`);
      workbooks.push(payload);
      const doneShare = workbooks.length / excelFiles.length;
      state.progressShown = Math.max(state.progressShown || 0, 8 + doneShare * 80);
      state.progressEase = {
        base: state.progressShown,
        spent0: Date.now(),
        estMs: 60000,
      };
      els.progressDetail.textContent = `Готово ${workbooks.length} из ${excelFiles.length}: ${excelFile.name}`;
    } catch (err) {
      clearTimeout(timeoutId);
      if (state.progressCancelled || state.renderEpoch !== myEpoch) {
        beaconPerf("excel-open-cancelled", 0, excelFile.name || "");
        return;
      }
      const isTimeout = err?.name === "AbortError";
      const errMsg = isTimeout
        ? `Не удалось прочитать файл (превышено время ожидания ${timeoutSec} с)`
        : (err?.message || `Не удалось прочитать файл: ${excelFile.name}`);
      failed.push(`${excelFile.name}: ${errMsg}`);
      els.progressDetail.textContent = `Ошибка в книге ${index + 1} из ${excelFiles.length}: ${excelFile.name} — пропускаем`;
    }
  }
  if (state.progressCancelled || state.renderEpoch !== myEpoch) {
    beaconPerf("excel-open-cancelled", 0, `before-show ${workbooks.length} books`);
    return;
  }
  if (!workbooks.length) {
    const firstError = failed[0] || `Не удалось прочитать файл: ${excelFiles[0]?.name || "Excel"}`;
    showOperationError(new Error(firstError));
    return;
  }
  await showExcelWorkbooks(workbooks, { isSingle, fullView: options.fullView });
  // Ждать рисунок листа только если сразу открывается большое окно.
  // Несколько книг: лента уже должна быть видна, полоску на 20 секунд не держать.
  if (!state.progressCancelled && state.renderEpoch === myEpoch && isSingle) {
    await waitForExcelSheetPaint(20000).catch(() => {});
  }
  if (state.renderEpoch !== myEpoch) return;
  const sheets = workbooks.reduce((total, workbook) => total + (workbook.sheets?.length || 0), 0);
  const doneText = `Готово ${workbooks.length} из ${excelFiles.length} книг · ${sheets} листов · лимит ${workbooks[0]?.maxRows || 2000} строк на лист`;
  finishProgress(failed.length ? `${doneText} · ошибок: ${failed.length}` : doneText);
}

async function renderWordDocuments(wordFiles, options = {}) {
  stopProgress(false, true);
  const myEpoch = (state.renderEpoch = (state.renderEpoch || 0) + 1);
  setTreeBrowseMode(false);
  const isSingle = Boolean(options.singleFile) || wordFiles.length === 1;
  if (options.fullView) {
    setViewerMode("full");
  } else if (state.viewMode !== "full") {
    setViewerMode("standard");
  }
  setStageActive(isSingle);
  resetPdfPreview();
  startProgress("Подготовка Word", `${wordFiles.length} документов · HTML-просмотр`);
  state.progressEase = {
    base: 8,
    spent0: Date.now(),
    estMs: 30000,
  };
  const documents = [];
  const failed = [];
  for (let index = 0; index < wordFiles.length; index += 1) {
    if (state.progressCancelled || state.renderEpoch !== myEpoch) {
      return;
    }
    const wordFile = wordFiles[index];
    els.progressDetail.textContent = `Документ ${index + 1} из ${wordFiles.length}: ${wordFile.name} — читается…`;
    const controller = createOperationController();
    const timeoutSec = 60;
    const timeoutId = setTimeout(() => controller.abort(), timeoutSec * 1000);
    try {
      const response = await fetch("/api/word/document", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: wordFile.path }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || `Не удалось прочитать файл: ${wordFile.name}`);
      documents.push({ path: wordFile.path, name: wordFile.name, ...payload });
      const doneShare = documents.length / wordFiles.length;
      state.progressShown = Math.max(state.progressShown || 0, 8 + doneShare * 80);
      state.progressEase = {
        base: state.progressShown,
        spent0: Date.now(),
        estMs: 30000,
      };
      els.progressDetail.textContent = `Готово ${documents.length} из ${wordFiles.length}: ${wordFile.name}`;
    } catch (err) {
      clearTimeout(timeoutId);
      if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
      const isTimeout = err?.name === "AbortError";
      const errMsg = isTimeout
        ? `Не удалось прочитать файл (превышено время ожидания ${timeoutSec} с)`
        : (err?.message || `Не удалось прочитать файл: ${wordFile.name}`);
      failed.push(`${wordFile.name}: ${errMsg}`);
      els.progressDetail.textContent = `Ошибка в документе ${index + 1} из ${wordFiles.length}: ${wordFile.name} — пропускаем`;
    }
  }
  if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
  if (!documents.length) {
    const firstError = failed[0] || `Не удалось прочитать файл: ${wordFiles[0]?.name || "Word"}`;
    showOperationError(new Error(firstError));
    return;
  }
  await showWordDocuments(documents, { isSingle, fullView: options.fullView });
  if (state.renderEpoch !== myEpoch) return;
  const doneText = `Готово ${documents.length} из ${wordFiles.length} документов Word`;
  finishProgress(failed.length ? `${doneText} · ошибок: ${failed.length}` : doneText);
}

async function renderSelectedFiles(options = {}) {
  const previewItems = collectPreviewFilesForDisplay();
  if (!previewItems.length) {
    startProgress("Превью не найдено", "Выберите папку или файлы (PDF, DWG, Word, Excel).");
    finishProgress("Превью не найдено");
    return;
  }
  const excelItems = previewItems.filter((item) => item.previewType === "EXCEL");
  if (excelItems.length === previewItems.length && excelItems.length > 0) {
    await renderExcelWorkbooks(excelItems);
    return;
  }
  const wordItems = previewItems.filter((item) => item.previewType === "WORD");
  if (wordItems.length === previewItems.length && wordItems.length > 0) {
    await renderWordDocuments(wordItems);
    return;
  }
  await renderSelectedPdfFiles(previewItems, options);
}

async function renderSelectedPdfFiles(previewItems = collectPreviewFilesForDisplay(), options = {}) {
  if (!previewItems.length) {
    startProgress("Превью не найдено", "Выберите папку или файлы (PDF, DWG, Word, Excel).");
    finishProgress("Превью не найдено");
    return;
  }

  const isSingle = options.singleFile || previewItems.length === 1;
  // Новый показ гасит предыдущий: поднимаем эпоху и добиваем старые запросы.
  // Иначе два параллельных рендера месят одну ленту и вешают страницу
  // (типично: PDF ещё грузится, а уже дважды щёлкнули DWG).
  stopProgress(false, true);
  const myEpoch = (state.renderEpoch = (state.renderEpoch || 0) + 1);
  // Показ выделение не меняет: оно уже выставлено вызывающим
  // (чип — все файлы, файл — один, «Отобразить» — текущее).
  // Лишь перекрашиваем дерево на месте, без перестройки.
  updateTreeSelectionHighlight();
  setTreeBrowseMode(false);
  // TXT-одиночка — тоже сначала в ленту (как PDF/Word/Excel):
  // крупно только по двойному клику на миниатюре.
  if (options.fullView) {
    setViewerMode("full");
  } else if (state.viewMode !== "full") {
    setViewerMode("standard");
  }

  // Большие папки: загружаем первые 200 файлов, остальные автоподгрузкой при скролле
  const FIRST_PAGE_SIZE = 200;
  let itemsToRender = previewItems;
  if (!isSingle && previewItems.length > FIRST_PAGE_SIZE) {
    state.remainingPreviewItems = previewItems.slice(FIRST_PAGE_SIZE);
    state.totalPreviewCount = previewItems.length;
    itemsToRender = previewItems.slice(0, FIRST_PAGE_SIZE);
  } else if (!isSingle) {
    state.remainingPreviewItems = [];
    state.totalPreviewCount = previewItems.length;
  } else {
    state.remainingPreviewItems = [];
    state.totalPreviewCount = 1;
  }

  resetPdfPreview();

  const batches = chunkPreviewItems(itemsToRender);
  const pageGroups = batches.map((batch) => {
    const itemsToFetch = batch.filter((item) => item?.type !== "missing-preview" && item?.type !== "native-file" && item?.previewType !== "IMAGE" && item?.previewType !== "VIDEO" && item?.previewType !== "TXT");
    if (!itemsToFetch.length) {
      return batch;
    }
    return null;
  });
  const renderableBatchCount = batches.filter((batch) => {
    return batch.some((item) => item?.type !== "missing-preview" && item?.type !== "native-file" && item?.previewType !== "IMAGE" && item?.previewType !== "VIDEO" && item?.previewType !== "TXT");
  }).length;

  let nextCommitBatchIndex = 0;
  let isFlushing = false;
  let flushRequested = false;

  async function flushReadyBatches() {
    if (isFlushing) {
      flushRequested = true;
      return;
    }
    isFlushing = true;
    try {
      do {
        flushRequested = false;
        while (!state.progressCancelled && state.renderEpoch === myEpoch && nextCommitBatchIndex < batches.length) {
          const readyPages = pageGroups[nextCommitBatchIndex];
          if (!readyPages) break;
          nextCommitBatchIndex += 1;
          if (readyPages.length) {
            await appendPagesToViewer(readyPages, null, myEpoch);
          }
        }
      } while (flushRequested && !state.progressCancelled && state.renderEpoch === myEpoch);
    } finally {
      isFlushing = false;
    }
  }

  const allErrors = [];
  let totalPages = 0;
  let renderedPages = 0;
  let nextBatchIndex = 0;
  let completedBatches = batches.length - renderableBatchCount;
  let completedFiles = 0;
  // Счётчики только для DWG: пачки DWG_MODEL всегда по одному файлу,
  // текст «Модель N из M» опирается на них, а не на общий completedFiles.
  const totalDwgFiles = itemsToRender.filter((item) => item?.previewType === "DWG_MODEL").length;
  let completedDwgFiles = 0;
  const renderStartTime = Date.now();

  const firstItem = itemsToRender[0];
  const isCloud = (firstItem?.path || "").startsWith("H:") || (firstItem?.path || "").includes("Общие диски");
  const singleDetail = `${firstItem?.name || "Файл"} — создаём страницы для просмотра${isCloud ? " · Файл расположен в облачном диске" : ""}`;

  startProgress(
    isSingle ? "Подготовка документа" : "Подготовка превью",
    isSingle ? singleDetail : `${itemsToRender.length} файлов · подготовка...`
  );
  // Ensure UI updates before heavy processing
  await new Promise(requestAnimationFrame);

  function refreshRenderProgress() {
    if (state.progressCancelled) return;
    const percent = Math.min(99, Math.round((completedFiles / itemsToRender.length) * 100));
    state.progressShown = percent;
    const elapsed = Date.now() - renderStartTime;
    state.progressEase = {
      base: percent,
      spent0: Date.now(),
      estMs: estimateBatchRemainMs(elapsed, completedFiles, itemsToRender.length),
    };
    els.progressValue.textContent = `${percent}%`;
    els.progressFill.style.width = `${percent}%`;
    if (isSingle) {
      els.progressDetail.textContent = singleDetail;
    } else {
      const eta = completedFiles > 0 ? formatEta((elapsed / completedFiles) * (itemsToRender.length - completedFiles)) : "";
      const totalLabel = state.totalPreviewCount > itemsToRender.length
        ? ` (из ${state.totalPreviewCount} всего)`
        : "";
      const batchCount = Math.max(1, batches.length);
      const curBatch = batches[Math.min(completedBatches, batchCount - 1)] || [];
      const firstIdx = completedFiles + 1;
      const lastIdx = Math.min(itemsToRender.length, completedFiles + curBatch.length);
      const curName = (curBatch[0] && curBatch[0].name) || "";
      els.progressDetail.textContent =
        `Пачка ${Math.min(completedBatches + 1, batchCount)} из ${batchCount}`
        + ` · Файлы ${firstIdx}–${lastIdx} из ${itemsToRender.length}${totalLabel}`
        + (curName ? ` · Сейчас: ${curName}` : "")
        + ` · Готово: ${completedFiles} файлов`
        + ` · стр. ${renderedPages}${eta ? ` · ${eta}` : ""}`;
    }
    // Лента пополняется инкрементально из renderBatch (appendPagesToViewer):
    // полная перестройка здесь больше не нужна и вешала страницу.
  }

  async function renderBatch(batchIndex) {
    if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
    const batch = batches[batchIndex];
    const itemsToFetch = batch.filter((item) => item?.type !== "missing-preview" && item?.type !== "native-file" && item?.previewType !== "IMAGE" && item?.previewType !== "VIDEO" && item?.previewType !== "TXT");
    if (!itemsToFetch.length) {
      // Готовые элементы (картинки, карточки) — в pageGroups и flush по порядку
      pageGroups[batchIndex] = batch;
      await flushReadyBatches();
      return;
    }
    if (state.renderEpoch !== myEpoch) return;

    const isDwg = itemsToFetch[0]?.previewType === "DWG_MODEL";
    const isExcel = itemsToFetch[0]?.previewType === "EXCEL";
    const isWord = itemsToFetch[0]?.previewType === "WORD";
    const batchTimeout = isDwg ? 600000 : isExcel ? 180000
      : Math.max(180000, Math.min(PDF_FETCH_TIMEOUT_MS, 60000 * Math.max(1, itemsToFetch.length)));
    let controller = null;
    let attempt = 0;
    let batchDone = false;
    while (!batchDone && attempt < 2) {
      attempt += 1;
      if (attempt > 1 && !isSingle) {
        els.progressDetail.textContent = (isDwg && totalDwgFiles > 0)
          ? `Модель ${completedDwgFiles + 1} из ${totalDwgFiles}: ${itemsToFetch[0]?.name || "чертёж"} — повторная попытка…`
          : `PDF ${completedFiles} из ${itemsToRender.length} · повторная попытка: ${itemsToFetch[0]?.name || "пачка"}`;
      }
      if (attempt === 1 && isDwg && totalDwgFiles > 0 && !state.progressCancelled) {
        els.progressDetail.textContent = `Модель ${completedDwgFiles + 1} из ${totalDwgFiles}: ${itemsToFetch[0]?.name || "чертёж"} — рендерится…`;
      }
      try {
        controller = new AbortController();
        state.operationControllers.push(controller);
        const timeoutId = setTimeout(() => controller.abort(), batchTimeout);

        const _batchT0 = performance.now();
        let payload = null;

        if (isWord) {
          const wordDocs = [];
          for (const item of itemsToFetch) {
            try {
              const res = await fetch("/api/word/document", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: item.path }),
                signal: controller.signal,
              });
              if (res.ok) {
                const data = await res.json();
                wordDocs.push({
                  name: item.name,
                  path: item.path,
                  sourcePath: item.path,
                  sourceName: item.name,
                  sourceType: "WORD",
                  pages: 1,
                  renderedPages: 1,
                  items: [{
                    page: 1,
                    url: data.thumbnailUrl || data.url,
                    previewType: "WORD",
                  }],
                });
              }
            } catch (_) {}
          }
          clearTimeout(timeoutId);
          if (state.progressCancelled) return;
          payload = { documents: wordDocs, totalPages: wordDocs.length, renderedPages: wordDocs.length, dpi: PDF_PREVIEW_DPI, errors: [] };
        } else if (isExcel) {
          const excelDocs = [];
          for (const item of itemsToFetch) {
            try {
              const res = await fetch("/api/excel/workbook", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ file: item.path }),
                signal: controller.signal,
              });
              if (res.ok) {
                const data = await res.json();
                excelDocs.push({
                  name: item.name,
                  path: item.path,
                  sourcePath: item.path,
                  sourceName: item.name,
                  sourceType: "EXCEL",
                  pages: (data.sheets || []).length || 1,
                  renderedPages: 1,
                  items: [{
                    page: 1,
                    url: data.thumbnailUrl,
                    previewType: "EXCEL",
                  }],
                });
              }
            } catch (_) {}
          }
          clearTimeout(timeoutId);
          if (state.progressCancelled) return;
          payload = { documents: excelDocs, totalPages: excelDocs.length, renderedPages: excelDocs.length, dpi: PDF_PREVIEW_DPI, errors: [] };
        } else {
          const endpoint = isDwg ? "/api/dwg/model-render" : "/api/pdf/render";
          const requestBody = {
            files: itemsToFetch.map((file) => file.path),
            dpi: PDF_PREVIEW_DPI,
            firstPageOnly: false,
            force: Boolean(options?.force),
          };

          const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(requestBody),
            signal: controller.signal,
          });
          clearTimeout(timeoutId);

          if (state.progressCancelled) return;
          payload = await response.json();
          const _hits = (payload.documents || []).filter((d) => d.cacheHit).length;
          beaconPerf("display-batch", performance.now() - _batchT0, `files=${itemsToFetch.length} hits=${_hits}/${itemsToFetch.length}`);
          if (!response.ok) {
            if (state.progressCancelled) return;
            allErrors.push({
              document: itemsToFetch.map((f) => f.name).join(", "),
              error: payload.error || `HTTP ${response.status}`,
            });
            const errCards = itemsToFetch.map((item) => ({
              type: "missing-preview",
              name: item?.name || "Документ",
              documentPath: item?.path || "",
              sourcePath: item?.path || "",
              sourceType: item?.extension || "PDF",
              message: payload.error || "Ошибка превью. Откройте файл через кнопку «Открыть».",
            }));
            pageGroups[batchIndex] = errCards;
            await flushReadyBatches();
            batchDone = true;
            return;
          }
        }

        if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
        totalPages += payload.totalPages || 0;
        renderedPages += payload.renderedPages || 0;
        allErrors.push(...(payload.errors || []));

        const batchPages = (payload.documents || []).flatMap((document) => {
          const matchedItem = itemsToFetch.find((f) => f.path === (document.sourcePath || document.path))
            || itemsToFetch.find((f) => f.name === (document.sourceName || document.name))
            || itemsToFetch[0];
          const realSourcePath = document.sourcePath || matchedItem?.previewFor?.path || matchedItem?.path || document.path;
          const realName = matchedItem?.previewFor ? matchedItem.previewFor.name : (document.sourceName || document.name);
          return (document.items || []).map((page) => ({
            ...page,
            name: `${realName} · стр. ${page.page}`,
            documentPath: document.path,
            sourcePath: realSourcePath,
            sourceName: realName,
            sourceType: document.sourceType || matchedItem?.extension || "",
            dpi: payload.dpi,
            cacheHit: document.cacheHit,
            previewFor: matchedItem?.previewFor || (realSourcePath ? { path: realSourcePath, name: realName } : null),
            previewType: matchedItem?.previewType || document.sourceType || "",
            totalPages: document.pages || 1,
            rawDoc: document,
          }));
        });
        pageGroups[batchIndex] = batchPages;
        await flushReadyBatches();
        batchDone = true;
        payload.documents?.forEach((doc) => {
          if (doc.sourceType === "DWG" || (doc.items && doc.items.some((it) => it.url && it.url.includes("/dwg/")))) {
            const hasPending = (doc.cacheHitPages || 0) < (doc.pages || 0);
            if (hasPending || !doc.isComplete) {
              startDwgStatusPolling(doc.path || doc.sourcePath, doc.pages, myEpoch);
            }
          }
        });
      } catch (error) {
        if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
        const isTimeout = error?.name === "AbortError";
        if (isTimeout && attempt < 2) continue;
        allErrors.push({
          document: itemsToFetch.map((f) => f.name).join(", "),
          error: isTimeout ? "timeout" : String(error?.message || error),
        });
        const errCards = itemsToFetch.map((item) => {
          const sz = item?.size ? ` (${formatBytes(item.size)})` : "";
          return {
            type: "missing-preview",
            name: item?.name || "Документ",
            documentPath: item?.path || "",
            sourcePath: item?.path || "",
            sourceType: item?.extension || "PDF",
            message: isTimeout
              ? `Файл${sz} не дождался ответа облачного диска Google Drive (включая повторную попытку). Нажмите «Открыть», чтобы запустить его напрямую.`
              : "Ошибка рендеринга. Откройте файл через кнопку «Открыть».",
          };
        });
        pageGroups[batchIndex] = errCards;
        await flushReadyBatches();
        batchDone = true;
      } finally {
        if (controller) {
          state.operationControllers = state.operationControllers.filter((item) => item !== controller);
          controller = null;
        }
      }
    }
    if (!state.progressCancelled && state.renderEpoch === myEpoch) {
      completedBatches += 1;
      completedFiles += batch.length;
      if ((batch[0]?.previewType) === "DWG_MODEL") completedDwgFiles += itemsToFetch.length;
      refreshRenderProgress();
    }
  }

  async function worker() {
    while (!state.progressCancelled && state.renderEpoch === myEpoch && nextBatchIndex < batches.length) {
      if (state.progressCancelled || state.renderEpoch !== myEpoch) break;
      const batchIndex = nextBatchIndex++;
      // Пачки DWG_MODEL — строго по одной через общий семафор (CAD-COM),
      // остальные типы разбираются параллельно как раньше.
      if ((batches[batchIndex][0]?.previewType) === "DWG_MODEL") {
        await acquireDwgSlot();
        try {
          await renderBatch(batchIndex);
        } finally {
          releaseDwgSlot();
        }
      } else {
        await renderBatch(batchIndex);
      }
    }
  }

  refreshRenderProgress();
  await flushReadyBatches();
  const workerCount = Math.min(PDF_RENDER_CONCURRENCY, Math.max(1, renderableBatchCount));
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  await flushReadyBatches();
  if (state.progressCancelled || state.renderEpoch !== myEpoch) return;

  refreshRenderProgress();
  updateRibbonLoadMore();

  // После завершения рендера делаем Окно 2 сразу активным для навигации
  if (state.renderedPages?.length) {
    state.activeNavZone = "thumbs";
    if (!state.activePageKey) {
      state.activePageKey = pageKey(state.renderedPages[0]);
    }
    updateActivePdfThumb();
    try {
      const firstThumb = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(state.activePageKey)}"]`);
      if (firstThumb) {
        firstThumb.focus();
      }
    } catch (_) {}
  }

  const errorCount = allErrors.length;
  const isSingleDwg = isSingle && itemsToRender[0]?.previewType === "DWG_MODEL";
  const detail = isSingle
    ? (errorCount
      ? (isSingleDwg && allErrors[0]?.error ? `Не удалось открыть документ: ${allErrors[0].error}` : "Не удалось открыть документ")
      : `Готово: ${totalPages} страниц`)
    : (errorCount
      ? `Показано: ${renderedPages} из ${totalPages} стр. · ошибок: ${errorCount}`
      : `Готово: ${state.totalPreviewCount || itemsToRender.length} файлов · стр. ${renderedPages} из ${totalPages}`);
  finishProgress(detail);
}

async function loadMorePdfFiles(itemsToRender) {
  startProgress("Подгрузка страниц", `${itemsToRender.length} файлов — подгружаем порциями`);
  const batches = chunkPreviewItems(itemsToRender);
  let nextBatchIndex = 0;
  let completedBatches = 0;
  let completedFiles = 0;
  // Те же DWG-счётчики, что в основном показе; плюс счётчик ошибок пачек
  // для честной строки финиша.
  const totalDwgFiles = itemsToRender.filter((item) => item?.previewType === "DWG_MODEL").length;
  let completedDwgFiles = 0;
  let loadErrors = 0;
  const loadStartTime = Date.now();
  // Продолжение текущего показа: фиксируем его эпоху, чтобы подгрузка
  // сама гасла, если пользователь тем временем начал новый показ.
  const myEpoch = state.renderEpoch || 0;

  function refreshRenderProgress() {
    if (state.progressCancelled) return;
    const percent = Math.min(99, Math.round((completedFiles / itemsToRender.length) * 100));
    state.progressShown = percent;
    const elapsed = Date.now() - loadStartTime;
    state.progressEase = {
      base: percent,
      spent0: Date.now(),
      estMs: estimateBatchRemainMs(elapsed, completedFiles, itemsToRender.length),
    };
    els.progressValue.textContent = `${percent}%`;
    els.progressFill.style.width = `${percent}%`;
    const eta = completedFiles > 0 ? formatEta((elapsed / completedFiles) * (itemsToRender.length - completedFiles)) : "";
    const remaining = state.remainingPreviewItems?.length || 0;
    const batchCount = Math.max(1, batches.length);
    const curBatch = batches[Math.min(completedBatches, batchCount - 1)] || [];
    const firstIdx = completedFiles + 1;
    const lastIdx = Math.min(itemsToRender.length, completedFiles + curBatch.length);
    const curName = (curBatch[0] && curBatch[0].name) || "";
    els.progressDetail.textContent =
      `Пачка ${Math.min(completedBatches + 1, batchCount)} из ${batchCount}`
      + ` · Файлы ${firstIdx}–${lastIdx} из ${itemsToRender.length} (в очереди ещё ${remaining})`
      + (curName ? ` · Сейчас: ${curName}` : "")
      + ` · Готово: ${completedFiles} файлов${eta ? ` · ${eta}` : ""}`;
  }

  async function renderBatch(batchIndex) {
    if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
    const batch = batches[batchIndex];
    const itemsToFetch = batch.filter((item) => item?.type !== "missing-preview" && item?.type !== "native-file" && item?.previewType !== "IMAGE" && item?.previewType !== "TXT");
    if (!itemsToFetch.length) {
      if (batch.length) await appendPagesToViewer(batch, null, myEpoch);
      completedBatches += 1;
      return;
    }
    if (state.renderEpoch !== myEpoch) {
      completedBatches += 1;
      return;
    }
    let controller = null;
    const isDwg = itemsToFetch[0]?.previewType === "DWG_MODEL";
    const isExcel = itemsToFetch[0]?.previewType === "EXCEL";
    // Тот же масштабируемый таймаут и один автоповтор, что в основном показе:
    // облачный диск отвечает медленно, сервер продолжает рендер и греет кэш.
    const batchTimeout = isDwg ? 600000 : isExcel ? 180000
      : Math.min(PDF_FETCH_TIMEOUT_MS, 30000 * Math.max(1, itemsToFetch.length));
    let attempt = 0;
    let batchDone = false;
    while (!batchDone && attempt < 2) {
      attempt += 1;
      if (attempt === 1 && isDwg && totalDwgFiles > 0 && !state.progressCancelled) {
        els.progressDetail.textContent = `Модель ${completedDwgFiles + 1} из ${totalDwgFiles}: ${itemsToFetch[0]?.name || "чертёж"} — рендерится…`;
      }
    try {
      controller = new AbortController();
      state.operationControllers.push(controller);
      const timeoutId = setTimeout(() => controller.abort(), batchTimeout);

      const endpoint = isDwg
        ? "/api/dwg/model-render"
        : "/api/pdf/render";

      const _batchT0 = performance.now();
      const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ files: itemsToFetch.map((file) => file.path), dpi: PDF_PREVIEW_DPI, firstPageOnly: false }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      if (state.progressCancelled) return;
      const payload = await response.json();
      const _hits = (payload.documents || []).filter((d) => d.cacheHit).length;
      beaconPerf("display-batch", performance.now() - _batchT0, `files=${itemsToFetch.length} hits=${_hits}/${itemsToFetch.length}`);
      if (response.ok) {
        const batchPages = payload.documents.flatMap((document) => {
          const matchedItem = itemsToFetch.find((f) => f.path === document.path) || itemsToFetch[0];
          return document.items.map((page) => ({
            ...page,
            name: `${matchedItem?.previewFor ? matchedItem.previewFor.name : document.name} · стр. ${page.page}`,
            documentPath: document.path,
            dpi: payload.dpi,
            cacheHit: document.cacheHit,
            previewFor: matchedItem?.previewFor || null,
            previewType: matchedItem?.previewType || "",
          }));
        });
        if (state.renderEpoch !== myEpoch) return;
        await appendPagesToViewer(batchPages, null, myEpoch);
        batchDone = true;
        payload.documents?.forEach((doc) => {
          if (doc.sourceType === "DWG" || (doc.items && doc.items.some((it) => it.url && it.url.includes("/dwg/")))) {
            const hasPending = (doc.cacheHitPages || 0) < (doc.pages || 0);
            if (hasPending || !doc.isComplete) {
              startDwgStatusPolling(doc.path || doc.sourcePath, doc.pages, myEpoch);
            }
          }
        });
      } else {
        const errCards = itemsToFetch.map((item) => ({
          type: "missing-preview",
          name: item?.name || "Документ",
          documentPath: item?.path || "",
          sourcePath: item?.path || "",
          sourceType: item?.extension || "PDF",
          message: payload.error || "Ошибка превью. Откройте файл через кнопку «Открыть».",
        }));
      if (state.renderEpoch === myEpoch) await appendPagesToViewer(errCards, null, myEpoch);
      loadErrors += itemsToFetch.length;
      batchDone = true;
      }
    } catch (err) {
      if (state.progressCancelled || state.renderEpoch !== myEpoch) return;
      const isTimeout = err?.name === "AbortError";
      if (isTimeout && attempt < 2) continue;
      const errCards = itemsToFetch.map((item) => ({
        type: "missing-preview",
        name: item?.name || "Документ",
        documentPath: item?.path || "",
        sourcePath: item?.path || "",
        sourceType: item?.extension || "PDF",
          message: isTimeout
            ? "Файл не дождался ответа облачного диска Google Drive (включая повторную попытку). Нажмите «Открыть» для прямого запуска."
            : "Ошибка рендеринга. Откройте файл через кнопку «Открыть».",
        }));
        if (state.renderEpoch === myEpoch) await appendPagesToViewer(errCards, null, myEpoch);
        loadErrors += itemsToFetch.length;
        batchDone = true;
      } finally {
      if (controller) {
        state.operationControllers = state.operationControllers.filter((item) => item !== controller);
        controller = null;
      }
    }
  }
  if (!state.progressCancelled && state.renderEpoch === myEpoch) {
    completedBatches += 1;
    completedFiles += batch.length;
    if ((batch[0]?.previewType) === "DWG_MODEL") completedDwgFiles += itemsToFetch.length;
    refreshRenderProgress();
  }
}

  async function worker() {
    while (!state.progressCancelled && state.renderEpoch === myEpoch && nextBatchIndex < batches.length) {
      if (state.progressCancelled || state.renderEpoch !== myEpoch) break;
      const batchIndex = nextBatchIndex++;
      // Пачки DWG_MODEL — строго по одной через общий семафор (CAD-COM),
      // остальные типы разбираются параллельно как раньше.
      if ((batches[batchIndex][0]?.previewType) === "DWG_MODEL") {
        await acquireDwgSlot();
        try {
          await renderBatch(batchIndex);
        } finally {
          releaseDwgSlot();
        }
      } else {
        await renderBatch(batchIndex);
      }
    }
  }

  const workerCount = Math.min(PDF_RENDER_CONCURRENCY, Math.max(1, batches.length));
  await Promise.all(Array.from({ length: workerCount }, () => worker()));
  if (state.progressCancelled) return;

  updateRibbonLoadMore();
  finishProgress(loadErrors > 0 ? `Дополнительные превью загружены · ошибок: ${loadErrors}` : "Дополнительные превью загружены");
}


els.load.addEventListener("click", () => importObject(false).catch(showOperationError));
if (document.getElementById("reloadPage")) {
  document.getElementById("reloadPage").addEventListener("click", () => window.location.reload());
}
els.refresh.addEventListener("click", () => {
  if (inTreeMode()) refreshObjectInPlace().catch(showOperationError);
  else importObject(true).catch(showOperationError);
});
els.display.addEventListener("click", () => {
  if (inTreeMode()) renderSelectedFiles().catch(showOperationError);
  else openSelectedObject().catch(showOperationError);
});
els.exclude.addEventListener("click", () => {
  stopDiffPolling();
  excludeSelectedObject().catch(showOperationError);
});
els.cancel.addEventListener("click", () => stopProgress(true));
els.backToObjects.addEventListener("click", () => {
  stopDiffPolling();
  setViewerMode("standard");
  setStageActive(false);
  setMode("objects");
  loadObjectSummaries().catch(() => {});
});
els.backToTree.addEventListener("click", () => {
  if (inWindow3()) {
    exitWindow3();
    return;
  }
  setViewerMode("standard");
  setTreeBrowseMode(true);
  renderTree();
});
els.treeSearch.addEventListener("input", () => {
  renderTree();
});
els.pdfPageImage.addEventListener("load", () => {
  applyPageView();
  const currPage = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey) || state.renderedPages?.[0];
  if (currPage) updatePagePosition(currPage);
});
els.excelSheetFrame.addEventListener("load", () => {
  forwardExcelSheetContextMenu();
  if (!state.excelWorkbook) return;
  els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-zoom", value: state.excelScale }, "*");
});
if (els.wordDocFrame) {
  els.wordDocFrame.addEventListener("load", () => {
    forwardWordDocContextMenu();
    if (!state.wordDoc) return;
    els.wordDocFrame.contentWindow?.postMessage({ type: "launcher-sheet-zoom", value: state.wordScale }, "*");
  });
}
els.excelTabsLeft.addEventListener("click", () => {
  els.excelTabs.scrollBy({ left: -Math.max(180, els.excelTabs.clientWidth * .72), behavior: "smooth" });
});
els.excelTabsRight.addEventListener("click", () => {
  els.excelTabs.scrollBy({ left: Math.max(180, els.excelTabs.clientWidth * .72), behavior: "smooth" });
});
els.excelTabs.addEventListener("wheel", (event) => {
  if (!event.shiftKey || !event.deltaY) return;
  event.preventDefault();
  els.excelTabs.scrollLeft += event.deltaY;
}, { passive: false });
els.viewZoomOut.addEventListener("click", () => zoomPdf(0.82));
els.viewZoomIn.addEventListener("click", () => zoomPdf(1.22));

if (els.viewToggleDpi) {
  els.viewToggleDpi.addEventListener("click", (e) => {
    e.stopPropagation();
    const cur = state.viewerDpi || 150;
    state.viewerDpi = cur === 72 ? 150 : (cur === 150 ? 300 : 72);
    try {
      localStorage.setItem("launcher_viewer_dpi", String(state.viewerDpi));
    } catch (_) {}
    updateViewerDpiButton();
    const currPage = state.renderedPages?.find((p) => pageKey(p) === state.activePageKey) || state.renderedPages?.[0];
    if (currPage) {
      requestHighQualityPage(currPage, state.viewerDpi);
    }
  });
}

if (els.viewPrevPage) {
  els.viewPrevPage.addEventListener("click", (e) => {
    e.stopPropagation();
    if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
      const win = els.pdfDocFrame?.contentWindow;
      if (win && win.PDFViewerApplication && win.PDFViewerApplication.pdfViewer) {
        win.PDFViewerApplication.pdfViewer.previousPage();
        return;
      }
    }
    stepThumbnails(-1);
  });
}
if (els.viewNextPage) {
  els.viewNextPage.addEventListener("click", (e) => {
    e.stopPropagation();
    if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
      const win = els.pdfDocFrame?.contentWindow;
      if (win && win.PDFViewerApplication && win.PDFViewerApplication.pdfViewer) {
        win.PDFViewerApplication.pdfViewer.nextPage();
        return;
      }
    }
    stepThumbnails(1);
  });
}

// «Вписать» возвращает всё в нормальное состояние: масштаб картинки,
// сдвиг и поворот. Панель при этом никуда не уезжает.
els.viewFit.addEventListener("click", () => {
  if (state.excelWorkbook) {
    state.view.rotation = 0;
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-rotate", value: 0 }, "*");
    els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-fit" }, "*");
    return;
  }
  if (state.wordDoc) {
    state.wordScale = 1;
    els.wordDocFrame.contentWindow?.postMessage({ type: "launcher-sheet-zoom", value: 1 }, "*");
    els.wordDocFrame.contentWindow?.postMessage({ type: "launcher-sheet-fit" }, "*");
    return;
  }
  if (state.viewMode === "medium") {
    state.thumbScale = 1;
    els.pdfThumbs.style.setProperty("--thumb-scale", "1");
    return;
  }
  state.view.rotation = 0;
  state.view.userZoomed = false;
  fitPdfPage();
});

if (els.viewRotate) {
  els.viewRotate.addEventListener("click", () => {
    if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
      const win = els.pdfDocFrame?.contentWindow;
      if (win && win.PDFViewerApplication) {
        win.PDFViewerApplication.rotatePages(90);
      }
      return;
    }
    if (state.excelWorkbook) {
      state.view.rotation = (state.view.rotation + 90) % 360;
      els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-rotate", value: state.view.rotation }, "*");
      els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-fit" }, "*");
      return;
    }
    state.view.rotation = (state.view.rotation + 90) % 360;
    fitPdfPage();
  });
}

// =========================================================================
// Навигация по оглавлению (TOC) и Deep Linking для больших каталогов и PDF
// =========================================================================

const _tocCache = new Map();

async function checkAndShowPdfToc(docPath, currentPageNum) {
  if (!els.viewToggleToc || !docPath || !docPath.toLowerCase().endsWith(".pdf")) {
    if (els.viewToggleToc) els.viewToggleToc.hidden = true;
    if (els.pdfTocDrawer) els.pdfTocDrawer.hidden = true;
    state.currentToc = null;
    state.activeTocPath = "";
    return;
  }

  // Если уже загружено оглавление для текущего файла
  const normActive = (state.activeTocPath || "").replace(/\//g, "\\").toLowerCase();
  const normDoc = (docPath || "").replace(/\//g, "\\").toLowerCase();
  if (normActive && normActive === normDoc && state.currentToc) {
    els.viewToggleToc.hidden = false;
    highlightActiveTocItem(currentPageNum);
    return;
  }

  let data = _tocCache.get(docPath);
  if (!data) {
    try {
      const resp = await fetch("/api/pdf/toc", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: docPath })
      });
      if (resp.ok) {
        data = await resp.json();
        _tocCache.set(docPath, data);
      }
    } catch (_) {}
  }

  if (data && data.count > 0) {
    state.currentToc = data.toc;
    state.activeTocPath = docPath;
    els.viewToggleToc.hidden = false;
    renderPdfTocList(data.toc);
    highlightActiveTocItem(currentPageNum);
  } else {
    state.currentToc = null;
    state.activeTocPath = "";
    els.viewToggleToc.hidden = true;
    if (els.pdfTocDrawer) els.pdfTocDrawer.hidden = true;
  }
}

function renderPdfTocList(items, filterQuery = "") {
  if (!els.pdfTocList) return;
  els.pdfTocList.replaceChildren();
  const query = filterQuery.trim().toLowerCase();

  const filtered = query
    ? items.filter((it) => it.title.toLowerCase().includes(query) || String(it.page).includes(query))
    : items;

  if (!filtered.length) {
    const empty = document.createElement("div");
    empty.style.padding = "10px";
    empty.style.color = "#94a3b8";
    empty.style.fontSize = "11px";
    empty.textContent = "Разделы не найдены";
    els.pdfTocList.append(empty);
    return;
  }

  const fragment = document.createDocumentFragment();
  // Показываем первые 800 элементов для плавности рендеринга DOM
  const slice = filtered.slice(0, 800);

  slice.forEach((item) => {
    const row = document.createElement("div");
    row.className = "pdf-toc-item";
    row.dataset.page = item.page;
    row.style.paddingLeft = `${Math.max(8, (item.level || 1) * 12)}px`;

    const titleEl = document.createElement("span");
    titleEl.className = "pdf-toc-item-title";
    titleEl.textContent = item.title;
    titleEl.title = `${item.title} (стр. ${item.page})`;

    const pageEl = document.createElement("span");
    pageEl.className = "pdf-toc-item-page";
    pageEl.textContent = `стр. ${item.page}`;

    row.append(titleEl, pageEl);

    row.addEventListener("click", (e) => {
      e.stopPropagation();
      jumpToPdfPage(item.page, item.title);
    });
    row.addEventListener("dblclick", (e) => {
      e.stopPropagation();
      jumpToPdfPage(item.page, item.title);
    });

    fragment.append(row);
  });

  els.pdfTocList.append(fragment);
}

function highlightActiveTocItem(pageNum) {
  if (!els.pdfTocList || !pageNum) return;
  const num = Number(pageNum);
  const items = [...els.pdfTocList.querySelectorAll(".pdf-toc-item")];
  if (!items.length) return;

  // Ищем раздел, в диапазон которого попадает страница (наибольший стартовый лист <= текущего листа)
  let bestItem = null;
  let bestPage = -1;
  for (const el of items) {
    const p = Number(el.dataset.page);
    if (p <= num && p >= bestPage) {
      bestPage = p;
      bestItem = el;
    }
  }

  // Если номер страницы меньше стартовой страницы первого раздела каталога (например, обложка/титул):
  if (!bestItem && items.length) {
    bestItem = items[0];
  }

  items.forEach((el) => {
    el.classList.toggle("active", el === bestItem);
  });
  if (bestItem) {
    bestItem.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }
}

async function jumpToPdfPage(targetPage, sectionTitle = "") {
  const num = Number(targetPage);
  if (!num || !state.activeTocPath) return;

  const normToc = (state.activeTocPath || "").replace(/\//g, "\\").toLowerCase();

  // Ищем страницу в уже загруженных
  const existing = state.renderedPages.find((p) => {
    const p1 = (p.documentPath || "").replace(/\//g, "\\").toLowerCase();
    const p2 = (p.sourcePath || "").replace(/\//g, "\\").toLowerCase();
    const p3 = (thumbPathForPage(p) || "").replace(/\//g, "\\").toLowerCase();
    const matchesDoc = p1 === normToc || p2 === normToc || p3 === normToc ||
      (normToc.length > 5 && (p1.endsWith(normToc) || normToc.endsWith(p1) || p2.endsWith(normToc) || normToc.endsWith(p2)));
    return matchesDoc && Number(p.page) === num;
  });

  if (existing) {
    state.view.userZoomed = false;
    showPdfPage(existing);
    highlightActiveTocItem(num);
    revealPathInTree(state.activeTocPath, { updateSelection: true, skipScroll: true });
    const thumb = els.pdfThumbs?.querySelector(`.pdf-thumb[data-page-key="${CSS.escape(pageKey(existing))}"]`);
    if (thumb) {
      thumb.scrollIntoView({ block: "center", behavior: "smooth" });
    }
    if (!existing.bytes) {
      fetch("/api/pdf/page", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file: state.activeTocPath, page: num, dpi: PDF_PREVIEW_DPI })
      }).then(r => r.json()).then(payload => {
        if (payload?.item?.url) {
          existing.url = payload.item.url;
          existing.bytes = payload.item.bytes;
          if (state.activePageKey === pageKey(existing)) {
            els.pdfPageImage.src = payload.item.url;
          }
        }
      }).catch(() => {});
    }
    return;
  }

  // Если страницы ещё нет в ленте — запрашиваем её на лету
  startProgress("Переход к разделу", `Страница ${num}: ${sectionTitle || ""}`);
  try {
    const resp = await fetch("/api/pdf/page", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ file: state.activeTocPath, page: num, dpi: PDF_PREVIEW_DPI })
    });
    const payload = await resp.json();
    if (!resp.ok) throw new Error(payload.error || "Не удалось загрузить страницу");

    const newPage = {
      ...payload.item,
      name: `${payload.name} · стр. ${num}`,
      documentPath: state.activeTocPath,
      sourcePath: state.activeTocPath,
      page: num,
      dpi: payload.dpi,
      cacheHit: payload.cacheHit,
      totalPages: payload.pages
    };

    await appendPagesToViewer([newPage], null, state.renderEpoch);
    state.view.userZoomed = false;
    showPdfPage(newPage);
    highlightActiveTocItem(num);
    revealPathInTree(state.activeTocPath, { updateSelection: true, skipScroll: true });
    finishProgress();
  } catch (err) {
    showOperationError(err);
  }
}

if (els.viewToggleToc) {
  els.viewToggleToc.addEventListener("click", () => {
    if (!els.pdfTocDrawer) return;
    const isHidden = els.pdfTocDrawer.hidden;
    els.pdfTocDrawer.hidden = !isHidden;
    if (isHidden && els.pdfTocSearch) {
      els.pdfTocSearch.focus();
    }
  });
}

if (els.pdfTocClose) {
  els.pdfTocClose.addEventListener("click", () => {
    if (els.pdfTocDrawer) els.pdfTocDrawer.hidden = true;
  });
}

if (els.pdfTocSearch) {
  els.pdfTocSearch.addEventListener("input", (e) => {
    if (state.currentToc) {
      renderPdfTocList(state.currentToc, e.target.value);
    }
  });
}

// Кнопка «Копировать ссылку на страницу и узел» (Deep Link для тендерных ведомостей)
if (els.viewCopyLink) { els.viewCopyLink.style.display = "none";
  els.viewCopyLink.addEventListener("click", () => {
    const page = (state.renderedPages || []).find((p) => {
      try { return pageKey(p) === state.activePageKey; } catch (_) { return false; }
    });
    const filePath = thumbPathForPage(page) || state.activeNativePath;
    const pageNum = page?.page || 1;
    const fileName = filePath ? filePath.split(/[\/\\]/).pop() : "document.pdf";

    // Поиск ближайшего раздела из TOC
    let sectionName = "";
    if (state.currentToc && state.currentToc.length) {
      const match = state.currentToc
        .filter((item) => item.page <= pageNum)
        .sort((a, b) => b.page - a.page)[0];
      if (match) sectionName = match.title;
    }

    // Формат ссылки для вставки в Excel / Word / чат
    const sectionPart = sectionName ? ` · Раздел: «${sectionName}»` : "";
    const linkText = `${fileName}#стр.${pageNum}${sectionPart} [${filePath}]`;

    navigator.clipboard?.writeText(linkText).then(() => {
      showToast(`Ссылка скопирована: Стр. ${pageNum}${sectionPart}`);
    }).catch(() => {
      prompt("Скопируйте ссылку:", linkText);
    });
  });
}

// Блокируем масштабирование всего окна браузера (Ctrl + / Ctrl - / Ctrl + wheel в пустых местах),
// чтобы каркас окон, рамки и разметка никогда не «плыли»
window.addEventListener("wheel", (event) => {
  if (event.ctrlKey) {
    event.preventDefault();
  }
}, { passive: false });

window.addEventListener("keydown", (event) => {
  if (event.ctrlKey && (event.key === "+" || event.key === "=" || event.key === "-" || event.key === "_" || event.key === "0")) {
    event.preventDefault();
  }
});

els.pdfPageImage.addEventListener("dblclick", (e) => {
  e.stopPropagation();
  if (pdfDragMoved) return;
  setViewerMode(state.viewMode === "full" ? "standard" : "full");
});

const pdfCanvas = document.getElementById("pdfPageCanvas");
if (pdfCanvas) {
  pdfCanvas.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    if (pdfDragMoved) return;
    setViewerMode(state.viewMode === "full" ? "standard" : "full");
  });
}

if (els.pdfTocDrawer) {
  els.pdfTocDrawer.addEventListener("dblclick", (e) => e.stopPropagation());
  els.pdfTocDrawer.addEventListener("click", (e) => e.stopPropagation());
  els.pdfTocDrawer.addEventListener("pointerdown", (e) => e.stopPropagation());
  els.pdfTocDrawer.addEventListener("mousedown", (e) => e.stopPropagation());
  els.pdfTocDrawer.addEventListener("pointerup", (e) => e.stopPropagation());
  els.pdfTocDrawer.addEventListener("wheel", (e) => e.stopPropagation(), { passive: true });
}

if (els.pdfStage) {
  els.pdfStage.addEventListener("dblclick", (e) => {
    if (e.target.closest(".viewer-controls, .excel-tabs-bar, .pdf-toc-drawer, button, a, input")) return;
    if (pdfDragMoved) return;
    setViewerMode(state.viewMode === "full" ? "standard" : "full");
  });
}

if (els.excelBookTitle) {
  els.excelBookTitle.addEventListener("dblclick", (e) => {
    e.stopPropagation();
    setViewerMode(state.viewMode === "full" ? "standard" : "full");
  });
}

// Единый канонический обработчик ПКМ в окне №3 (просмотрщик)
if (els.pdfViewer) {
  els.pdfViewer.addEventListener("contextmenu", (event) => {
    // Если есть выделенный текст, разрешаем стандартное меню Windows (включая копирование)
    const sel = window.getSelection();
    const selectedText = (sel && sel.toString().trim()) || "";
    if (false) {
      return;
    }
    if (event.target.closest("button, input, a, .excel-tabs, .excel-tabs-bar, .viewer-controls")) return;
    event.preventDefault();
    event.stopPropagation();
    hideFileContextMenu();
    const info = getActiveSourceInfo();
    const targetPath = (info && info.path) || state.activeNativePath || state.revealedPath || "";
    if (!targetPath) return;
    showFileContextMenu(event.clientX, event.clientY, {
      selectedText,
      path: targetPath,
      isDir: false,
      ext: extOfPath(targetPath),
    });
  });
}

function showPdfViewerContextMenu(clientX, clientY, extra = {}) {
  hideFileContextMenu();
  const info = getActiveSourceInfo();
  const targetPath = (info && info.path) || state.activeNativePath || state.revealedPath || "";
  showFileContextMenu(clientX, clientY, {
    isPdf: true,
    selectedText: (extra && extra.selectedText) || "",
    hasZone: Boolean(extra && extra.hasZone),
    canCadExport: Boolean(extra && extra.canCadExport),
    path: targetPath,
    isDir: false,
    ext: extOfPath(targetPath),
  });
}
window.showPdfViewerContextMenu = showPdfViewerContextMenu;

if (els.excelViewer) {
  els.excelViewer.addEventListener("contextmenu", (event) => {
    const wbPath = state.excelWorkbook?.path || "";
    if (!wbPath) return;
    event.preventDefault();
    event.stopPropagation();
    showFileContextMenu(event.clientX, event.clientY, {
      path: wbPath,
      isDir: false,
      ext: state.excelWorkbook?.extension || extOfPath(wbPath),
    });
  });
}

if (els.wordViewer) {
  els.wordViewer.addEventListener("contextmenu", (event) => {
    if (event.target.closest("button, input, a, .excel-tabs, .excel-tabs-bar, .viewer-controls")) return;
    const docPath = state.wordDoc?.path || state.activeNativePath || "";
    if (!docPath) return;
    event.preventDefault();
    event.stopPropagation();
    showFileContextMenu(event.clientX, event.clientY, {
      path: docPath,
      isDir: false,
      ext: extOfPath(docPath),
    });
  });
}

window.addEventListener("message", (event) => {
  if (event.data?.type === "launcher-toggle-full-view") {
    setViewerMode(state.viewMode === "full" ? "standard" : "full");
  } else if (event.data?.type === "launcher-escape") {
    handleGlobalEscape();
  } else if (event.data?.type === "launcher-contextmenu") {
    const rect = els.wordDocFrame ? els.wordDocFrame.getBoundingClientRect() : { left: 0, top: 0 };
    const x = rect.left + (event.data.clientX || 0);
    const y = rect.top + (event.data.clientY || 0);
    const info = getActiveSourceInfo();
    const currentDoc = state.wordDoc;
    const path = (info && info.path) || (currentDoc && currentDoc.path) || state.activeNativePath || "";
    if (path) {
      showFileContextMenu(x, y, { path, isDir: false, ext: extOfPath(path) });
    }
  }
});

window.addEventListener("resize", () => {
  if (state.viewMode === "full" || els.pdfViewer?.classList.contains("stage-active")) {
    fitPdfPage();
  }
});

// Масштабирование только содержимого дерева (колёсико над левой частью)
if (els.sidebar) {
  els.sidebar.addEventListener("wheel", (event) => {
    if (!event.ctrlKey || !event.deltaY) return;
    event.preventDefault();
    event.stopPropagation();
    zoomTree(event.deltaY < 0 ? 1.08 : 0.92);
  }, { passive: false });
}
if (els.scaleWidget) {
  els.scaleWidget.addEventListener("wheel", (event) => {
    if (!event.deltaY) return;
    event.preventDefault();
    event.stopPropagation();
    const factor = event.deltaY < 0 ? 1.08 : 0.92;
    zoomTree(factor);
    zoomThumbs(factor);
  }, { passive: false });
}

// Масштабирование только картинки на сцене (в полноэкранном 3-м режиме)
els.pdfStage.addEventListener("wheel", (event) => {
  if (event.target.closest(".viewer-controls, .pdf-toc-drawer, .excel-tabs-bar")) return;
  const canvas = document.getElementById("pdfPageCanvas");
  const isCanvasActive = canvas && !canvas.hidden;
  if (!event.ctrlKey || (els.pdfPageImage.hidden && !isCanvasActive && !state.excelWorkbook)) return;
  event.preventDefault();
  event.stopPropagation();
  zoomPdf(event.deltaY < 0 ? 1.12 : 0.89, event.clientX, event.clientY);
}, { passive: false });

// Масштабирование только миниатюр (Ctrl + колёсико над правой лентой)
els.pdfThumbs.addEventListener("wheel", (event) => {
  if (!event.ctrlKey || !event.deltaY) return;
  event.preventDefault();
  event.stopPropagation();
  zoomThumbs(event.deltaY < 0 ? 1.15 : 0.87);
}, { passive: false });

// Панель управления масштабом (кнопки −, 100%, + в верхней панели)
// 100% работает везде во всех окнах: в левом поле, во втором поле, а при просмотре чертежа дублирует «Вписать»
if (els.scaleResetBtn) {
  els.scaleResetBtn.addEventListener("click", () => {
    // 1. Сброс масштаба левого поля (дерево и список объектов)
    state.treeScale = 1;
    document.documentElement.style.setProperty("--tree-scale", "1");

    // 2. Сброс масштаба второго поля (лента миниатюр)
    state.thumbScale = 1;
    els.pdfThumbs.style.setProperty("--thumb-scale", "1");

    try {
      localStorage.setItem("launcher_tree_scale", "1");
      localStorage.setItem("launcher_thumb_scale", "1");
    } catch {}

    // 3. Единый чертёж / документ (дублирует действие «Вписать» / сброс)
    if (state.excelWorkbook) {
      state.view.rotation = 0;
      els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-rotate", value: 0 }, "*");
      els.excelSheetFrame.contentWindow?.postMessage({ type: "launcher-sheet-fit" }, "*");
    } else if (!els.pdfPageImage.hidden || (document.getElementById("pdfPageCanvas") && !document.getElementById("pdfPageCanvas").hidden)) {
      state.view.rotation = 0;
      state.view.userZoomed = false;
      fitPdfPage();
    }

    updateScaleIndicator();
    showToast("Масштаб: 100% (исходный)");
  });
}

if (els.scaleMinusBtn) {
  els.scaleMinusBtn.addEventListener("click", () => {
    const isStageViewing = state.viewMode === "full" || els.pdfViewer?.classList.contains("stage-active");
    const canvas = document.getElementById("pdfPageCanvas");
    const isCanvasActive = canvas && !canvas.hidden;
    if (isStageViewing && (!els.pdfPageImage.hidden || isCanvasActive || state.excelWorkbook)) {
      zoomPdf(0.89);
    } else {
      zoomTree(0.9);
      zoomThumbs(0.9);
    }
  });
}

if (els.scalePlusBtn) {
  els.scalePlusBtn.addEventListener("click", () => {
    const isStageViewing = state.viewMode === "full" || els.pdfViewer?.classList.contains("stage-active");
    const canvas = document.getElementById("pdfPageCanvas");
    const isCanvasActive = canvas && !canvas.hidden;
    if (isStageViewing && (!els.pdfPageImage.hidden || isCanvasActive || state.excelWorkbook)) {
      zoomPdf(1.12);
    } else {
      zoomTree(1.1);
      zoomThumbs(1.1);
    }
  });
}

// Восстановление сохранённых масштабов при старте
try {
  const savedTreeScale = parseFloat(localStorage.getItem("launcher_tree_scale") || "1");
  if (savedTreeScale && savedTreeScale >= 0.75 && savedTreeScale <= 2.5) {
    state.treeScale = savedTreeScale;
    document.documentElement.style.setProperty("--tree-scale", String(state.treeScale));
  }
  const savedThumbScale = parseFloat(localStorage.getItem("launcher_thumb_scale") || "1");
  if (savedThumbScale && savedThumbScale >= 0.4 && savedThumbScale <= 5) {
    state.thumbScale = savedThumbScale;
    els.pdfThumbs.style.setProperty("--thumb-scale", String(state.thumbScale));
  }
  updateScaleIndicator();
} catch {}

let pdfDragMoved = false;

els.pdfStage.addEventListener("pointerdown", (event) => {
  if (event.target.closest(".viewer-controls, .pdf-toc-drawer, .excel-tabs-bar, input, button")) return;
  const canvas = document.getElementById("pdfPageCanvas");
  const isCanvasActive = canvas && !canvas.hidden;
  if ((els.pdfPageImage.hidden && !isCanvasActive) || event.button !== 0) return;
  event.preventDefault();
  state.view.dragging = true;
  pdfDragMoved = false;
  state.view.dragStartX = event.clientX;
  state.view.dragStartY = event.clientY;
  state.view.dragPanX = state.view.panX;
  state.view.dragPanY = state.view.panY;
  els.pdfStage.setPointerCapture(event.pointerId);
  updateViewTransform();
});

els.pdfStage.addEventListener("pointermove", (event) => {
  if (!state.view.dragging) return;
  const dx = event.clientX - state.view.dragStartX;
  const dy = event.clientY - state.view.dragStartY;
  if (!pdfDragMoved && (Math.abs(dx) > 3 || Math.abs(dy) > 3)) {
    pdfDragMoved = true;
  }
  state.view.panX = state.view.dragPanX + dx;
  state.view.panY = state.view.dragPanY + dy;
  updateViewTransform();
});

function endPdfDrag(event) {
  if (!state.view.dragging) return;
  state.view.dragging = false;
  try {
    els.pdfStage.releasePointerCapture(event.pointerId);
  } catch {
    // Pointer capture may already be released by the browser.
  }
  updateViewTransform();
}

els.pdfStage.addEventListener("pointerup", endPdfDrag);
els.pdfStage.addEventListener("pointercancel", endPdfDrag);

function handleGlobalEscape() {
  if (hideFileContextMenu()) {
    return;
  }
  if (els.settingsModal && !els.settingsModal.hidden) {
    closeSettingsModal();
    return;
  }
  if (!els.pdfPageImage.hidden && state.view.dragging) {
    state.view.dragging = false;
    updateViewTransform();
    return;
  }
  if (els.pdfTocDrawer && !els.pdfTocDrawer.hidden) {
    els.pdfTocDrawer.hidden = true;
    return;
  }
  // 1. В Окне 3: Escape сбрасывает телодвижения (контекстное меню -> перевод -> выделение -> поиск)
  if (inWindow3()) {
    if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
      const win = els.pdfDocFrame?.contentWindow;
      if (win && typeof win.handlePdfJsEscape === "function") {
        if (win.handlePdfJsEscape()) {
          return true;
        }
      }
    }
    const sel = window.getSelection();
    if (sel && !sel.isCollapsed && sel.toString().trim()) {
      sel.removeAllRanges();
      return true;
    }
    // Если локальных модальных состояний и выделений нет — возвращаемся из Окна 3 к Окну 1 + 2
    exitWindow3();
    return true;
  }
  // 2. В режиме дерева:
  if (inTreeMode()) {
    // 2.1. Если введён поисковый запрос — сбрасываем поиск
    if (els.treeSearch && els.treeSearch.value.trim()) {
      els.treeSearch.value = "";
      renderTree();
      return;
    }
    // 2.2. Если включён фильтр форматов или изменений — сбрасываем фильтры
    if (state.activeFilters.size > 0 || state.diffFilter) {
      state.activeFilters.clear();
      state.diffFilter = false;
      renderFormats();
      renderTree();
      return;
    }
    // 2.3. Если выделены узлы или строка в дереве — снимаем выделение
    if (state.selectedPaths.size > 0 || state.revealedPath) {
      state.selectedPaths.clear();
      state.revealedPath = "";
      renderTree();
      return;
    }
    // 2.4. Если в дереве ничего не выбрано — выходим назад к списку объектов!
    stopDiffPolling();
    setViewerMode("standard");
    setMode("objects");
    return;
  }
  // 3. В режиме списка объектов: если выбран объект, снимаем выбор и возвращаемся к исходному виду
  if (state.selectedObjectId !== null) {
    state.selectedObjectId = null;
    updateObjectListSelection();
    updateObjectButtons();
    updateObjectStats();
    updateViewerBanner('Политика "Локальный компьютер"');
    return;
  }
}

function stepThumbnails(delta) {
  const pages = state.renderedPages;
  if (!pages?.length) return;
  let currentIdx = pages.findIndex((p) => pageKey(p) === state.activePageKey);
  if (currentIdx < 0) currentIdx = 0;
  let nextIdx = currentIdx + delta;
  if (nextIdx < 0) nextIdx = pages.length - 1;
  else if (nextIdx >= pages.length) nextIdx = 0;

  const nextPage = pages[nextIdx];
  if (nextPage) {
    showPdfPage(nextPage);
    const targetDocPath = thumbPathForPage(nextPage);
    if (targetDocPath) {
      revealPathInTree(targetDocPath, { updateSelection: true, skipScroll: false });
    }
    const key = pageKey(nextPage);
    const thumbEl = Array.from(els.pdfThumbs?.querySelectorAll(".pdf-thumb") || []).find(
      (el) => el.dataset.pageKey === key
    );
    if (thumbEl) {
      thumbEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
    }
  }
}

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && (event.key === "f" || event.key === "F" || event.key === "а" || event.key === "А")) {
    if (els.pdfDocViewer && !els.pdfDocViewer.hidden) {
      event.preventDefault();
      openPdfJsSearch();
      return;
    }
    if (els.treeSearch) {
      event.preventDefault();
      els.treeSearch.focus();
      els.treeSearch.select();
      return;
    }
  }
  const activeTag = document.activeElement?.tagName;
  const isInput = activeTag === "INPUT" || activeTag === "TEXTAREA";

  if (event.key === "Escape") {
    event.preventDefault();
    handleGlobalEscape();
    return;
  }

  if (isInput) return;

  // Навигация клавишами Вверх / Вниз:
  if (event.key === "ArrowUp" || event.key === "ArrowDown") {
    const isThumbsActive = state.viewMode === "full" || state.activeNavZone === "thumbs" || els.pdfViewer?.contains(document.activeElement);
    const thumbEls = Array.from(els.pdfThumbs?.querySelectorAll(".pdf-thumb") || []);

    if (thumbEls.length > 0 && isThumbsActive) {
      event.preventDefault();
      if (state.renderedPages?.length) {
        stepThumbnails(event.key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (state.excelWorkbooks?.length) {
        const books = state.excelWorkbooks;
        let currentIdx = state.excelWorkbookIndex;
        if (event.key === "ArrowDown") {
          currentIdx = currentIdx >= 0 && currentIdx < books.length - 1 ? currentIdx + 1 : 0;
        } else {
          currentIdx = currentIdx > 0 ? currentIdx - 1 : books.length - 1;
        }
        const isStage = Boolean(els.pdfViewer?.classList.contains("stage-active"));
        if (isStage) {
          activateExcelWorkbook(currentIdx).catch(showOperationError);
        } else {
          state.excelWorkbookIndex = currentIdx;
          renderExcelWorkbookRail();
        }
        const nextBook = books[currentIdx];
        if (nextBook?.path) {
          revealPathInTree(nextBook.path, { updateSelection: true, skipScroll: false });
        }
        return;
      }
      if (state.wordDocs?.length) {
        const docs = state.wordDocs;
        let currentIdx = state.wordDocIndex;
        if (event.key === "ArrowDown") {
          currentIdx = currentIdx >= 0 && currentIdx < docs.length - 1 ? currentIdx + 1 : 0;
        } else {
          currentIdx = currentIdx > 0 ? currentIdx - 1 : docs.length - 1;
        }
        const isStage = Boolean(els.pdfViewer?.classList.contains("stage-active"));
        if (isStage) {
          activateWordDocument(currentIdx).catch(showOperationError);
        } else {
          state.wordDocIndex = currentIdx;
          renderWordDocumentRail();
        }
        const nextDoc = docs[currentIdx];
        if (nextDoc?.path) {
          revealPathInTree(nextDoc.path, { updateSelection: true, skipScroll: false });
        }
        return;
      }
      return;
    }

    // Иначе (Зона 1 — дерево слева): навигация по списку файлов БЕЗ авторендеринга
    if (inTreeMode()) {
      const files = state.visibleRows.filter((r) => r.type === "file");
      if (!files.length) return;
      event.preventDefault();
      const currentPath = Array.from(state.selectedPaths)[0] || state.revealedPath;
      let idx = files.findIndex((f) => f.path === currentPath);
      if (event.key === "ArrowDown") {
        idx = idx >= 0 && idx < files.length - 1 ? idx + 1 : 0;
      } else {
        idx = idx > 0 ? idx - 1 : files.length - 1;
      }
      const nextFile = files[idx];
      if (nextFile) {
        selectNode(nextFile);
        const row = els.objectTree?.querySelector(`.tree-row[data-path="${CSS.escape(nextFile.path)}"]`);
        if (row) row.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
      return;
    }
  }

  // Клавиша Enter в дереве: явный запуск рендера для выбранного файла
  if (event.key === "Enter" && inTreeMode() && state.activeNavZone !== "thumbs") {
    const currentPath = Array.from(state.selectedPaths)[0] || state.revealedPath;
    if (currentPath) {
      const fileNode = state.visibleRows.find((r) => r.path === currentPath && r.type === "file");
      if (fileNode) {
        event.preventDefault();
        previewFileDirectly(fileNode, { fullView: false }).catch(showOperationError);
        return;
      }
    }
  }

  // Навигация клавишами Влево / Вправо по книгам Excel
  if (state.excelWorkbooks?.length > 1 && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
    event.preventDefault();
    const books = state.excelWorkbooks;
    let currentIdx = state.excelWorkbookIndex;
    if (event.key === "ArrowRight") {
      currentIdx = currentIdx >= 0 && currentIdx < books.length - 1 ? currentIdx + 1 : 0;
    } else {
      currentIdx = currentIdx > 0 ? currentIdx - 1 : books.length - 1;
    }
    const isStage = Boolean(els.pdfViewer?.classList.contains("stage-active"));
    if (isStage) {
      activateExcelWorkbook(currentIdx).catch(showOperationError);
    } else {
      state.excelWorkbookIndex = currentIdx;
      renderExcelWorkbookRail();
    }
    const nextBook = books[currentIdx];
    if (nextBook?.path) {
      revealPathInTree(nextBook.path, { updateSelection: true, skipScroll: false });
    }
    return;
  }

  // Навигация клавишами Влево / Вправо по страницам / миниатюрам
  if (state.renderedPages?.length && (event.key === "ArrowLeft" || event.key === "ArrowRight")) {
    event.preventDefault();
    stepThumbnails(event.key === "ArrowRight" ? 1 : -1);
    return;
  }
});

// Отслеживание двух активных зон навигации:
// Зона 1: Дерево слева (папки, подпапки, файлы)
// Зона 2: Лента миниатюр справа (вертикальная лента страниц)
if (els.pdfViewer) {
  els.pdfViewer.addEventListener("pointerdown", () => { state.activeNavZone = "thumbs"; });
  els.pdfViewer.addEventListener("mouseenter", () => { state.activeNavZone = "thumbs"; });
  els.pdfViewer.addEventListener("focusin", () => { state.activeNavZone = "thumbs"; });
}
if (els.pdfThumbs) {
  els.pdfThumbs.addEventListener("pointerdown", () => { state.activeNavZone = "thumbs"; });
  els.pdfThumbs.addEventListener("mouseenter", () => { state.activeNavZone = "thumbs"; });
  els.pdfThumbs.addEventListener("focusin", () => { state.activeNavZone = "thumbs"; });
  els.pdfThumbs.addEventListener("click", (event) => {
    // Клик по пустому месту ленты (мимо карточек): снять всё выделение.
    // Клики по карточкам сюда не доходят (stopPropagation в карточке).
    // Превью при этом не трогаем.
    if (event.target.closest(".pdf-thumb")) return;
    if (!state.selectedPaths.size && !state.revealedPath) return;
    state.activeNavZone = "thumbs";
    state.selectedPaths.clear();
    state.revealedPath = "";
    state.lastSelectedIndex = null;
    if (els.pdfViewer?.classList.contains("empty")) setActiveNativePath("");
    updateTreeSelectionHighlight();
  });
}
if (els.objectTree) {
  els.objectTree.addEventListener("pointerdown", () => { state.activeNavZone = "tree"; });
  els.objectTree.addEventListener("mouseenter", () => { state.activeNavZone = "tree"; });
  els.objectTree.addEventListener("focusin", () => { state.activeNavZone = "tree"; });
  els.objectTree.addEventListener("click", (event) => {
    // Клик по пустому месту дерева (мимо строк): снять всё выделение.
    // Клики по строкам сюда не доходят (stopPropagation в строке).
    if (event.target.closest(".tree-row")) return;
    if (!state.selectedPaths.size && !state.revealedPath) return;
    state.activeNavZone = "tree";
    state.selectedPaths.clear();
    state.revealedPath = "";
    state.lastSelectedIndex = null;
    if (els.pdfViewer?.classList.contains("empty")) setActiveNativePath("");
    updateTreeSelectionHighlight();
  });
}
const treeShellContainer = document.getElementById("treeShell") || document.querySelector(".tree-panel");
if (treeShellContainer) {
  treeShellContainer.addEventListener("pointerdown", () => { state.activeNavZone = "tree"; });
  treeShellContainer.addEventListener("mouseenter", () => { state.activeNavZone = "tree"; });
}

// Отслеживание позиции курсора мыши для точной привязки к листу под курсором при прокрутке колесом
window.addEventListener("mousemove", (e) => {
  state._lastMouseX = e.clientX;
  state._lastMouseY = e.clientY;
}, { passive: true });

let _ribbonSyncRaf = null;
function syncRibbonScrollToTree() {
  if (_ribbonSyncRaf) return;
  _ribbonSyncRaf = requestAnimationFrame(() => {
    _ribbonSyncRaf = null;
    if (state.viewMode === "full" || !els.pdfThumbs) return;
    if (!state.renderedPages?.length && !state.excelWorkbooks?.length && !state.wordDocs?.length) return;

    let targetThumb = null;
    // Если курсор находится над лентой миниатюр — берём миниатюру точно под курсором
    if (state._lastMouseX !== undefined && state._lastMouseY !== undefined) {
      const el = document.elementFromPoint(state._lastMouseX, state._lastMouseY);
      targetThumb = el?.closest(".pdf-thumb");
    }
    // Если курсор не над миниатюрой (или прокрутка колесом/скроллбаром вне неё) — берём миниатюру по центральной ватерлинии
    if (!targetThumb) {
      const rect = els.pdfThumbs.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const midY = rect.top + rect.height / 2;
        const midX = rect.left + rect.width / 2;
        const el = document.elementFromPoint(midX, midY);
        targetThumb = el?.closest(".pdf-thumb");
      }
    }
    if (!targetThumb) return;

    // 1. Для Excel-книг
    if (targetThumb.classList.contains("excel-book-thumb") && targetThumb.dataset.workbookIndex !== undefined) {
      const idx = Number(targetThumb.dataset.workbookIndex);
      const wb = state.excelWorkbooks?.[idx];
      if (wb?.path && state.revealedPath !== wb.path) {
        revealPathInTree(wb.path, { updateSelection: false, skipScroll: false });
      }
      return;
    }

    // 2. Для Word-документов
    if (targetThumb.classList.contains("word-doc-thumb") && targetThumb.dataset.docIndex !== undefined) {
      const idx = Number(targetThumb.dataset.docIndex);
      const doc = state.wordDocs?.[idx];
      if (doc?.path && state.revealedPath !== doc.path) {
        revealPathInTree(doc.path, { updateSelection: false, skipScroll: false });
      }
      return;
    }

    // 3. Для PDF-страниц
    if (!targetThumb.dataset?.pageKey) return;
    const key = targetThumb.dataset.pageKey;
    const page = state.renderedPages.find((p) => pageKey(p) === key);
    if (!page) return;
    const docPath = thumbPathForPage(page);
    if (docPath && state.revealedPath !== docPath) {
      revealPathInTree(docPath, { updateSelection: false, skipScroll: false });
    }
  });
}
if (els.pdfThumbs) {
  els.pdfThumbs.addEventListener("scroll", syncRibbonScrollToTree, { passive: true });
}

document.addEventListener("click", (event) => {
  if (els.objectListState.classList.contains("active") && !event.target.closest(".object-row, button, textarea")) {
    state.selectedObjectId = null;
    renderObjectList();
  }
  // В режиме дерева: сбрасываем выделение ТОЛЬКО если кликнули по пустому фону самого дерева
  // Клик в просмотрщик, ленту миниатюр, скроллбар или тулбар никогда не сбрасывает дерево!
  if (inTreeMode() && els.objectTree && els.objectTree === event.target) {
    state.selectedPaths.clear();
    state.revealedPath = "";
    updateTreeSelectionHighlight();
  }
});

setMode("objects");
setViewerMode("standard");

// Автообновление (Спринт 2): проверка через 3 секунды после загрузки.
function showUpdateBanner(data) {
  if (document.getElementById('update-pill')) return;
  const pill = document.createElement('button');
  pill.type = 'button';
  pill.id = 'update-pill';
  pill.title = data.changelog || 'Доступно обновление лаунчера';
  pill.textContent = 'Доступно обновление v' + data.latest_version + ' [Обновить]';
  pill.style.cssText = 'margin-left:8px;padding:2px 12px;border-radius:999px;border:1px solid #93c5fd;background:#dbeafe;color:#1d4ed8;font-size:12px;cursor:pointer;white-space:nowrap;';
  pill.addEventListener('click', () => {
    pill.disabled = true;
    pill.textContent = 'Загрузка обновления...';
    fetch('/api/updates/apply', { method: 'POST' })
      .then(r => r.json())
      .then(() => {
        showToast('Идет загрузка и установка обновления... Лаунчер перезапустится через несколько секунд.');
      })
      .catch(() => {
        showToast('Идет загрузка и установка обновления... Лаунчер перезапустится через несколько секунд.');
      });
  });
  if (els.scaleWidget) els.scaleWidget.after(pill);
}

function checkUpdates() {
  fetch('/api/updates/check')
    .then(r => r.json())
    .then(data => {
      if (data && data.has_update) {
        showUpdateBanner(data);
      }
    }).catch(() => {});
}
setTimeout(checkUpdates, 3000);
loadObjectSummaries().catch((error) => {
  els.objectList.innerHTML = `<div class="empty-note">Ошибка загрузки списка: ${error.message}</div>`;
});

// Меню действий в шапке
document.getElementById("menuFile")?.addEventListener("click", () => els.load.click());
document.getElementById("menuAction")?.addEventListener("click", () => {
  if (!els.display.disabled) els.display.click();
  else if (!els.refresh.disabled) els.refresh.click();
  else els.load.click();
});
document.getElementById("menuView")?.addEventListener("click", () => {
  if (els.scaleResetBtn) els.scaleResetBtn.click();
});
document.getElementById("menuHelp")?.addEventListener("click", () => {
  showToast("FProject Launcher — Справка");
  if (inTreeMode()) {
    stopDiffPolling();
    setMode("objects");
  }
});

// Кэш настроек из /api/config/apps: действие по умолчанию,
// переключатель нативных программ и пути exe по расширениям.
async function loadAppSettings() {
  try {
    const res = await fetch("/api/config/apps");
    if (res.ok) {
      state.appSettings = await res.json();
    }
  } catch (err) {
  }
  return state.appSettings;
}

function extractAppPath(val) {
  if (!val) return "";
  if (typeof val === "object" && val !== null) {
    return String(val.path || "").trim();
  }
  return String(val || "").trim();
}

function settingsCustomExe(extension) {
  if (!extension) return "";
  const raw = String(extension).trim().toLowerCase();
  const withDot = raw.startsWith(".") ? raw : "." + raw;
  const withoutDot = raw.startsWith(".") ? raw.slice(1) : raw;
  const val =
    state.appSettings?.[withDot] ||
    state.appSettings?.[withoutDot] ||
    state.appSettings?.[withDot.toUpperCase()] ||
    state.appSettings?.[withoutDot.toUpperCase()] ||
    (withDot === ".dwg" || withDot === ".dxf" ? state.appSettings?.settingDwgExe : "") ||
    (withDot === ".pdf" ? state.appSettings?.settingPdfExe : "") ||
    ([".doc", ".docx", ".rtf", ".odt"].includes(withDot) ? state.appSettings?.settingWordExe : "") ||
    ([".xls", ".xlsx", ".xlsm", ".csv", ".ods", ".xlsb"].includes(withDot) ? state.appSettings?.settingExcelExe : "") ||
    ([".ppt", ".pptx", ".odp"].includes(withDot) ? state.appSettings?.settingPptExe : "") ||
    ([".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".ico", ".svg"].includes(withDot) ? state.appSettings?.settingImgExe : "") ||
    ([".zip", ".rar", ".7z", ".tar", ".gz"].includes(withDot) ? state.appSettings?.settingArchExe : "") ||
    ([".txt", ".log", ".ini", ".cfg", ".json", ".xml", ".yaml", ".yml"].includes(withDot) ? state.appSettings?.settingTxtExe : "") ||
    ([".mp4", ".avi", ".mov", ".mkv", ".mp3", ".wav"].includes(withDot) ? state.appSettings?.settingMediaExe : "") ||
    "";
  return extractAppPath(val);
}

const NATIVE_APP_GROUPS = [
  { id: "settingDwgExe", label: "AutoCAD / DWG (.dwg, .dxf)", exts: [".dwg", ".dxf"], ph: "Например: C:\\Program Files\\Autodesk\\AutoCAD 2024\\acad.exe" },
  { id: "settingPdfExe", label: "PDF-просмотрщик (.pdf)", exts: [".pdf"], ph: "Например: C:\\Program Files\\Adobe\\Acrobat DC\\Acrobat\\Acrobat.exe" },
  { id: "settingWordExe", label: "Microsoft Word (.doc, .docx, .rtf, .odt)", exts: [".doc", ".docx", ".rtf", ".odt"], ph: "Например: C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE" },
  { id: "settingExcelExe", label: "Microsoft Excel (.xls, .xlsx, .xlsm, .csv, .ods)", exts: [".xls", ".xlsx", ".xlsm", ".csv", ".ods"], ph: "Например: C:\\Program Files\\Microsoft Office\\root\\Office16\\EXCEL.EXE" },
  { id: "settingPptExe", label: "Microsoft PowerPoint (.ppt, .pptx, .odp)", exts: [".ppt", ".pptx", ".odp"], ph: "Например: C:\\Program Files\\Microsoft Office\\root\\Office16\\POWERPNT.EXE" },
  { id: "settingImgExe", label: "Просмотр изображений (.jpg, .png, .gif и др.)", exts: [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff", ".ico", ".svg"], ph: "Например: C:\\Windows\\System32\\mspaint.exe" },
  { id: "settingArchExe", label: "Архиватор (.zip, .rar, .7z и др.)", exts: [".zip", ".rar", ".7z", ".tar", ".gz"], ph: "Например: C:\\Program Files\\7-Zip\\7zFM.exe" },
  { id: "settingTxtExe", label: "Текстовые файлы (.txt, .log и др.)", exts: [".txt", ".log", ".ini", ".cfg", ".json", ".xml", ".yaml", ".yml"], ph: "Например: C:\\Windows\\System32\\notepad.exe" },
  { id: "settingMediaExe", label: "Видео и музыка (.mp4, .mp3 и др.)", exts: [".mp4", ".avi", ".mov", ".mkv", ".mp3", ".wav"], ph: "Например: C:\\Program Files\\VideoLAN\\VLC\\vlc.exe" },
];

function renderSettingsAppRows(cfg) {
  const form = document.getElementById("settingsAppsForm");
  if (!form) return;
  form.replaceChildren();
  for (const group of NATIVE_APP_GROUPS) {
    const current = group.exts.map((e) => extractAppPath(cfg?.[e])).find(Boolean) || "";
    const field = document.createElement("div");
    field.className = "settings-field";
    const label = document.createElement("label");
    label.className = "settings-label";
    label.setAttribute("for", group.id);
    label.textContent = group.label + ":";
    const row = document.createElement("div");
    row.className = "settings-input-row";
    const input = document.createElement("input");
    input.type = "text";
    input.id = group.id;
    input.className = "settings-input";
    input.placeholder = group.ph;
    input.spellcheck = false;
    input.value = current;
    input.dataset.exts = group.exts.join(",");
    const browse = document.createElement("button");
    browse.type = "button";
    browse.className = "settings-browse-btn";
    browse.dataset.target = group.id;
    browse.title = "Выбрать файл .exe через проводник";
    browse.textContent = "Обзор…";
    browse.addEventListener("click", () => browseExeForSetting(group.id));
    const clear = document.createElement("button");
    clear.type = "button";
    clear.className = "settings-clear-btn";
    clear.title = "Очистить";
    clear.textContent = "✕";
    clear.addEventListener("click", () => {
      input.value = "";
      updateDwgHintVisibility();
    });
    input.addEventListener("input", () => {
      if (group.id === "settingDwgExe") updateDwgHintVisibility();
    });
    row.append(input, browse, clear);
    field.append(label, row);
    form.append(field);
  }
}

// РљРѕРЅС‚РµРєСЃС‚РЅРѕРµ РјРµРЅСЋ С„Р°Р№Р»Р°/РїР°РїРєРё/С‚РµРєСЃС‚Р° (РїСЂР°РІР°СЏ РєРЅРѕРїРєР° РјС‹С€Рё).
// РџСѓРЅРєС‚С‹: РЎРєРѕРїРёСЂРѕРІР°С‚СЊ, РџРµСЂРµРІРµСЃС‚Рё, РќР°Р№С‚Рё РІ РґРѕРєСѓРјРµРЅС‚Рµ, РЎРєРѕРїРёСЂРѕРІР°С‚СЊ РїСѓС‚СЊ, РћС‚РєСЂС‹С‚СЊ РІ РїСЂРѕРіСЂР°РјРјРµ, РћС‚РєСЂС‹С‚СЊ РІ РїСЂРѕРІРѕРґРЅРёРєРµ.
function hideFileContextMenu() {
  if (els.contextMenu && !els.contextMenu.hidden) {
    els.contextMenu.hidden = true;
    return true;
  }
  return false;
}
window.hideFileContextMenu = hideFileContextMenu;

function triggerTranslateText(text) {
  if (!text) return;
  try {
    const win = els.pdfDocFrame?.contentWindow;
    if (win && typeof win.launcherTranslateText === "function") {
      win.launcherTranslateText(text);
      return;
    }
  } catch (_) {}
  showToast("\u041F\u0435\u0440\u0435\u0432\u043E\u0434: " + text.slice(0, 35) + "\u2026");
}

function triggerSearchText(text) {
  if (!text) return;
  openPdfJsSearch(text);
}

function showFileContextMenu(clientX, clientY, target) {
  const menu = els.contextMenu;
  if (!menu || !target) return;

  const isPdf = Boolean(target.isPdf);
  const pdfSelectedText = isPdf ? String(target.selectedText || "").trim() : "";
  const genericSelectedText = isPdf ? "" : (target.selectedText || window.getSelection()?.toString() || "").trim();
  const items = [];

  if (isPdf) {
    const hasText = Boolean(pdfSelectedText);
    const canCad = Boolean(target.canCadExport);

    // 1. Скопировать
    items.push({
      icon: "\uD83D\uDCCB",
      label: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C",
      hint: "Ctrl+C",
      disabled: !hasText,
      run: async () => {
        if (!hasText) return;
        await copyTextToClipboard(pdfSelectedText, "");
      },
    });

    // 2. Перевести
    items.push({
      icon: "\uD83C\uDF10",
      label: "\u041F\u0435\u0440\u0435\u0432\u0435\u0441\u0442\u0438",
      hint: "",
      disabled: !hasText,
      run: () => {
        if (!hasText) return;
        const pdfWin = els.pdfDocFrame?.contentWindow;
        if (pdfWin && typeof pdfWin.launcherTranslateText === "function") {
          pdfWin.launcherTranslateText(pdfSelectedText);
        } else {
          showToast("\u0414\u0435\u0439\u0441\u0442\u0432\u0438\u0435 \u043F\u0435\u0440\u0435\u0432\u043E\u0434\u0430 \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u043D\u043E: \u0444\u0443\u043D\u043A\u0446\u0438\u044F PDF viewer \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430");
        }
      },
    });

    // 3. В DWG перевести
    items.push({
      icon: "\uD83D\uDCD0",
      label: "\u0412 DWG \u043F\u0435\u0440\u0435\u0432\u0435\u0441\u0442\u0438",
      hint: "",
      disabled: !canCad,
      run: () => {
        if (!canCad) return;
        const pdfWin = els.pdfDocFrame?.contentWindow;
        if (pdfWin && typeof pdfWin.exportCurrentZoneToCad === "function") {
          pdfWin.exportCurrentZoneToCad();
        } else {
          showToast("\u042D\u043A\u0441\u043F\u043E\u0440\u0442 \u0432 CAD \u043D\u0435\u0434\u043E\u0441\u0442\u0443\u043F\u0435\u043D: \u0444\u0443\u043D\u043A\u0446\u0438\u044F \u044D\u043A\u0441\u043F\u043E\u0440\u0442\u0430 \u043D\u0435 \u043D\u0430\u0439\u0434\u0435\u043D\u0430");
        }
      },
    });

    items.push({ sep: true });
  } else if (genericSelectedText) {
    // Прежнее поведение меню других окон без изменений
    items.push({
      icon: "\uD83D\uDCCB",
      label: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C",
      hint: "Ctrl+C",
      run: () => copyTextToClipboard(genericSelectedText, "\u0422\u0435\u043A\u0441\u0442 \u0441\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u043D \u0432 \u0431\u0443\u0444\u0435\u0440 \u043E\u0431\u043C\u0435\u043D\u0430"),
    });
    items.push({
      icon: "\uD83C\uDF10",
      label: "\u041F\u0435\u0440\u0435\u0432\u0435\u0441т\u0438",
      hint: "",
      run: () => triggerTranslateText(genericSelectedText),
    });
    items.push({
      icon: "\uD83D\uDD0D",
      label: "\u041D\u0430\u0439\u0442\u0438 \u0432 \u0434\u043E\u043A\u0443\u043C\u0435\u043D\u0442\u0435",
      hint: "",
      run: () => triggerSearchText(genericSelectedText),
    });
    items.push({ sep: true });
  } else {
    items.push({
      icon: "\uD83D\uDCCB",
      label: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C",
      hint: "Ctrl+C",
      disabled: true,
      run: () => {},
    });
    items.push({ sep: true });
  }

  // 2. РџСѓРЅРєС‚ "РЎРєРѕРїРёСЂРѕРІР°С‚СЊ РїСѓС‚СЊ"
  if (target.path) {
    items.push({
      icon: "\uD83D\uDCC2",
      label: "\u0421\u043A\u043E\u043F\u0438\u0440\u043E\u0432\u0430\u0442\u044C \u043F\u0443\u0442\u044C",
      hint: "",
      run: () => copyPathToClipboard(target.path),
    });
    items.push({ sep: true });
  }

  // 3. РџСѓРЅРєС‚ "РћС‚РєСЂС‹С‚СЊ РІ РїСЂРѕРіСЂР°РјРјРµ РїРѕ СѓРјРѕР»С‡Р°РЅРёСЋ"
  if (target.path && !target.isDir) {
    items.push({
      icon: "\u2197\uFE0F",
      label: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0432 \u043F\u0440\u043E\u0433\u0440\u0430\u043C\u043C\u0435 \u043F\u043E \u0443\u043C\u043E\u043B\u0447\u0430\u043D\u0438\u044E",
      hint: "",
      run: () => openFileByPath(target.path, "native"),
    });
  }

  // 4. РџСѓРЅРєС‚ "РћС‚РєСЂС‹С‚СЊ РІ РїСЂРѕРІРѕРґРЅРёРєРµ"
  if (target.path) {
    items.push({
      icon: "\uD83D\uDCC1",
      label: "\u041E\u0442\u043A\u0440\u044B\u0442\u044C \u0432 \u043F\u0440\u043E\u0432\u043E\u0434\u043D\u0438\u043A\u0435",
      hint: "",
      run: () => openFileByPath(target.path, "explorer"),
    });
  }

  menu.replaceChildren();
  for (const it of items) {
    if (it.sep) {
      const d = document.createElement("div");
      d.className = "context-menu-separator";
      menu.append(d);
      continue;
    }
    const b = document.createElement("button");
    b.type = "button";
    b.className = "context-menu-item";
    b.title = it.label;
    if (it.disabled) {
      b.disabled = true;
    }

    const left = document.createElement("div");
    left.className = "context-menu-item-left";

    const icon = document.createElement("span");
    icon.className = "context-menu-icon";
    icon.textContent = it.icon || "";

    const lab = document.createElement("span");
    lab.className = "context-menu-label";
    lab.textContent = it.label;

    left.append(icon, lab);
    b.append(left);

    if (it.hint) {
      const hint = document.createElement("span");
      hint.className = "context-menu-shortcut";
      hint.textContent = it.hint;
      b.append(hint);
    }

    b.addEventListener("click", (event) => {
      event.stopPropagation();
      if (!it.disabled && typeof it.run === "function") {
        it.run();
      }
      hideFileContextMenu();
    });
    menu.append(b);
  }

  menu.style.left = clientX + "px";
  menu.style.top = clientY + "px";
  menu.hidden = false;
  const w = menu.offsetWidth || 240;
  const h = menu.offsetHeight || 160;
  menu.style.left = Math.max(8, Math.min(clientX, window.innerWidth - w - 8)) + "px";
  menu.style.top = Math.max(8, Math.min(clientY, window.innerHeight - h - 8)) + "px";
}

// Р“Р»РѕР±Р°Р»СЊРЅС‹Рµ СЃР»СѓС€Р°С‚РµР»Рё РѕС‚РјРµРЅС‹ РєРѕРЅС‚РµРєСЃС‚РЅРѕРіРѕ РјРµРЅСЋ:
// 1) РљР»РёРє РјС‹С€СЊСЋ РІ Р»СЋР±РѕРµ СЃРІРѕР±РѕРґРЅРѕРµ РїРѕР»Рµ/РїСЂРѕСЃС‚СЂР°РЅСЃС‚РІРѕ
const handleDismissContextMenu = (event) => {
  if (!els.contextMenu || els.contextMenu.hidden) return;
  if (event && els.contextMenu.contains(event.target)) return;
  hideFileContextMenu();
};
document.addEventListener("pointerdown", handleDismissContextMenu, true);
document.addEventListener("mousedown", handleDismissContextMenu, true);
document.addEventListener("click", handleDismissContextMenu, true);
window.addEventListener("scroll", handleDismissContextMenu, true);
window.addEventListener("resize", () => hideFileContextMenu());
window.addEventListener("blur", () => hideFileContextMenu());

// 2) РћС‚РјРµРЅР° РєРѕРЅС‚РµРєСЃС‚РЅРѕРіРѕ РјРµРЅСЋ РїРѕ РєР»Р°РІРёС€Рµ Esc (РІ С„Р°Р·Рµ Р·Р°С…РІР°С‚Р°, РґРѕ РѕСЃС‚Р°Р»СЊРЅС‹С… РѕР±СЂР°Р±РѕС‚С‡РёРєРѕРІ)
window.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (hideFileContextMenu()) {
      event.preventDefault();
      event.stopPropagation();
      return;
    }
  }
}, true);

function hookIframeContextMenuDismiss(iframe) {
  if (!iframe) return;
  const attach = () => {
    try {
      const doc = iframe.contentDocument;
      if (!doc || doc.__ctxDismissHooked) return;
      doc.__ctxDismissHooked = true;
      const dismiss = (e) => {
        if (e && e.button === 2) return;
        hideFileContextMenu();
      };
      doc.addEventListener("pointerdown", dismiss, true);
      doc.addEventListener("mousedown", dismiss, true);
      doc.addEventListener("click", dismiss, true);
      doc.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
          if (hideFileContextMenu()) {
            e.preventDefault();
            e.stopPropagation();
          }
        }
      }, true);
      iframe.contentWindow?.addEventListener("scroll", dismiss, true);
      iframe.contentWindow?.addEventListener("blur", dismiss);
    } catch (_) {}
  };
  attach();
  iframe.addEventListener("load", attach);
}


function setDwgHint(message) {
  const hint = document.getElementById("settingsDwgHint");
  if (!hint) return;
  if (message) {
    hint.textContent = message;
    hint.hidden = false;
  } else {
    hint.textContent = "";
    hint.hidden = true;
  }
}

function updateDwgHintVisibility() {
  const dwgInput = document.getElementById("settingDwgExe");
  if (!dwgInput || (dwgInput.value && dwgInput.value.trim())) {
    setDwgHint("");
  }
}

// Управление модальным окном "Параметры"
async function openSettingsModal(highlightExt) {
  setDwgHint("");
  try {
    const res = await fetch("/api/config/apps");
    if (res.ok) {
      const cfg = await res.json();
      renderSettingsAppRows(cfg);
    }
  } catch (err) {
  }
  if (els.settingsModal) {
    els.settingsModal.hidden = false;
    if (highlightExt) {
      const norm = String(highlightExt).toLowerCase();
      const dot = norm.startsWith(".") ? norm : "." + norm;
      const targetInput = Array.from(document.querySelectorAll("#settingsAppsForm .settings-input")).find(
        (inp) => (inp.dataset.exts || "").split(",").map((e) => e.trim().toLowerCase()).includes(dot)
      );
      if (targetInput) {
        setTimeout(() => {
          targetInput.focus();
          targetInput.select?.();
          targetInput.classList.add("input-updated");
          setTimeout(() => targetInput.classList.remove("input-updated"), 2000);
        }, 100);
      }
    }
  }
}

function closeSettingsModal() {
  if (els.settingsModal) els.settingsModal.hidden = true;
}

function applyImportedToInputs(imported, onlyIfEmpty = false) {
  if (!imported) return 0;
  let count = 0;
  const inputs = Array.from(document.querySelectorAll("#settingsAppsForm .settings-input"));
  inputs.forEach((input) => {
    if (onlyIfEmpty && input.value && input.value.trim()) {
      return;
    }
    const exts = String(input.dataset.exts || "").split(",").map((e) => e.trim().toLowerCase()).filter(Boolean);
    for (const ext of exts) {
      const val = imported[ext];
      const p = extractAppPath(val);
      if (p) {
        input.value = p;
        input.classList.add("input-updated");
        setTimeout(() => input.classList.remove("input-updated"), 1500);
        count++;
        break;
      }
    }
  });
  return count;
}

async function parseApiResponse(res) {
  let data = null;
  try {
    data = await res.json();
  } catch (parseErr) {
    data = null;
  }
  if (!res.ok) {
    if (data && (data.message || data.error || data.error_code)) {
      const code = data.error_code ? ` [${data.error_code}]` : "";
      const msg = data.message || data.error || "Неизвестная ошибка сервера";
      throw new Error(`Ошибка сервера (${res.status})${code}: ${msg}`);
    }
    throw new Error(`Ошибка сервера HTTP ${res.status}. Проверьте состояние процесса Launcher.`);
  }
  return data || {};
}

function handleApiFetchError(err, prefix = "Не удалось определить программы Windows") {
  const isNetwork =
    err instanceof TypeError ||
    String(err.message || "").toLowerCase().includes("failed to fetch") ||
    String(err.message || "").toLowerCase().includes("networkerror") ||
    String(err.message || "").toLowerCase().includes("load failed");
  if (isNetwork) {
    showToast(
      "Нет соединения с локальным backend Launcher.\nПолностью перезапустите Launcher.\nПодробности доступны в журнале Launcher."
    );
  } else {
    showToast(`${prefix}: ${err.message || err}.\nПодробности записаны в журнал Launcher.`);
  }
}

async function fillEmptyFromWindows() {
  const btn = document.getElementById("settingsFillEmptyBtn");
  const prevText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Поиск в Windows...";
  }
  try {
    const res = await fetch("/api/config/apps/import-windows", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ mode: "fill_empty" })
    });
    const data = await parseApiResponse(res);
    const count = applyImportedToInputs(data.imported || {}, true);
    if (data.skipped?.[".dwg"] === "no_usable_windows_association" || data.report?.dwgHint) {
      const dwgInput = document.getElementById("settingDwgExe");
      if (!dwgInput || !dwgInput.value) {
        setDwgHint("Windows вернула системный CAD launcher, а не фактическое приложение. Выберите DWG Viewer или AutoCAD вручную.");
      }
    } else {
      updateDwgHintVisibility();
    }

    if (count > 0) {
      showToast(`Заполнено пустых полей: ${count}. Не забудьте нажать «Сохранить»!`);
    } else {
      showToast("Все поля уже заполнены или Windows не вернула подходящих ассоциаций.");
    }
  } catch (err) {
    handleApiFetchError(err, "Не удалось определить программы Windows");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevText;
    }
  }
}

async function replaceFromWindows() {
  const confirmed = confirm(
    "Заменить сохранённые приложения программами по умолчанию Windows?\n\nСуществующие настройки для поддерживаемых типов файлов будут перезаписаны ассоциациями из Windows (при наличии пригодного приложения)."
  );
  if (!confirmed) {
    return;
  }

  const btn = document.getElementById("settingsReplaceBtn");
  const prevText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Замена из Windows...";
  }
  try {
    const res = await fetch("/api/config/apps/import-windows", {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ mode: "replace_confirmed" })
    });
    const data = await parseApiResponse(res);
    const count = applyImportedToInputs(data.imported || {}, false);
    if (data.skipped?.[".dwg"] === "no_usable_windows_association" || data.report?.dwgHint) {
      setDwgHint("Windows вернула системный CAD launcher, а не фактическое приложение. Выберите DWG Viewer или AutoCAD вручную.");
    } else {
      updateDwgHintVisibility();
    }

    if (count > 0) {
      showToast(`Обновлено категорий из Windows: ${count}. Не забудьте нажать «Сохранить»!`);
    } else {
      showToast("Подходящих ассоциаций Windows не найдено.");
    }
  } catch (err) {
    handleApiFetchError(err, "Не удалось заменить программы Windows");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevText;
    }
  }
}

async function openWindowsSettings() {
  const btn = document.getElementById("settingsOpenWinSettingsBtn");
  const prevText = btn ? btn.textContent : "";
  if (btn) {
    btn.disabled = true;
  }
  try {
    const res = await fetch("/api/config/apps/open-windows-settings", {
      method: "POST",
      headers: { "Accept": "application/json" }
    });
    await parseApiResponse(res);
    showToast("Открываем параметры приложений Windows…");
  } catch (err) {
    handleApiFetchError(err, "Не удалось открыть настройки Windows");
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = prevText;
    }
  }
}

async function saveSettings() {
  const cfg = {
    useNativeApps: state.appSettings?.useNativeApps !== false,
  };
  document.querySelectorAll("#settingsAppsForm .settings-input").forEach((input) => {
    const value = (input.value || "").trim().replace(/^["']+|["']+$/g, "").trim();
    String(input.dataset.exts || "").split(",").map((e) => e.trim()).filter(Boolean).forEach((ext) => {
      const lower = ext.toLowerCase();
      const dot = lower.startsWith(".") ? lower : "." + lower;
      const noDot = dot.slice(1);
      cfg[dot] = value;
      cfg[noDot] = value;
      cfg[dot.toUpperCase()] = value;
      cfg[noDot.toUpperCase()] = value;
    });
    if (input.id) {
      cfg[input.id] = value;
    }
  });
  try {
    const res = await fetch("/api/config/apps", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cfg),
    });
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Не удалось сохранить настройки");
    }
    closeSettingsModal();
    await loadAppSettings().catch(() => {});
    showToast("Параметры успешно сохранены");
  } catch (err) {
    showOperationError(err);
  }
}

async function browseExeForSetting(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const btn = document.querySelector(`.settings-browse-btn[data-target="${inputId}"]`);
  if (btn) btn.disabled = true;
  try {
    const currentPath = (input.value || "").trim();
    const res = await fetch("/api/choose-exe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current: currentPath }),
    });
    if (!res.ok) {
      throw new Error(`Ошибка сервера: HTTP ${res.status}`);
    }
    const data = await res.json();
    if (data.path) {
      input.value = data.path;
      input.classList.add("input-updated");
      setTimeout(() => input.classList.remove("input-updated"), 1500);
      updateDwgHintVisibility();
    } else if (data.error && !data.cancelled && !data.timedOut) {
      showOperationError(new Error(data.error));
    }
  } catch (err) {
    showOperationError(err);
  } finally {
    if (btn) btn.disabled = false;
  }
}

if (els.btnSettings) els.btnSettings.addEventListener("click", openSettingsModal);
if (els.settingsCloseBtn) els.settingsCloseBtn.addEventListener("click", closeSettingsModal);
if (els.settingsCancelBtn) els.settingsCancelBtn.addEventListener("click", closeSettingsModal);
if (els.settingsFillEmptyBtn) els.settingsFillEmptyBtn.addEventListener("click", fillEmptyFromWindows);
if (els.settingsReplaceBtn) els.settingsReplaceBtn.addEventListener("click", replaceFromWindows);
if (els.settingsOpenWinSettingsBtn) els.settingsOpenWinSettingsBtn.addEventListener("click", openWindowsSettings);
if (els.settingsSaveBtn) els.settingsSaveBtn.addEventListener("click", saveSettings);
if (els.settingsModal) {
  els.settingsModal.addEventListener("click", (event) => {
    if (event.target === els.settingsModal) closeSettingsModal();
  });
}
document.querySelectorAll(".settings-browse-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.dataset.target;
    if (targetId) browseExeForSetting(targetId);
  });
});
document.querySelectorAll(".settings-clear-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const targetId = btn.dataset.target;
    const input = document.getElementById(targetId);
    if (input) {
      input.value = "";
      updateDwgHintVisibility();
    }
  });
});



// Настройки подгружаем сразу, чтобы клики знали действие по умолчанию.
loadAppSettings().catch(() => {});

// Версия кода в заголовке окна: видно, какой сборкой пользуемся.
// Если заголовок без версии — окно старое, его надо закрыть и открыть заново.
try {
  const vm = String((typeof document !== "undefined" && document.currentScript && document.currentScript.src) || "").match(/[?&]v=([^&]+)/);
  if (vm) document.title = `FProject Launcher · ${decodeURIComponent(vm[1])}`;
} catch (e) {}


// =============================================================================
// Интеграция с нативным просмотрщиком Mozilla PDF.js
// Двусторонняя синхронизация (лента миниатюр ↔ страницы PDF) и поиск
// =============================================================================

function openPdfJsSearch(text) {
  const win = els.pdfDocFrame?.contentWindow;
  if (!win) return;
  win.focus();
  try {
    if (win.PDFViewerApplication && win.PDFViewerApplication.findBar) {
      if (!win.PDFViewerApplication.findBar.opened) {
        win.PDFViewerApplication.findBar.open();
      }
      if (win.PDFViewerApplication.findBar.highlightAll) {
        win.PDFViewerApplication.findBar.highlightAll.checked = true;
      }
      const findInput = win.document?.getElementById("findInput");
      if (findInput) {
        if (text) {
          findInput.value = text;
        }
        findInput.focus();
        findInput.select();
        if (text) {
          findInput.dispatchEvent(new Event("input", { bubbles: true }));
        }
      }
    }
  } catch (err) {
    console.warn("openPdfJsSearch error:", err?.name || "Error");
  }
}

function handlePdfViewerPageChanged(pageNum) {
  if (!pageNum) return;
  const currentDoc = els.pdfDocFrame?.dataset?.currentDoc;
  if (!currentDoc) return;

  const matchingPage = state.renderedPages?.find(
    (p) => (p.documentPath === currentDoc || p.sourcePath === currentDoc || p.previewFor?.path === currentDoc) && Number(p.page) === pageNum
  );

  if (matchingPage) {
    state.activePageKey = pageKey(matchingPage);
    updateActivePdfThumb();
    updatePagePosition(matchingPage);

    const activeThumb = els.pdfThumbs?.querySelector(".pdf-thumb.active");
    if (activeThumb) {
      activeThumb.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "smooth" });
    }
  }
}

function initPdfDocFrameSync() {
  if (!els.pdfDocFrame) return;

  els.pdfDocFrame.addEventListener("load", () => {
    try {
      const win = els.pdfDocFrame.contentWindow;
      if (!win) return;

      const setupSync = () => {
        const app = win.PDFViewerApplication;
        if (!app || !app.eventBus) return;

        app.eventBus.on("pagechanging", (evt) => {
          const pageNum = evt.pageNumber;
          handlePdfViewerPageChanged(pageNum);
        });

        app.eventBus.on("cursortoolchanged", (evt) => {
          if (win && typeof win.getViewerToolMode === "function") {
            updateViewerToolButton(win.getViewerToolMode());
          } else {
            updateViewerToolButton(evt.tool === 1 ? 1 : 0);
          }
        });

        // Плавное пошаговое масштабирование колесом мыши с Ctrl (как кнопки + и − на нижней панели)
        let lastWheelZoomTime = 0;
        win.addEventListener("wheel", (evt) => {
          if (!evt.ctrlKey && !evt.metaKey) return;
          evt.preventDefault();
          evt.stopImmediatePropagation();
          const now = performance.now();
          if (now - lastWheelZoomTime < 80) return;
          lastWheelZoomTime = now;
          const previousScale = app.pdfViewer?.currentScale || 1;
          const delta = evt.deltaY || evt.detail || 0;
          if (delta < 0) {
            app.zoomIn(1);
          } else if (delta > 0) {
            app.zoomOut(1);
          } else {
            return;
          }
          if (typeof app._centerAtPos === "function") {
            app._centerAtPos(previousScale, evt.clientX, evt.clientY);
          }
        }, { capture: true, passive: false });

        if (els.pdfDocFrame.dataset.targetPage) {
          const target = parseInt(els.pdfDocFrame.dataset.targetPage, 10);
          if (target && app.page !== target) {
            app.page = target;
          }
        }
      };

      if (win.PDFViewerApplication && win.PDFViewerApplication.initialized) {
        setupSync();
      } else {
        win.document.addEventListener("webviewerloaded", () => {
          const app = win.PDFViewerApplication;
          if (app && app.initializedPromise) {
            app.initializedPromise.then(setupSync);
          } else {
            setupSync();
          }
        }, { once: true });
      }
    } catch (e) {
      console.warn("PDF viewer frame sync setup:", e);
    }
  });
}

function updateViewerToolButton(mode) {
  if (!els.viewToggleTool) return;
  const m = Number(mode);
  if (m === 1 || mode === "hand") {
    els.viewToggleTool.textContent = "🖐️ Лапа";
    els.viewToggleTool.title = "Активен режим: Лапа (панорамирование). Клик — переключить на Рамку (AutoCAD)";
    els.viewToggleTool.classList.add("active");
  } else if (m === 2 || mode === "text") {
    els.viewToggleTool.textContent = "I Текст";
    els.viewToggleTool.title = "Активен режим: Текст (обычный построчный курсор). Клик — переключить на Лапу (панорамирование)";
    els.viewToggleTool.classList.add("active");
  } else {
    els.viewToggleTool.textContent = "↖️ Рамка";
    els.viewToggleTool.title = "Активен режим: Рамка (AutoCAD). Клик — переключить на Текст (обычный курсор)";
    els.viewToggleTool.classList.remove("active");
  }
}
window.updateViewerToolButton = updateViewerToolButton;

function toggleViewerTool() {
  const isPdf = Boolean(els.pdfDocViewer && !els.pdfDocViewer.hidden);
  if (isPdf) {
    const win = els.pdfDocFrame?.contentWindow;
    if (win && typeof win.getViewerToolMode === "function" && typeof win.setViewerToolMode === "function") {
      const current = win.getViewerToolMode();
      // Cycle: 0 (Рамка) -> 2 (Текст) -> 1 (Лапа) -> 0 (Рамка)
      const next = current === 0 ? 2 : current === 2 ? 1 : 0;
      win.setViewerToolMode(next);
      updateViewerToolButton(next);
      return;
    }
  } else {
    state.view.panMode = !state.view.panMode;
    updateViewTransform();
    updateViewerToolButton(state.view.panMode ? 1 : 0);
  }
}

if (els.viewToggleTool) {
  els.viewToggleTool.addEventListener("click", toggleViewerTool);
}


if (els.viewBackBtn) {
  els.viewBackBtn.addEventListener("click", () => {
    exitWindow3();
  });
}

window.handleGlobalEscape = handleGlobalEscape;
initPdfDocFrameSync();
hookIframeContextMenuDismiss(els.pdfDocFrame);
hookIframeContextMenuDismiss(els.excelSheetFrame);
hookIframeContextMenuDismiss(els.wordDocFrame);
