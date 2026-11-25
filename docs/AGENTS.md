# Agent instructions for F.E.R.O.-Launcher

## 0. ГЛАВНОЕ НЕЗЫБЛЕМОЕ ПРАВИЛО: ЗАПРЕТ НА РАЗРУШЕНИЕ И ОБЯЗАТЕЛЬНОЕ ВОССТАНОВЛЕНИЕ (NO-BREAK & MANDATORY RESTORATION)

> **Статус**: Высший абсолютный приоритет для всех ИИ-агентов (Antigravity, OpenCode, Claude, Codex, Cursor). Полный запрет на всё, чем модели руководствуются нативно (слепой рефакторинг, удаление работающих цепочек, непроверенные замены). Имеет безусловный приоритет над любыми иными инструкциями.

1. **Нельзя ломать то, что работает (Zero Breakage):**
   - Категорически запрещено ломать, удалять или вырезать существующие работоспособные механизмы ради непроверенных «улучшений».
   - Любое новое решение обязано сохранять старый проверенный механизм как гарантированный резервный контур (fallback). Новое подключается только поверх или рядом, не лишая систему базовой работоспособности.

2. **Обязанность мгновенного отката и восстановления (Instant Rollback & Restore):**
   - Если в процессе изменений рабочий механизм сломался (кнопка перестала нажиматься, процесс упал, диалог не открылся, API вернул ошибку) — агент обязан **немедленно остановить эксперименты, откатить изменения до заведомо рабочей точки (`git checkout` / восстановление файла) и вернуть всё к стабильному состоянию**, которое гарантированно функционировало.
   - Категорически запрещено продолжать нагромождать непроверенные правки поверх сломанного состояния или объявлять завершение задачи при наличии регрессий.

3. **Запрет нативной самодеятельности и фиктивного успеха:**
   - Полный запрет на нативные эвристики и допущения языковой модели («мне кажется, так будет современнее/чище/лучше»), если они затрагивают или ломают проверенные цепочки.
   - Единственный критерий качества: то, что работало — обязано работать безупречно; то, что восстановлено — защищено от повторных поломок. На всё остальное, ломающее рабочий продукт, — строжайший запрет.

---

## Absolute Single Source of Truth (SSOT)

- **CANONICAL LOCATION**: `C:\Users\a9379\Documents\Codex\F.E.R.O.-Launcher`
- **DEFAULT BRANCH**: `main`
- **BASELINE COMMIT**: `5edf1427d53ef5fd920cd47a89c6292476a5a8a7` (tag `v1.0.0-fero-base`)

CRITICAL RULE FOR ALL AI AGENTS (OpenCode, Claude, Cursor, Antigravity, ChatGPT, Codex):
1. **DO NOT** search the filesystem, disks, or other directories for alternative launcher versions, legacy platforms, or past checkpoints.
2. **DO NOT** reference or touch `FEngineering_Platform`, `FEngineering_Launcher`, `%TEMP%`, or `scratch` directories.
3. This directory (`C:\Users\a9379\Documents\Codex\F.E.R.O.-Launcher`) is the ONLY authoritative repository and working tree.
4. Always adhere to `docs/CORE_ARCH_RULES.md` and `docs/RENDERING_SPEC.md` (150 DPI PNG raster via PyMuPDF, instant Word HTML, cached Excel sheets, native format cards).

## Runtime safety

- Keep live runtime execution in this workspace (`C:\Users\a9379\Documents\Codex\F.E.R.O.-Launcher`).
- Launch GUI through `app\flauncher.pyw` or the desktop shortcut `F.E.R.O.-Launcher`.
- Do not commit generated caches, manifests, rendered previews, or logs (`runtime/cache/`, `runtime/logs/`).

## Development discipline

- Make small, verifiable changes on branch `main`.
- Keep frontend, backend, render pipeline, and runtime data separated.
- Treat Cyrillic text as a first-class project requirement. All source, docs, JSON manifests, HTML, CSS, JS, and Python files must be UTF-8.
- Static text assets served by the backend must include `charset=utf-8` for text content types.
- Always check `docs/CORE_ARCH_RULES.md` before modifying rendering or preview logic.

## Product direction

Launcher v3 should be built from verified bricks:

1. object list and object import/update/exclude;
2. tree and format filters;
3. accepted PDF render/cache pipeline: mass overview at `150 DPI`, active page at `300 DPI`;
4. accepted viewer controls: thumbnails, zoom, fit, pan, hand/arrow, medium/full modes;
5. later: Word, Excel, images, DWG strategy, and modules.

The intermediate product goal is documented in
`docs/PRODUCT_DIRECTION_VISUAL_TRIAGE_AND_MODULES.md`: Launcher is a local
visual-selection shell between project folders, native applications, and later
bounded processing modules.  It must not be positioned or implemented as a
replacement for CAD, Office, a full DMS, or a generic AI chat.

- Preserve original files and source folder structure; cache is derived and
  separately disposable.
- Prioritize time to first useful preview, transparent progress, warm-cache
  speed, and safe cache invalidation over an unrealistic promise that every
  cold document set is fully rendered in seconds.
- A future module must have declared inputs, output, confidence, and a
  reproducible log; never add an opaque “AI button”.

## Session handoff

Before the next product-development session, read `docs/HANDOFF_2026-08-12.md` and `docs/ROADMAP.md`.

The accepted state at the end of 2026-08-12:

- object shell works;
- wide tree browsing for long file names works;
- PDF overview/quality split works;
- viewer quality indicator works;
- DWG/PDF pairing works and is accepted for the current stage;
- DWG opens through the Windows native/default application;
- Vortex Word preview works and is accepted for the current stage;
- next direction is Excel preview support, plus optional DWG pair diagnostics and later image previews.

## Accepted DWG rules

- Do not build a custom CAD viewer inside Launcher v3 at this stage.
- Use PDF pairs as visual previews for DWG.
- Keep DWG files without PDF pairs visible; show a clear empty preview state instead of hiding them.
- Open DWG files through Windows default application from Launcher.
- Pairing must normalize project codes, separators, Cyrillic text, and service prefixes.
- Pairing must prefer missing a doubtful pair over connecting files from different sections.
- Explicit `Часть 1` / `Часть 2`, `узел`, and `сечение` conflicts must not be paired.

## Accepted Vortex Word rules

- Use the name `Вортекс` / `Vortex` for the universal preview module.
- Do not build a custom Word viewer.
- Preview `.doc` and `.docx` by converting through Microsoft Word to PDF cache, then use the accepted PDF render pipeline.
- Keep native opening available as `Открыть Word`.
- Treat `.gdoc` as a Google Docs shortcut, not as a local Word document.
- `.gdoc` must be visible in filters/tree and openable, but it should show a no-local-preview placeholder instead of being sent through Microsoft Word.
- Next Vortex target is Excel: `.xls` / `.xlsx`.

## Accepted Vortex Excel rules — 2026-08-13 checkpoint

Excel is a read-only navigation surface, not a second Excel editor.

- Support `.xlsx` / `.xlsm` through an HTML cache per workbook sheet.  Keep
  `.xls` visible and natively openable; add conversion support only after a
  separate compatibility test.
- The large view is the source of truth: it preserves sheet tabs, authored
  column widths, row heights, merges, basic fonts, fills, scrolling, zoom and
  hand panning.
- A workbook card/thumbnail must be a reduced viewport of that exact cached
  HTML sheet.  Never create a second simplified raster/table renderer for
  Excel thumbnails.  Separate renderers caused wrong text baselines, clipped
  rows and a mismatch between card and large view.
- Build the first selected sheet synchronously; prepare remaining sheets in
  the background, one at a time.  A cached sheet request must not reopen the
  workbook merely to rediscover its title.
- Do not show technical notices inside a worksheet canvas.  Show the complete
  workbook file name in the Launcher chrome above its sheet tabs.  Card labels
  must not use ellipses: wrap or allow horizontal reading of the full name.
- Before declaring Excel work accepted, run: Python compile, JS syntax check,
  `scripts/check_encoding.cmd`, then real browser QA with several ordinary
  workbooks, including one multi-sheet file.  Do not generalize from damaged
  or unusually large workbooks that Office itself struggles to open.

## Accepted Excel tab rule

- Excel sheet tabs are ordinary HTML buttons. Keep the proven rounded-button
  implementation with immediate active-state feedback.
- Do not reintroduce experimental tab shapes, overlapping tabs, SVG tab
  backgrounds, or pseudo-element browser-cap effects: they caused visual
  artefacts and delayed active-state feedback.

## Accepted viewer control and layer rules — 2026-08-13 checkpoint

- The bottom viewer panel is one shared control set for PDF, DWG previews,
  Word previews, and Excel sheets.  It must retain zoom, `Вписать`, rotate,
  hand/arrow, and the three viewing modes.  Do not make a reduced Excel or
  Word variant.
- The same panel must show a native-open action whenever an original file is
  available: `Открыть PDF`, `Открыть DWG`, `Открыть Word`, or `Открыть Excel`.
  Do not omit it for PDF/Word merely because their preview uses the PDF stage.
- `Вписать` must always have enough fixed width for its full Russian label;
  it must never be clipped or wrapped because another format has a different
  panel layout.
- Excel HTML is an overlay layer.  Its semantic `hidden` state must map to
  `display: none`; otherwise an inactive Excel iframe can cover a correctly
  rendered PDF, DWG preview, or Word page and make the large image look blank.
- Before changing a shared viewer control or layer, inspect both an Excel
  workbook and a PDF/DWG preview in the real browser.  Do not infer cross-
  format behaviour from one mode alone.

## Office handoff: multi-machine rules (2026-09-15, office PC)

These rules enable task transfer between the office PC, the laptop and
different agents without context loss. They supplement (never override)
the product rules above.

### 1. Purpose of the Launcher

Fast visual triage of project documents: open an object folder, skim the
tree, preview PDF / Word / Excel / images / DWG-via-PDF-pairs, open the
original in its native application. It is a viewing shell, not a CAD,
Office, DMS or AI-chat replacement.

### 2. Three interface zones (see `app/frontend/index.html`)

1. Left sidebar (`#sidebar`): object list (`#objectListState`) and file
   tree with search + format filters (`#treeState`, `#objectTree`).
2. Center viewer (`#pdfViewer` / `#pdfStage`): large page/sheet view,
   including the Excel overlay (`#excelViewer`).
3. Bottom strip: thumbnail ribbon (`#pdfThumbs`), shared viewer controls
   (`#viewerControls`) and the operation progress panel (`#progressPanel`).

### 3. Address and ports

- The only allowed application address is `http://127.0.0.1:8780/`
  (backend default `--port 8780`, see `app/backend/server.py`).
- Never use port 8000 for checking this project.

### 4. Sources of truth

- GitHub (`f-engineering-spb/f-engineering-launcher`) is the only source
  of code and commit history. Working branch: `dvg-main`.
- The local copy on SSD (e.g.
  `C:\Users\u301\Documents\Codex\f-engineering-launcher`) is the only
  working copy of the code.
- Google Drive `E:\Общие диски\021_F-Engineering_Knowledge_Library\09_Launcher`
  is a library/archive: documents, tasks, reports, artefacts. It is NOT
  a Git repository — never `git init` inside `E:` and never hand-copy
  code between `E:` and the local repo when GitHub can provide it.

### 5. Live data protection

- Do NOT touch live data on `H:` / `E:` on your own initiative (no scan,
  import, move, rename, delete of real object folders).
- Test fixtures live only locally (e.g. `C:\tmp\launcher_check_src`);
  real DWG/object folders are opened only on explicit instruction.

### 6. Heavy CAD ban (default)

- Do NOT run heavy DWG conversion or AutoCAD (daemon, oneshot, model
  space renders) without a separate explicit permission — every
  conversion opens AutoCAD on the user's machine.
- Lightweight checks (PDF, Word, Excel, images, tree, progress panel)
  need no extra permission.

### 7. Mandatory verification and reporting

- After every meaningful change run a local smoke test on
  `http://127.0.0.1:8780/` and record the result.
- Assignments follow `docs/TASK_TEMPLATE.md`; every session ends with a
  report in the shape of `docs/REPORT_TEMPLATE.md` (final message only,
  no intermediate questions).

### 8. Do not distract the user

- Never ask the user to run git commands, copy files, hunt processes or
  open a console. Do everything checkable yourself on the machine.
- Ask the user only for decisions you cannot resolve by inspection
  (credentials, live-data access, heavy CAD runs, product direction).
- Frontend edits require F5 in the browser (stale JS trap); backend
  Russian text requires `scripts/check_encoding.cmd` before/after.

### 9. Forbidden by default

- No health-check endpoints polling schemes, no cron/schedule tasks, no
  auto-sync and no background monitors unless a separate decision
  explicitly allows them.

### 10. Clean baseline freeze (2026-09-17, branch `review/v3.3-updates`)

- Before touching UI or key routes, read the docs: base flow is
  `docs/LAUNCHER_BASELINE_WORKFLOW.md`, the Load button is a frozen
  contract in `docs/LOAD_BUTTON_CONTRACT.md`.
- Without an explicit user order it is forbidden to: change main-button
  behaviour, add dialogs / built-in explorers / file browsers, replace
  system Windows dialogs with custom UI, "improve" the working flow, or
  resurrect previously removed mechanisms (`choose_folder.*`,
  `/api/browse`, `browse_filesystem()`, legacy COM openers,
  `/api/open-explorer`).
- A feature not described in the base flow is not assumed needed: ask
  or propose it separately first.
- DWG work must not break: object loading, file tree, ribbon + viewer,
  native operations, the Load button. Keep DWG changes in small
  separate commits.

### 11. Sole current baseline (dvg-main)

ЕДИНСТВЕННАЯ АКТУАЛЬНАЯ БАЗА

Единственная актуальная ветка проекта — dvg-main.

Работать нужно только из текущего репозитория и только после:

git switch dvg-main

История до текущего состояния намеренно не используется.
Старые ветки, теги, коммиты, архивы и внешние копии не являются источниками кода.
Не искать и не восстанавливать прежние версии.
Не сравнивать текущий код со старыми версиями.
Не использовать _BACKUP как рабочую базу.

Внешняя папка _BACKUP не является актуальной рабочей базой.
Единственная актуальная база — ветка dvg-main текущего репозитория.
Старые локальные копии и архивы запрещено использовать без прямого указания пользователя.

Актуальная рабочая папка — `C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3_CURRENT_COPY`.
Папку `FEngineering_Launcher_v3_OLD_DO_NOT_USE` не использовать.
Старые Git-истории не искать, старые версии не восстанавливать.
Единственная база — текущий HEAD ветки dvg-main.

### 12. Стандарты запуска CLI-агента (agy)

- **Исполняемый файл:** `agy`
- **Команда пакетного запуска:**
  ```powershell
  agy -p "$(Get-Content prompt.txt -Raw)" --dangerously-skip-permissions --mode accept-edits
  ```
- **Рабочая ветка:** `dvg-main`
- **Актуальная рабочая папка:** `C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3_CURRENT_COPY`
- **Запрещённая папка:** `C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3_OLD_DO_NOT_USE`
- **Хелпер запуска:** В корне репозитория создан скрипт `RUN_AGENT.cmd` для удобного запуска CLI-агента со считыванием задачи из `prompt.txt`.

### 13. Стиль коммуникации: Смешанный русско-английский формат (Bilingual Practice & Vocabulary Growth)

> **Статус**: Обязательный стандарт диалога с пользователем (Single Tone of Voice).  
> **Целевой уровень**: B1–B2 (Upper-Intermediate) на базе школьной и инженерной подготовки.  
> **Главная цель**: Поддержание и органичное совершенствование английского языка в процессе работы без потери скорости, ясности и инженерной строгости.

1. **Естественный языковой микс (Natural Code-Switching):**
   - Диалог ведётся на смешанном русско-английском языке. Русский язык служит надёжной смысловой основой, а в речь органично вплетаются английские фразы, деловые обороты, инженерные концепции и идиомы (*idioms & set expressions*).
2. **Обязательная расшифровка и перевод терминов (Zero Ambiguity / Decode & Clarify):**
   - Каждое английское сокращение или технический термин (акроним, аббревиатура: например, *SSOT — Single Source of Truth* / единый источник истины, *WBS — Work Breakdown Structure* / иерархическая структура работ, *DPI — Dots Per Inch* / точек на дюйм, *GUI — Graphical User Interface* / графический интерфейс, *PR — Pull Request* / запрос на слияние кода) обязательно расшифровывается, переводится и поясняется понятным языком.
3. **Понятный контекстный ввод (Comprehensible Input):**
   - Английские конструкции подбираются так, чтобы смысл был прозрачен из окружающего русского контекста либо сразу сопровождался кратким переводом/синонимом в скобках.
   - Использовать реальные фразы из инженерной и IT-практики (*under the hood* — «под капотом / как устроено внутри», *best practices* — «лучшие практики», *trade-off* — «компромисс / баланс плюсов и минусов», *step by step* — «шаг за шагом», *heads-up* — «предупреждение / полезно иметь в виду»).
4. **Тактичность и комфорт (No Snobbery):**
   - Языковые вставки не должны превращаться в словесную перегрузку или снобизм. Это дружелюбный, живой и полезный формат взаимной работы (*collaborative and supportive communication*).

### 14. Регламент многооконного режима (Multi-Window Architecture & Process Coordination)

> **Статус**: Действующий стандарт одновременного сравнения чертежей.

1. **Единый бэкенд-демон (*Single Shared Backend Daemon*):**
   - Все окна лаунчера работают исключительно через канонический порт `8780`. Запрещено создавать новые серверные процессы на портах 8781, 8782 и т.д.
   - Окна функционируют как лёгкие клиенты к единому серверу с общим дисковым и оперативным кэшем.
2. **Координация жизненного цикла (*Reference Counting & Watchdog*):**
   - Каждое окно отправляет пульс `GET /api/heartbeat?id=...` каждые 5 секунд.
   - Закрытие одного окна проверяет `count_other_active_gui_windows()`. Если другие окна активны — бэкенд на порту 8780 остаётся жить.
   - Закрытие последнего окна выгружает сервер и подчищает дочерние процессы без зависания в памяти.
   - Сторож `server.py` (*idle watchdog*) автоматически выгружает сервер через 15 секунд при нуле активных пульсов.
3. **Бесшовный переход и сравнение чертежей (*Deep Linking*):**
   - Вызов нового окна осуществляется через кнопку `🗗 В новом окне` в панели Окна 3, горячую клавишу `Ctrl+N` (или `Ctrl+Т`) либо пункт контекстного меню `🗗 Открыть в новом окне`.
   - Новое окно мгновенно открывает целевой объект и выбранный чертёж в Окне 3.

### 15. Регламент отображения структуры каталогов (Adaptive Tree Expansion & Folder Icons)

> **Статус**: Обязательный стандарт визуального отображения дерева файлов (Окно 1).

1. **Единый стандарт иконки папок (Folder Icon Standard):**
   - Корневой узел дерева, как и все вложенные папки, ВСЕГДА отображается стандартной жёлтой иконкой папки `FOLDER_ICON_SVG` (`#d89e13`).
   - Категорически запрещено подменять иконку корневой папки на иконку белого листа бумаги или файла.
2. **Адаптивное раскрытие дерева (*Adaptive Tree Expansion*):**
   - Для объектов и папок объёмом **до 150 файлов** (рабочие выборки, разделы фасадов, поэтажные планы) дерево открывается **полностью раскрытым по умолчанию** (*auto-expanded*). Запрещено сворачивать папки в слепые стрелки при небольшом количестве файлов.
   - Для гигантских массивов (>150 файлов) сворачивание сохраняется для оптимизации быстродействия.

### 16. Протокол непрерывной фиксации при эксплуатации на объекте ОД150 (Continuous Tracking & Proactive Evolution)

1. **Фиксация всех изменений (Zero Context Loss):**
   - Все изменения логики, интерфейса, параметров отображения и настроек немедленно фиксируются в Git-репозитории на ветке `main` и отражаются в документации `docs/`.
2. **Проактивная оптимизация под инженерные сценарии (Proactive Evolution):**
   - На основе активной эксплуатации лаунчера на объекте ОД150 (Купчино, 1012 файлов, фасадные витражи и разрезы) агент обязан предлагать технические улучшения для ускорения навигации, сопоставления чертежей и работы со спецификациями.


