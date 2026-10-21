# F.E.R.O. Launcher v4 — Полная сводка проекта и передача эстафеты (Handover Summary)

**Дата фиксации:** 16 октября 2026 г.  
**Текущая активная ветка:** `main` (рабочая копия чистая, синхронизирована с `origin/main`).  
**Стабильный тег чекпоинта:** `v4.1.0-checkpoint-stable` (коммит `4112c55`).  
**Назначение документа:** Служит полным, исчерпывающим контекстом для нового агента или разработчика. Позволяет сразу продолжить разработку без повторного объяснения предыстории, архитектуры и ранее решённых проблем.

---

## 1. Инфраструктура, пути и окружение (Paths & Environment)

### Основные пути на диске:
* **Корень репозитория:**  
  `C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4`
* **Удаленный репозиторий GitHub:**  
  `https://github.com/9379998-creator/fero-launcher-v4.git`
* **База данных SQLite (WAL-режим):**  
  `C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4\runtime\db\launcher.sqlite`
* **Кэш рендеринга миниатюр и векторных страниц DWG/PDF:**  
  `C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4\runtime\cache\`
* **Руководство пользователя и документация F.E.R.O. Launcher:**  
  `C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4\docs\f_engineering_launcher_guide.html`

### Эталонный референсный кейс (Golden Standard Project):
* **Папка с объектом на общем диске:**  
  `g:\Общие диски\011_Производство\ФЕРО\Заказчики\ГК Эколайн\БЦ на Энгельса\DWG AP`
* **Ключевые эталонные файлы в папке:**
  1. `Ведомость_объемов_работ_фасады_БЦ_Энгельса.csv` — коммерческая ведомость объемов работ, разделенная на разделы I–IV (Светопрозрачные конструкции, Навесной вентилируемый фасад, Двери и входные группы, Кровельные примыкания и ограждения). Содержит единичные расценки на материалы без НДС, на монтаж/СМР без НДС, НДС 22%, итоговые суммы и средние показатели на 1 м² фасада под ключ.
  2. `Паспорт_и_спецификация_фасадов_БЦ_Энгельса.html` — интерактивный Apple-style дашборд-паспорт объекта:
     - Вкладка рендеров фасадов (Фасады 1-8, 8-1, Л-А, А-Л, узлы);
     - Таблица сверки объемов: Векторный PDF vs CADCraft DWG Hatch (сходимость 97.1%, технологическая дельта +3%, 100% совпадение штучных элементов);
     - Матрица площадей материалов по ориентациям фасадов с процентным долевым распределением;
     - Коммерческая ведомость СМР с живым калькулятором (директивные расценки 85 / 87.5 / 90 тыс. ₽/м², очистка, печать, экспорт в Excel);
     - Конструктивные пироги наружных стен и узлов (Лист 20 АР).
  3. `Фасады_БЦ_Энгельса_2_листа_А1.pdf` — результирующий двухстраничный графический отчет А1.
  4. Исходные файлы `*.dwg` (планы этажей с отметками, фасады в осях, разрезы 1-1, 2-2, 3-3).

### Системное окружение и ПО:
* **ОС:** Windows 11 / Windows Server (PowerShell).  
  *Критически важное правило:* в PowerShell перед вызовом команд git необходимо обязательно указывать:  
  `$env:GIT_CONFIG_GLOBAL="NUL"; git <команда>`
* **Python:** Python 3.14 (установлены библиотеки `PyMuPDF` (`fitz`), `openpyxl`, `beautifulsoup4`, `pywin32`, `fastapi`, `uvicorn`).
* **AutoCAD 2025:**
  - Системный лаунчер открытия: `C:\Program Files\Common Files\Autodesk Shared\AcShellEx\AcLauncher.exe`
  - Основной бинарник: `C:\Program Files\Autodesk\AutoCAD 2025\acad.exe`
* **Сервер Launcher:**
  - Локальный порт: `http://localhost:8000` (или `8789` через `Запуск_Нового_Лаунчера.cmd`)
  - Запуск: `python app/backend/server.py`

---

## 2. История решённых проблем и текущее состояние системы

До настоящего момента была проведена масштабная работа по стабилизации ядра и пользовательского интерфейса:

### 1. Устранение проблемы двойного запуска AutoCAD и зависаний
* **Симптом:** При открытии DWG из Окна №2 или Окна №3 запускались два экземпляра `acad.exe` («два красных окна»), выскакивало окно «Внешние ссылки», либо происходило зависание.
* **Причина:**
  1. Фоновый скрипт парсинга создавал скрытый COM-интерфейс `AutoCAD.Application`, который перехватывал регистрацию и конфликтовал с пользовательским процессом.
  2. Запуск выполнялся напрямую через `acad.exe` без ключей MDI/SDI, что заставляло AutoCAD открывать каждый файл в абсолютно новом процессе.
* **Решение:**
  - Фоновый COM-запуск был изолирован.
  - Нативное открытие переведено на официальный системный `AcLauncher.exe` с аргументом `/O`:
    ```python
    subprocess.Popen([ac_launcher, "/O", file_path], creationflags=subprocess.DETACHED_PROCESS)
    ```
    Это обеспечивает открытие чертежа строго в единственном запущенном экземпляре AutoCAD без блокировки лаунчера и без всплывающих черных окон командной строки.

### 2. Строгий порядок ленты миниатюр (Окно №2) в соответствии с деревом (Окно №1)
* **Симптом:** При стриминговом асинхронном рендеринге DWG/PDF миниатюры отображались по мере завершения потоков, из-за чего порядок карточек в ленте произвольно перемешивался, а при прокрутке дерева фокус скакал вверх и вниз.
* **Решение:**
  - В `app/frontend/app.js` внедрена система фиксированных виртуальных слотов.
  - Позиция каждой миниатюры строго привязана к исходному индексу файла в отфильтрованном списке дерева каталога.
  - Реализован плавный двусторонний скроллинг: выбор файла в дереве мягко центрирует соответствующую миниатюру в ленте.

### 3. Исправление нативного открытия и превью всех медиаформатов
* Исправлена ошибка `UnboundLocalError` при обработке системных путей в `server.py`.
* Подавлены всплывающие окна терминала (`cmd.exe`) за счет использования флагов `CREATE_NO_WINDOW` / `DETACHED_PROCESS`.
* Обеспечен полноценный просмотр и открытие по правому клику для всех форматов:
  - Документы: `.pdf`, `.dwg`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.txt`;
  - Графика: `.jpg`, `.jpeg`, `.png`, `.gif`, `.tif`, `.tiff`;
  - Видео: `.mov`, `.mp4`.

### 4. Навигация и эргономика клавиши Escape
* **Окно №1 (Дерево объектов):** кнопка «Назад» активна только при погружении во вложенные папки дерева.
* **Окно №2 (Лента миниатюр):** активна лента и навигация.
* **Окно №3 (Полноэкранный просмотрщик):** кнопка «Назад» возвращает в ленту миниатюр; кнопка выбора объекта намеренно деактивирована для исключения случайного зависания фокуса.
* **Клавиша `Escape`:** универсальный возврат:
  - Из Окна №3 $\to$ в Окно №2 (миниатюры);
  - Из Окна №2 $\to$ в Окно №1 (дерево папок);
  - Из Окна №1 $\to$ к списку всех объектов лаунчера.

### 5. Состояние Git-репозитория:
* **Активная ветка:** только `main`.
* **Все предыдущие ветки разработки заархивированы в виде тегов:**
  - `archive/feat-dwg-on-demand`
  - `archive/feat-dwg-to-pdf`
  - `archive/feat-dwg-audit-v4`
  - `archive/feat-pdf-html-viewer`
  - `archive/feat-word-html-viewer`
  - `archive/feature-large-pdf-lazy-viewing`
  - `archive/fix-dwg-cache-and-layout-correctness`
  - `archive/fix-file-count-consistency`
  - `archive/fix-pdf-viewer-reference`
  - `archive/old-main-20261006`
* **Контрольные чекпоинты:**
  - `v4.0.0-baseline` — чистая эталонная база.
  - `v4.1.0-checkpoint-stable` — полностью стабилизированный просмотрщик DWG/PDF/Office с единым инстансом AutoCAD и синхронизированной лентой.

---

## 3. Новая задача: База данных, расчет объемов и первоначальный бюджет

### Бизнес-логика и сценарий использования:
1. **На старте:** Пользователь загружает через лаунчер сырую папку с чертежами DWG (например, `БЦ на Энгельса\DWG AP`). В папке **нет** готовых PDF и смет.
2. **Шаг 1. Конвертация и рендеринг:**
   Лаунчер преобразует листы и модели DWG в качественный векторный PDF (через CadCraft / AutoCAD AcPlot).
3. **Шаг 2. Двойное извлечение объемов (Dual Extraction):**
   - **DWG CAD:** Извлечение полилиний и штриховок (`AcDbHatch`) по слоям (остекление СПД, стемалит, подсистема, фибробетон, кассеты, двери, примыкания, створки).
   - **Векторный PDF:** Извлечение векторных полигонов через PyMuPDF (`fitz`), расчет площадей через формулу Гаусса (Shoelace) с калибровкой масштаба.
4. **Шаг 3. Сверка и перекрестный контроль (Reconciliation):**
   - Сопоставление площадей по каждому конструктивному элементу.
   - Расчет дельты ($\Delta$) и коэффициента сходимости. Как показал эталонный кейс, сходимость 97.1% идеальна для фасадов, так как DWG учитывает нахлесты под парапеты и узлы примыканий.
   - Определение согласованного (принятого) объема.
5. **Шаг 4. Расчет сметы по базе единичных расценок:**
   - Каждой позиции сопоставляются:
     - Цена материалов без НДС (руб./ед.);
     - Цена СМР / монтажа без НДС (руб./ед.);
   - Добавляется НДС 22%;
   - Вычисляется общая стоимость объекта, доля материалов, доля СМР и средняя цена за 1 м² фасада.
6. **Шаг 5. Формирование первоначального бюджета (Deliverables):**
   - Генерация интерактивного HTML-паспорта фасадов с живым калькулятором;
   - Экспорт ведомости объемов работ в CSV / Excel;
   - Генерация сводного PDF-отчета.

---

## 4. Архитектура схемы данных SQLite (`runtime/db/launcher.sqlite`)

Для реализации задачи в `app/backend/db.py` разворачивается следующая структура:

```sql
-- 1. Объекты (проекты)
CREATE TABLE IF NOT EXISTS roots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    project_name TEXT NOT NULL,
    address TEXT,
    client TEXT,
    total_facade_area_m2 REAL DEFAULT 0.0,
    is_active BOOLEAN NOT NULL DEFAULT 1
);

-- 2. Индексированные документы объекта
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id INTEGER NOT NULL,
    rel_path TEXT NOT NULL,
    name TEXT NOT NULL,
    ext TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime_ns INTEGER NOT NULL,
    facade_orientation TEXT, -- 'Фасад 1-8', 'План 3 этажа' и т.д.
    FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE,
    UNIQUE (root_id, rel_path)
);

-- 3. Извлеченные геометрические элементы из DWG и PDF
CREATE TABLE IF NOT EXISTS parsed_elements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    source_type TEXT NOT NULL, -- 'dwg_hatch', 'dwg_polyline', 'pdf_vector', 'block_ref'
    layer TEXT,
    material_category TEXT NOT NULL, -- 'СПД', 'Стемалит', 'Фибробетон', 'Кассеты', 'Створки'
    raw_value REAL NOT NULL,
    raw_units TEXT NOT NULL,
    area_m2 REAL,
    perimeter_m REAL,
    count INTEGER DEFAULT 1,
    metadata TEXT, -- JSON с дополнительными свойствами
    FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
);

-- 4. Сверка объемов (Reconciliation)
CREATE TABLE IF NOT EXISTS volume_reconciliations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id INTEGER NOT NULL,
    item_code TEXT NOT NULL, -- '1.1', '1.2', '2.1'
    category_name TEXT NOT NULL, -- 'I. СВЕТОПРОЗРАЧНЫЕ КОНСТРУКЦИИ'
    element_name TEXT NOT NULL, -- 'Витражное остекление (прозрачное)'
    unit TEXT NOT NULL, -- 'м²', 'шт.', 'п.м.', 'компл.'
    pdf_volume REAL NOT NULL,
    dwg_volume REAL NOT NULL,
    delta_volume REAL NOT NULL,
    convergence_pct REAL NOT NULL,
    engineering_note TEXT,
    accepted_volume REAL NOT NULL,
    FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE
);

-- 5. Нормативная база единичных расценок
CREATE TABLE IF NOT EXISTS unit_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_code TEXT UNIQUE NOT NULL,
    category TEXT NOT NULL,
    work_name TEXT NOT NULL,
    material_specification TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    material_price_no_vat REAL NOT NULL,
    smr_price_no_vat REAL NOT NULL,
    updated_at TEXT NOT NULL
);

-- 6. Сформированные первоначальные бюджеты (сметы)
CREATE TABLE IF NOT EXISTS estimates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    total_materials_no_vat REAL NOT NULL,
    total_smr_no_vat REAL NOT NULL,
    total_cost_no_vat REAL NOT NULL,
    vat_22 REAL NOT NULL,
    total_cost_with_vat REAL NOT NULL,
    avg_price_per_m2 REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL,
    FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS estimate_rows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_id INTEGER NOT NULL,
    reconciliation_id INTEGER NOT NULL,
    unit_rate_id INTEGER NOT NULL,
    quantity REAL NOT NULL,
    material_cost REAL NOT NULL,
    smr_cost REAL NOT NULL,
    total_row_cost_no_vat REAL NOT NULL,
    total_row_cost_with_vat REAL NOT NULL,
    FOREIGN KEY (estimate_id) REFERENCES estimates(id) ON DELETE CASCADE,
    FOREIGN KEY (reconciliation_id) REFERENCES volume_reconciliations(id),
    FOREIGN KEY (unit_rate_id) REFERENCES unit_rates(id)
);
```

---

## 5. План интеграции с интерфейсом Launcher (UI Buttons)

В верхней панели (`action-grid` в `app/frontend/index.html`) для загруженного и выбранного объекта добавляются три целевые кнопки:

1. **`📊 Объемы` (Расчет и сверка объемов):**
   - Запускает сбор геометрии из DWG и PDF.
   - Открывает интерактивное представление в Окне №3:
     - Таблица сверки (Векторный PDF vs DWG Hatch) с цветовой индикацией сходимости (>95% — зелёный);
     - Матрица площадей по фасадам (Фасад 1-8, 8-1, Л-А, А-Л, Итого).
2. **`💰 Бюджет` (Первоначальный бюджет):**
   - Применяет базу расценок к принятым объемам.
   - Показывает интерактивную ведомость с возможностью директивной смены цен или применения быстрых ориентиров (85 / 87.5 / 90 тыс. ₽/м² фасада под ключ).
   - Выводит структуру затрат: доля материалов (62.5 тыс. ₽/м²), доля монтажа с механизмами (25.0 тыс. ₽/м²), НДС 22%.
3. **`📑 Паспорт` (Генерация и экспорт документации):**
   - Открывает готовый интерактивный паспорт фасадов объекта в Окне №3.
   - Предоставляет кнопки «📥 Скачать Excel (CSV)» и «🖨️ Печать / PDF».

---

## 6. Пошаговая дорожная карта для следующего агента

При переходе в новый чат агент должен следовать следующему четкому плану:

1. **Шаг 1: Актуализация базы данных `app/backend/db.py`**
   - Применить расширенную схему таблиц (`roots`, `parsed_elements`, `volume_reconciliations`, `unit_rates`, `estimates`, `estimate_rows`).
   - Наполнить таблицу `unit_rates` эталонными базовыми расценками из `Ведомость_объемов_работ_фасады_БЦ_Энгельса.csv`.
2. **Шаг 2: Реализация движка извлечения и сверки объемов (`app/backend/volume_engine.py`)**
   - Интеграция извлечения контуров из DWG (через CadCraft) и векторных полигонов из PDF (PyMuPDF).
   - Расчет дельты, коэффициента сходимости и генерация строк сверки.
3. **Шаг 3: Генератор интерактивного HTML-паспорта и CSV-сметы (`app/backend/budget_generator.py`)**
   - Создание сервиса, который берет расчетные данные из SQLite и формирует полнофункциональный HTML-паспорт (по эталону `Паспорт_и_спецификация_фасадов_БЦ_Энгельса.html`).
   - Формирование CSV файла спецификации с формулами и итогами.
4. **Шаг 4: Интеграция с UI F.E.R.O. Launcher**
   - Добавление кнопок «📊 Объемы», «💰 Бюджет», «📑 Паспорт» в `app/frontend/index.html`.
   - Подключение обработчиков в `app/frontend/app.js` и вывод результатов в Окне №3.
5. **Шаг 5: Сквозной тест на эталоне**
   - Запустить расчет на папке `g:\Общие диски\011_Производство\ФЕРО\Заказчики\ГК Эколайн\БЦ на Энгельса\DWG AP`.
   - Сверить выданные площади и бюджет с эталонными файлами.
