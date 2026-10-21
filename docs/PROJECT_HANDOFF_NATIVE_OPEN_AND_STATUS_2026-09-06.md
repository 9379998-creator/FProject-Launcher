# F-Engineering Launcher v3 — Подробная передача проекта и план решения по нативным программам

**Дата:** 06.09.2026  
**Версия:** 0.4.0-v3-pdf-render  
**Текущий порт сервера:** `http://127.0.0.1:8780/`  
**Статус:** Базовые просмотрщики (PDF, HTML-Excel, Word, DWG, картинки) работают. Проводится отладка и стабилизация механизма открытия исходных файлов в нативных программах (DWG, PDF, Word, Excel, графические файлы, архивы).

---

## 1. Назначение и концепция продукта

Launcher v3 — специализированный визуальный лаунчер для проектировщиков и инженеров. Его задача:
1. **Быстрая загрузка и обзор** больших древовидных структур файлов проектной документации (объектов строительства).
2. **Мгновенный визуальный предпросмотр** чертежей, сканов, таблиц и документов (карточки / миниатюры $\rightarrow$ большой просмотрщик) без необходимости запускать тяжёлые приложения для сотен файлов.
3. **Надежное открытие исходного файла в нативной программе** (AutoCAD, Excel, Word, ONLYOFFICE, Paint, VLC и др.) в один клик прямо из дерева или из панели просмотра.
4. **Безопасная работа с корпоративными сетевыми дисками** (Google Drive `H:\`, сетевые папки) без зависаний, с кэшированием и фильтрацией временных файлов (`~$*`, `.~*`).

---

## 2. Карта репозитория, расположение файлов и запуск

### Основные директории и файлы
- **Корневая директория проекта:**
  ```text
  C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3
  ```
- **Исходный код:**
  - `app/backend/server.py` — локальный HTTP API сервер (чистый Python, `ThreadingHTTPServer`).
  - `app/frontend/index.html` — разметка single-page приложения.
  - `app/frontend/app.js` — логика фронтенда, дерево, зум/панорама, вызовы API.
  - `app/frontend/styles.css` — стили интерфейса, темная/светлая тема, адаптивность.
- **Скрипты автоматизации и конвертации (`scripts/`):**
  - `scripts/start_windows.cmd` — **главный и единственный способ запуска сервера** (настраивает UTF-8, находит свободный порт, запускает `server.py`).
  - `scripts/convert_excel_to_pdf.ps1` — конвертер Excel в PDF через COM.
  - `scripts/convert_word_to_pdf.ps1` — конвертер Word в PDF через COM.
  - `scripts/convert_xls_to_xlsx.ps1` — конвертер устаревших XLS в XLSX.
  - `scripts/render_dwg_model_space.ps1` — рендерер пространства модели DWG через AutoCAD COM.
- **Локальный runtime (`runtime/`) — не коммитится:**
  - `runtime/manifests/*.json` — сохранённые деревья загруженных объектов.
  - `runtime/cache/` — кэшированные превью: `pdf/`, `excel/html/`, `word/`, `dwg/`.
  - `runtime/logs/native-open.jsonl` — журнал каждого запроса на открытие файлов с таймингами и ошибками.
- **Внешние диски и пути к данным:**
  - `H:\` — виртуальный диск **Google Drive** (`H:\Общие диски\...`, например `000_Объекты СПб`, `007_Коммерческий отдел`, `022_F-Engineering`). Файлы `.gsheet` и `.gdoc` на нём являются облачными ссылками.
  - `C:\Users\a9379\Downloads\` — локальная папка загрузок.

### Подтвержденные установленные программы на машине пользователя
1. **DWG / DXF:** AutoCAD (путь задаётся в настройках лаунчера, параметр `settingDwgExe`).
2. **Excel (.xlsx, .xls, .xlsm, .csv):** `C:\Program Files\Microsoft Office\Root\Office16\EXCEL.EXE`.
3. **Word (.docx, .doc, .rtf):** `C:\Program Files\Microsoft Office\Root\Office16\WINWORD.EXE`.
4. **PDF:** `C:\Program Files\ONLYOFFICE\DesktopEditors\DesktopEditors.exe` и `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
5. **Изображения (.png, .jpg, .jpeg, .bmp, .webp, .ico):** `C:\Users\a9379\AppData\Local\Microsoft\WindowsApps\mspaint.exe` (современный Paint).
6. **Видео / Аудио:** `C:\Program Files\VideoLAN\VLC\vlc.exe`.
7. **Архивы:** `C:\Program Files\7-Zip\7zFM.exe` и `C:\Program Files (x86)\WinRAR\WinRAR.exe`.
8. **Текст / Код:** `C:\Windows\system32\notepad.exe`.

---

## 3. Что уже сделано в проекте (хронология и результаты)

1. **Модальное окно загрузки папок / объектов:**
   - Вкладка «Быстрый доступ» (пресеты дисков C:, H:, Downloads).
   - Вкладка «Обзор» — встроенный проводник по файловой системе через `/api/browse`.
   - Вкладка «Ввод пути» — ручной ввод любого сетевого пути или Drag-and-Drop.
   - Системный выбор папки Windows (`/api/choose-folder`).
2. **Фильтрация временных lock-файлов Office:**
   - Все файлы `~$*` и `.~*` отфильтрованы в сканере `server.py` (`build_tree`, `browse_filesystem`, `is_excel_file`, `is_word_file`) и удалены из манифестов.
3. **HTML-просмотрщик Excel:**
   - Быстрый просмотр всех листов без запуска Excel через `openpyxl` $\rightarrow$ HTML-кэш.
   - Поддержка вкладок листов, форматирования ячеек, зума, поворота и режима fit.
4. **Рендеринг PDF и чертежей:**
   - Двухуровневый кэш: 150 DPI для быстрого каталога/миниатюр, 300 DPI по требованию.
   - Просмотрщик с панорамированием («рука»), зумом колесиком мыши и кнопками, поворотом на 90°.
5. **Дифференциальная синхронизация:**
   - Отслеживание изменений в папках объектов через `/api/objects/diff`.

---

## 4. Глубокий разбор проблемы: почему кнопки открытия нативных программ не срабатывали

Пользователь сообщил:
> *«кнопки последние которые должны были открывать нативные программы сейчас не работают нужно исправить эту ситуацию»*

### А. В интерфейсе есть три точки вызова нативных программ
1. **Центральная кнопка в тулбаре просмотрщика (`#openNativeFile`):**
   - Находится в блоке `#viewerControls`.
   - Текст: **«Открыть»**, подсказка: *«Открыть исходный файл в [Программа] ([Путь])»*.
   - Обработчик в `app.js`:
     ```javascript
     els.openNativeFile.addEventListener("click", () => {
       openActiveNativeFile().catch(showOperationError);
     });
     ```
2. **Кнопка «↗» в строке дерева файлов (`.open-native-row-button`):**
   - Генерируется для каждого файла в `renderTreeNode`.
   - Обработчик:
     ```javascript
     openButton.addEventListener("click", (event) => {
       event.stopPropagation();
       openFileByPath(node.path).catch(showOperationError);
     });
     ```
3. **Двойной клик по строке дерева (`row.addEventListener("dblclick", ...)`):**
   - Вызывает `openFileByPath(node.path)`.

### Б. Системные причины сбоев в Windows (диагностированные в реестре)
1. **Сломанные ассоциации WPS Office:**
   - На машине пользователя ранее был установлен Kingsoft WPS Office, затем удалён.
   - В реестре Windows (`HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\...`) остались ключи `UserChoice`:
     - `.png` $\rightarrow$ ссылался на несуществующий `photolaunch.exe` (ошибка `WinError -2147221003`).
     - `.xlsx` $\rightarrow$ ссылался на `ET.Xlsx.6` (WPS Spreadsheets).
     - `.doc` $\rightarrow$ ссылался на `WPS.Doc.6` (WPS Writer).
   - Вызов `os.startfile(...)` в Python делегирует открытие Windows Shell, который натыкался на мёртвые записи WPS Office и молча ничего не открывал!
2. **Файлы на виртуальном диске Google Drive (`H:\`):**
   - При вызове через промежуточные скрипты пути с пробелами и кириллицей на диске `H:` требовали точной передачи аргументов и рабочей директории (`cwd`).
3. **Зависания PowerShell COM:**
   - Старые скрипты `open_word_native.ps1`, `open_excel_native.ps1`, `open_dwg_review_copy.ps1` использовали `New-Object -ComObject` или `Marshal]::GetActiveObject`. Если приложение показывало модальное окно (например, предупреждение о защищенном виде для файла из интернета), COM блокировался и скрипт падал по 60-секундному таймауту.

### В. Почему кнопки могут не реагировать прямо сейчас у пользователя
Следующему агенту необходимо проверить следующие сценарии:
1. **Кэширование браузером файлов `app.js` и `styles.css`:**
   - Пользователь загружает интерфейс из кэша браузера, где старая версия `app.js` ещё не содержит новых обработчиков.
   - **Решение:** Добавить к подключению скриптов версионирование (`app.js?v=...`), либо попросить пользователя нажать `Ctrl + F5`.
2. **Кнопка `#openNativeFile` скрыта (`hidden`), пока не выбран предпросмотр:**
   - В `app.js`:
     ```javascript
     function setActiveNativePath(path) {
       state.activeNativePath = path || "";
       els.openNativeFile.hidden = !state.activeNativePath;
       ...
     }
     ```
   - Функция `setActiveNativePath` вызывается **только** внутри `showPdfPage` и `renderExcelWorkbooks`, то есть после нажатия кнопки «Отобразить»!
   - Если пользователь просто кликнул по строке в дереве, но не нажал «Отобразить», центральная кнопка «Открыть» остаётся скрытой (`hidden`)!
   - **Решение:** При одиночном клике в дереве (`selectNode`) также вызывать `setActiveNativePath(singleSelectedNode.path)`, чтобы кнопка «Открыть» активировалась сразу при выделении файла.
3. **Поведение кнопки «↗» и двойного клика в дереве:**
   - Проверить в консоли браузера (DevTools F12), отправляется ли `fetch("/api/open-file", ...)` при клике на «↗» и двойном клике.
   - Добавить явное логирование в консоль: `console.log("[Launcher] Opening native file:", path)`.
4. **Контекст запуска Windows:**
   - Убедиться, что `server.py` запущен в интерактивной сессии пользователя (Session 1 Console), а не как изолированная служба, чтобы запущенные процессы `EXCEL.EXE`, `WINWORD.EXE`, `acad.exe` отображали свои окна на экране.

---

## 5. Что реализовано в бэкенде: диспетчер `launch_native_file`

В `app/backend/server.py` реализован прямой запуск:
```python
def launch_native_file(path: Path) -> str:
    # 1. DWG -> AutoCAD (путь из настроек, параметр settingDwgExe)
    # 2. XLSX / XLS -> EXCEL.EXE (путь из настроек)
    # 3. DOCX / DOC -> WINWORD.EXE (путь из настроек)
    # 4. Остальное -> путь из настроек или Проводник Windows
    # Fallback -> Проводник Windows
```

Тестирование через HTTP POST `/api/open-file`:
- `DWG` $\rightarrow$ `HTTP 200 (mode: custom-app:acad.exe)`
- `XLS` $\rightarrow$ `HTTP 200 (mode: excel-direct:EXCEL.EXE)`
- `XLSX` $\rightarrow$ `HTTP 200 (mode: excel-direct:EXCEL.EXE)`
- `DOCX` $\rightarrow$ `HTTP 200 (mode: word-direct:WINWORD.EXE)`
- `PDF` $\rightarrow$ `HTTP 200 (mode: pdf-direct:DesktopEditors.exe)`
- `PNG` $\rightarrow$ `HTTP 200 (mode: paint-direct:mspaint.exe)`

Журнал пишется в `runtime/logs/native-open.jsonl`.

---

## 6. Чеклист и инструкция для следующего агента

1. **Сервер:**
   - Сервер запущен на порту `8780`: `http://127.0.0.1:8780/api/health`.
   - Запуск осуществляется исключительно через `scripts\start_windows.cmd`.
2. **Кэширование фронтенда (ВНЕДРЕНО):**
   - В `index.html` применен `?v=20260906-native-fix-04`.
   - Если пользователь открыл окно ранее, напомнить нажать `Ctrl + F5`.
3. **Кнопка «Открыть» активна сразу при клике на файл в дереве (ВНЕДРЕНО):**
   - В `selectNode` добавлен автоматический вызов `setActiveNativePath(selectedItem.path)` при одиночном выборе файла. Кнопка «Открыть» теперь не требует предварительного нажатия «Отобразить».
4. **Обратная связь и логирование (ВНЕДРЕНО):**
   - В `openFileByPath(path)` выводится статус: `Открытие в [Программа]` $\rightarrow$ `Файл открыт: [Программа]`.
   - Добавлено логирование `console.log("[Launcher] Opening in...")`.
5. **Проверка в реальном браузере:**
   - Открыть `http://127.0.0.1:8780/`.
   - Кликнуть на любой файл в дереве (DWG, XLS, XLSX, DOCX, PDF, PNG) $\rightarrow$ центральная кнопка «Открыть» становится активной с корректным названием программы $\rightarrow$ клик запускает файл.
   - Кликнуть на иконку «↗» в строке дерева $\rightarrow$ запускает файл в программе.
   - Двойной клик по строке файла $\rightarrow$ запускает файл в программе.
