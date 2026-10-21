# Задание на аудит: F-Engineering Launcher v3

> Документ-задание для эксперта-проверяющего. Цель — независимая верификация
> всей рабочей версии фронтенда и бэкенда, всех путей и интеграций, и поиск
> дефектов, которые могли остаться после сессии доработок.
>
> Предполагается, что вы эксперт по Python/JS/Windows-интеграциям. Проверяйте
> код руками (чтение), затем, где возможно, — запуском.
>
> **Статус задания:** ФИНАЛЬНОЕ. Версия утверждена и влита в `main`. Прочитайте
> этот файл целиком: разделы §A–§B отмечают, что уже внедрено и проверено,
> чтобы не дублировать проверку, а сосредоточиться на оставшемся и поискать
> неявные дефекты.

---

## 0. Контекст

- **Продукт:** локальный лаунчер для инженеров фасадной компании: подключает
  папку объекта (локальный диск или Google Drive `H:`), показывает дерево
  файлов, фильтрует по форматам, строит превью (PDF/Excel/Word/DWG-пара) и
  открывает исходники в нативных Windows-программах (AutoCAD, Excel, Word,
  ONLYOFFICE, Paint, VLC, 7-Zip, Notepad).
- **Архитектура:** браузер (frontend) ↔ локальный Python HTTP-сервер
  (backend, порт `8780`) ↔ нативные программы и конвертеры.
- **Платформа:** Windows 10/11. Важно: бэкенд — только Windows (PowerShell,
  COM, `.exe`). На Linux он частично работает (PDF-рендер, HTML Excel).

## 1. Что проверять — репозиторий

- **Путь к repo (источник истины):**
  `C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3`
- **GitHub:** `https://github.com/f-engineering-spb/f-engineering-launcher.git`
- **Основная ветка (источник истины):** `main`
  - Сессия доработок влита в `main` через PR #3 (merge-коммит `cbcc2c9`,
    смержен 2026-09-06). Верхний коммит `main` — `cbcc2c9`.
  - Рабочая ветка `agent/viewer-controls-checkpoint` — прежняя, можно
    игнорировать для аудита: она совпадает по содержимому с `main` (плюс
    ничего нового).
- **Роль файлов:**
  - `app/backend/server.py` — Python-сервер (THTTP), основной код.
  - `app/frontend/app.js` — логика фронтенда (дерево, превью, вызовы API).
  - `app/frontend/index.html` — разметка, `styles.css` — стили.
  - `scripts/*.ps1` — конвертеры (Word→PDF, Excel→PDF, XLS→XLSX, DWG-рендер)
    и помощники (choose_folder, check_encoding, package_release).
  - `runtime/manifests/*.json` — манифесты импортированных объектов.
  - `runtime/logs/native-open.jsonl` — журнал каждого `/api/open-file`.
  - `docs/`, `tests/` — документация; тесты почти отсутствуют (см. §8).

## 1a. Что уже внедрено в этой сессии и проверено

Следующие изменения в `main` внедрены и **уже быстро проверены** (синтаксис,
HTTP-статусы). Эксперт может считать их частично проверенными и
сосредоточиться на глубокой корректности, кросс-форматных сценариях и побочных
эффектах:

- Бэкенд:
  - `threading.Lock` (`NATIVE_OPEN_LOG_LOCK`) вокруг записи в `native-open.jsonl`.
  - `Cache-Control: no-cache, no-store, must-revalidate` для HTML/JS/CSS в `serve_static`.
  - Гард `.gsheet` / `.gdoc` / `.gslides` → HTTP 400 с подсказкой.
  - Поле `longPathWarning` (>240 символов) в ответе `/api/open-file`.
  - `.tif` / `.tiff` уже присутствуют в карте расширений изображений.
- Фронтенд:
  - Дедупликация двойного клика (`openFileByPathDeduped` + поля
    `state.lastOpenPath` / `state.lastOpenAt`).
  - Синхронизация выделения с кнопкой «Открыть» (`setActiveNativePath("")`
    при 0 или >1 выделении).
  - `preventDefault()` на кнопке «↗».
  - Функция `showNotice()` для не блокирующих предупреждений.
- Проверки уже выполнены: `node --check app.js` = 0, `python ast.parse` = OK,
  `scripts/check_encoding.cmd` = все OK, HTTP-ответы для `.gsheet` (400) и
  длинного пути (`longPathWarning`) верны.

**Просим проверить эти правки на глубину и побочные эффекты, НЕ перепроверяя
синтаксис/кодировку заново (они уже валидны).**

## 2. Важное замечание про объём дифа

`git diff` относительно начального состояния большой (server.py ~+761,
app.js ~+1033 строк) — это накопленные изменения за всю сессию работы, а не
только финальные правки. Проверяйте **всю текущую версию `main`**, а не только
последний патч.

**Ориентир для аудита:** версия, которую проверяем — это `main` на коммите
`cbcc2c9` (merge PR #3). Если нужно изолировать именно последние правки
сессии, смотрите коммиты цепочки в `main`:
`9ebc8ee → 281d464 → f22558e → 40fcd1f → 6943282 → a0266a7 → cbcc2c9`.

---

## 3. Чек-лист бэкенда (`server.py`)

### 3.1 Карта нативного открытия — `launch_native_file(path)` (≈ стр. 733)
Проверить:
- Каждое расширение (`dwg/dxf`, `xlsx/xls/xlsm/xlsb/csv/ods`, `docx/doc/docm/rtf/dotx/odt`, `pdf`, `png/jpg/jpeg/bmp/webp/gif/ico/tif/tiff`, видео, архивы, текст) → какой `.exe` запускается.
- Все пути к программам **существуют** на текущей машине (проверить `Test-Path`).
- Есть ли `shell=True` где-либо (должно быть **всегда `False`** — списки аргументов).
- Fallback-цепочки: если прямой `.exe` не найден → `os.startfile` → `cmd /c start` (`os.startfile` намеренно обходит мёртвые ассоциации — это ок, но проверить, что он не вызовет фантомный WPS).
- **Расширения должны быть исчерпывающими:** нет ли пропущенных форматов (например `tif/tiff`, `ppt/pptx`, `svg`)? Сравнить с картой расширений в `discover_quick_projects`/`file_extension`.

### 3.2 Гард облачных документов (новое)
Проверить, что в обработчике `/api/open-file` (≈ стр. 1968):
- `.gsheet` / `.gdoc` / `.gslides` → возвращает `400` с подсказкой «облачный документ Google…», а **не** запускает EXE.
- Валидно ли сообщение, попадает ли в лог как `status:error`.

### 3.3 Предупреждение о длинном пути (новое)
Проверить `longPathWarning` в ответе `/api/open-file`:
- Порог `> 240` символов.
- Возвращается `longPathWarning: <текст>` при длинном пути, `null` при коротком.
- Не ломает ли поле нормальный ответ `{ok:true, path, openedPath, mode}`.

### 3.4 Потокобезопасность лога (новое)
Проверить `append_native_open_log` + `NATIVE_OPEN_LOG_LOCK`:
- Реальная ли защита от чередования строк при конкурентных `/api/open-file`.
- `threading` импортирован, `Lock` создан как модульная константа.
- Нет ли других общих файлов-ресурсов без блокировки (например запись манифестов, кэшей).

### 3.5 Кэширование статики (новое)
Проверить `serve_static` (≈ стр. 2046):
- Для HTML/JS/CSS отдаётся `Cache-Control: no-cache, no-store, must-revalidate`.
- `Content-Type` с `charset=utf-8` для text/js.
- Пути к `/cache/` («serve_cache») — защита от path-traversal (`relative_to`).
- Не противоречит ли это `send_cache` для PNG-страниц (там был
  `Cache-Control: private, max-age=31536000, immutable`) — при этом PNG-кэш
  должен остаться долгим, а HTML/JS/CSS — no-store. Проверить, что не
  перепутано.

### 3.6 API-маршруты
Проверить соответствие фронтенд-вызовов и серверных route:
- `GET /api/health`, `/api/objects`, `/api/objects/:id`, `/api/browse`
- `POST /api/objects/import`, `/api/objects/exclude`, `/api/objects/diff`
- `POST /api/open-file`
- `POST /api/pdf/render`, `/api/pdf/page`
- `POST /api/word/render`, `/api/word/page`
- `POST /api/dwg/model-render`, `/api/dwg/model-page`
- `POST /api/excel/workbook`, `/api/excel/sheet`, `/api/excel/render`, `/api/excel/page`
- `POST /api/open-explorer`, `/api/choose-folder`
Для каждого: валидны ли параметры, есть ли обработка ошибок (читается ли JSON,
проверяется `response.ok` на фронте), не падает ли на битых/kecш файлах.

### 3.7 Длинные пути / Windows MAX_PATH
Проверить гипотезу: `H:\Общие диски\...` + длинные шифры легко превышают
260 символов. Что произойдёт при `build_tree`, `pdf_render`, `open-file`?
- Сервер возвращает `400`/понятную ошибку или бросает необработанное
  исключение, роняя поток (запрос, но не сервер)?
- Есть ли смысл проверять `LongPathsEnabled` в реестре и слать предупреждение?

---

## 4. Чек-лист фронтенда (`app.js`)

### 4.1 Функции нативного открытия
- `openFileByPath(path)` — проверяет `response.ok`, обрабатывает
  `longPathWarning` через `showNotice`, вызывает `startProgress/finishProgress`.
- `openFileByPathDeduped(path)` — дедупликация двойного клика (~800 мс).
  Проверить: поле `state.lastOpenPath`/`lastOpenAt` объявлено, дедуп не мешает
  одиночному клику по «↗».
- Кнопка «↗» в строке (`renderTreeNode`): `stopPropagation` + `preventDefault`.
- Обработчики: `els.openNativeFile` (toolbar), двойной клик по строке дерева,
  клик по кнопке в summary (`#summaryOpenBtn`).

### 4.2 Выделение → кнопка «Открыть»
- `selectNode(node, event)`: протестировать Ctrl/Shift-клик, снятие последнего
  выделения, множественное выделение. Кнопка «Открыть» (`#openNativeFile`)
  должна показываться **только** при ровно одном выбранном файле и скрываться
  в остальных случаях (`setActiveNativePath("")`).

### 4.3 Исправленный баг скобок
- Историческая ошибка: в `selectNode` не хватало `}` (весь скрипт не парсился).
  Проверить, что сейчас: `node --check app.js` = 0, скобки сбалансированы.
  Убедиться, что больше нет аналогичных «незакрытых» блоков.

### 4.4 Дерево и фильтры
- `renderTreeNode`, `renderFormats`, `renderTree`, фильтры по расширениям.
- `fileExtensionFromPath`, `getNativeAppLabel` — согласованность меток и карты
  расширений с бэкендом.

### 4.5 Превью
- PDF: `showPdfPage`, `renderPdfViewer`, качество 150/300 DPI.
- Excel: `renderExcelWorkbooks`, `activateExcelSheet`, вкладки, HTML-кэш.
- Word: превью через Word→PDF.
- DWG: превью через PDF-пару + нативное открытие.
- Общий пул контролов (`viewerControls`) — зум/«Вписать»/поворот/рука/режимы.

---

## 5. Интеграции со средой

### 5.1 Реальные программы (проверить пути на этом ПК)
```powershell
# Примерные пути — подтвердить существование
C:\Program Files\Autodesk\AutoCAD 2024\acad.exe
C:\Program Files\Microsoft Office\Root\Office16\EXCEL.EXE
C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE
C:\Program Files\ONLYOFFICE\DesktopEditors\DesktopEditors.exe
C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe
C:\Program Files\Google\Chrome\Application\chrome.exe
C:\Program Files\VideoLAN\VLC\vlc.exe
C:\Program Files\7-Zip\7zFM.exe
C:\Program Files (x86)\WinRAR\WinRAR.exe
%LOCALAPPDATA%\Microsoft\WindowsApps\mspaint.exe
```
- Если программа установлена не по этим путям (например Office15/Office19,
  AutoCAD 2025) — отметить расхождение.

### 5.2 Реестр: «мёртвые» ассоциации WPS
Проверить `HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\<ext>\UserChoice`:
- `.xlsx` → `ET.Xlsx.6`, `.png/.jpg` → `WPS.PIC.*` (следы удалённого WPS).
- Убедиться, что лаунчер обходит их (прямой EXE), но проводник — нет.
- Это объясняет симптом: старый `app.js` через `os.startfile` открывал
  только `.jpg` (целая ассоциация), а `.png/.pdf/.docx/.xlsx` — нет.

### 5.3 Poppler
- `pdfinfo`/`pdftoppm` ищутся сначала в `runtime/tools/poppler/Library/bin`,
  затем в codex-кэше, затем в PATH. Проверить наличие, что PDF-превью
  реально рендерится.

### 5.4 Защищённый просмотр Office на `H:`
- Файлы с Google Drive `H:` могут открываться Office в режиме Protected View
  (только чтение). Это штатное поведение, не баг — подтвердить вывод.

---

## 6. Сценарии ручного тестирования (в браузере)

Сервер: `.\scripts\start_windows.cmd` → `http://127.0.0.1:8780/`.

1. **Импорт объекта:** «Загрузить» → выбрать папку → дерево появляется.
2. **PDF:** клик по `.pdf` → превью страницы (pthumbs + большой вид).
3. **Excel (.xlsx):** превью листов, переключение вкладок.
4. **Word (.doc/.docx):** превью после конвертации Word→PDF.
5. **DWG:** превью по PDF-паре или пустое состояние (но НЕ скрыто), открытие
   в AutoCAD.
6. **Нативное открытие** всех форматов: кнопка в тулбаре, «↗» в строке,
   двойной клик. Убедиться, что **файл открывается ровно один раз** (дедуп
   работает).
7. **Моно-выделение:** при 1 файле — кнопка «Открыть» активна; при 0 или >1 —
   скрыта.
8. **`.gsheet`/`.gdoc`:** ожидает `400` + понятное сообщение (не запуск EXE).
9. **Ошибки:** битый PDF → понятная ошибка, интерфейс не «успех».

---

## 7. Что проверить в скриптах `scripts/`
- `start_windows.ps1`/`.cmd` — UTF-8 окружение, выбор Python, запуск на
  порту 8780.
- `check_encoding.cmd/.ps1/.py` — проверка UTF-8 (важно: кириллица в исходниках).
- `convert_word_to_pdf.ps1`, `convert_excel_to_pdf.ps1`,
  `convert_xls_to_xlsx.ps1` — COM-конвертация; есть ли таймауты, падает ли на
  модальном окне (защищённый просмотр).
- `render_dwg_model_space.ps1` — рендер DWG через AutoCAD.
- `package_release.ps1` — упаковка портативного архива (исключает кэши/логи,
  включает Poppler).
- `choose_folder.py/ps1` — системный диалог выбора папки.

---

## 8. Тесты
- `tests/README.md` есть, но **реальных автотестов почти нет**.
- Проверить: `python -m py_compile app/backend/server.py` (синтаксис),
  `node --check app/frontend/app.js` (синтаксис),
  `.\scripts\check_encoding.cmd` (кодировка).
- Перечислить, каких test-покрытий не хватает (unit для `diff_trees`,
  `file_cache_key`, `launch_native_file`; e2e для импорта/рендера).

---

## 9. Известные риски / открытые вопросы (проверить, подтвердить или опровергнуть)

1. **`AllowSetForegroundWindow(0xFFFFFFFF)`** из фонового Python — считается
   no-op. Работает «по удаче» (Office/AutoCAD сами забирают фокус). Стоит ли
   строгое решение (suspended-режим + `ASFW(pid)`)? Оценить необходимость.
2. **`ThreadingHTTPServer`** — поток на запрос. ОК для localhost, но при
   долгих рендерах (Word/Excel/DWG COM) много одновременных запросов могу
   генерировать множество потоков. Есть ли риск исчерпания ресурсов.
3. **Windows MAX_PATH** — актуален ли `LongPathsEnabled`? Нужно ли
   предупреждение в UI уже на этапе дерева (не только при открытии).
4. **Безопасность:** `serve_cache`/`serve_static` — проверить traversal;
   `read_json` — корректный парсинг; экранирование HTML в UI.
5. **Кириллица:** везде ли UTF-8 для текста/путей/JSON/пр.

---

## 10. Формат отчёта

Выдать:
- **Вердикт по каждому пункту чек-листа:** `OK` / `⚠️ риск` / `❌ дефект` /
  `N/A`, с кратким обоснованием и номером строки/файла.
- **Список найденных дефектов** (критичность: критический/высокий/средний/низкий)
  с рекомендацией правки.
- **Раздел «с чем не согласен»** относительно предполагаемых решений из №9, 3.7.
- **Итоговую резолюцию:** можно ли принимать в работу текущую версию.

---

## 11. Контекст развёртывания (после аудита)

Версия `main` (коммит `cbcc2c9`) является целевой для:

1. **Портативный архив Windows** — собирается через
   `scripts/package_release.ps1` в `dist/FEngineering_Launcher_v3-portable-*.zip`,
   затем раскладывается в `H:\Общие диски\021_F-Engineering_Knowledge_Library\09_Launcher\`.
2. **Демо-витрина на VPS** — `94.183.188.151:8780` (тот же сервер, что
   `ferospb.info`), Linux. Там нативное открытие не работает (Windows-программ
   нет), но PDF-превью (Poppler в PATH) и HTML-Excel (openpyxl) работают.
3. **Предупреждение для аудита:** сервер на VPS развёрнут в `/opt/launcher`
   из предыдущей версии кода; правки этой сессии туда **ещё не доехали** —
   если аудит подтвердит версию, надо синхронизировать `/opt/launcher` с
   `main`.

Если после аудита версия одобрена — рекомендую обновить VPS-витрину и
переcобрать портативный архив из `main`, чтобы везде была одна утверждённая
версия.

