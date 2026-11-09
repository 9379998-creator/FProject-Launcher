# Паспорт передачи проекта: F-Engineering / FProject Launcher (v4.3.0)
**Инженерное бюро ООО «ФЕРО»**  
*Дата фиксации: 09 ноября 2026 г.*

---

## 1. Репозитории GitHub (Source of Truth)

| Назначение | Ссылка на GitHub | Ветка / Статус |
|---|---|---|
| **Активный репозиторий разработки (v4.3.0)** | [`https://github.com/9379998-creator/FProject-Launcher`](https://github.com/9379998-creator/FProject-Launcher) | `main` (последний коммит `cf801d6`, рабочая база) |
| Базовый репозиторий организации (v3.1.0) | [`https://github.com/f-engineering-spb/f-engineering-launcher`](https://github.com/f-engineering-spb/f-engineering-launcher) | `dvg-main` (архивный baseline) |
| Зеркало v4 | [`https://github.com/9379998-creator/fero-launcher-v4`](https://github.com/9379998-creator/fero-launcher-v4) | `main` |

---

## 2. Размещение файлов на локальном компьютере

### А. Папка разработки (Workspace для нового чата):
> **`C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher\`**  
> *(Именно эту папку нужно добавить в «Проекты» в Antigravity).*
* Полный клонированный Git-репозиторий со всеми исходниками, тестами и скриптами сборки.
* Ветка `main`, состояние рабочей копии чистое (`working tree clean`).

### Б. Среда выполнения (Installed App на компьютере):
> **`C:\Users\a9379\AppData\Local\FEngineering_Launcher\`**
* Установленная рабочая версия лаунчера, с которой работает ярлык на Рабочем столе.
* В процессе работы лаунчер поднимает локальный API-сервер на `http://127.0.0.1:8780` (при занятости переходит на порты `8781..8789`) и запускает окно WebView2.

### В. Готовые пакеты для передачи коллегам:
1. **Корпоративный общий Google Диск:**
   * Путь: `G:\Общие диски\022_F-Engineering\01_Launcher\`
   * Файлы:
     * `FEngineering_Launcher_v4_Portable.zip` (161 МБ, полный автономный переносимый релиз)
     * `Запуск_Лаунчера.bat` (скрипт запуска в 1 клик)
     * `ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt` (памятка по запуску)
     * `FEngineering_Launcher_Setup.exe` (1-клик установщик Inno Setup)
2. **Локальная папка для быстрой пересылки (флешка / Telegram):**
   * Путь: `C:\Users\a9379\Documents\FERO_Launcher_v4_Release\`

---

## 3. Что было сделано в текущей сессии (09.11.2026)

1. **Аудит состояния:** Выявлены все активные репозитории на GitHub и локальные каталоги; подтверждено, что рабочая версия на ПК соответствует версии 4.3.0 в `FProject-Launcher`.
2. **Сборка Portable-релиза:**
   * Из рабочей среды упакованы бинарник `FEngineeringLauncher.exe`, рантайм `_internal` со всеми скомпилированными Python-библиотеками, каталоги `app/` и `scripts/`.
   * Интегрирован автономный Poppler (`runtime/tools/poppler`), исключающий внешние зависимости при рендеринге PDF/DWG.
   * Очищены персональные базы данных (`runtime/db`), кэши рендеринга и логи.
3. **Создание запускающего бат-файла:**
   * Создан `Запуск_Лаунчера.bat` (кодировка UTF-8, автоматическая смена рабочей директории на `%~dp0`, запуск `FEngineeringLauncher.exe` без консольных ошибок).
   * Добавлены `Создать_ярлык_на_Рабочем_столе.bat` и `ИНСТРУКЦИЯ_ДЛЯ_КОЛЛЕГИ.txt`.
4. **Верификация и тестирование:**
   * Проведена проверка целостности архива ZIP: все 2 703 контрольные суммы CRC32 валидны.
   * Протестирован запуск `FEngineeringLauncher.exe` в изолированной среде: успешная инициализация PyMuPDF (`fitz 1.27.2.3`), `ezdxf` и `webview`.
5. **Синхронизация:** Релизный архив и сопутствующие файлы скопированы на Google Диск и в локальную папку `Documents`.

---

## 4. Архитектура проекта и структура исходников

```text
FProject-Launcher/
├── app/
│   ├── backend/               # Локальный API-сервер (Bottle)
│   │   ├── server.py          # Основной контроллер API, обработка запросов
│   │   ├── passport_generator.py # Генератор паспорта объекта (HTML/WBS)
│   │   ├── dwg_engine.py      # Обработчик DWG чертежей
│   │   ├── excel_engine.py    # Парсер спецификаций Excel
│   │   └── folder_picker.cs   # Нативный Win32/COM диалог выбора папок
│   ├── frontend/              # Интерфейс браузера (WebView2)
│   │   ├── index.html         # Разметка 3-оконного просмотрщика
│   │   ├── styles.css         # Стилизация (дизайн FERO Light / Gray)
│   │   └── app.js             # Логика клиента, зум, панорамирование
│   ├── cad/                   # Модули анализа и связки геометрии
│   │   ├── component_assembler.py # Сборщик фасадных элементов
│   │   └── pdf_cad_extractor.py   # Извлечение размерных цепочек и привязок
│   ├── rendering/             # Диспетчер отрисовки документов
│   └── flauncher.pyw          # Точка входа приложения (WebView2 + фоновый сервер)
├── installer/
│   └── launcher_setup.iss     # Сценарий сборщика Inno Setup
├── scripts/
│   ├── build_exe.cmd          # Сборка автономного EXE через PyInstaller
│   ├── build_installer.cmd    # Сборка установщика
│   └── start_windows.cmd      # Скрипт запуска для разработчика
├── runtime/                   # Временные папки (игнорируются Git, кроме tools)
│   └── tools/poppler/         # Автономные утилиты Poppler
├── FProjectLauncher.spec      # Конфигурация PyInstaller
└── version.json               # Метаданные версии (4.3.0)
```

---

## 5. Инструкция для агента в новом чате (Quick Start)

Если вы начинаете новый чат в рабочей папке `FProject-Launcher`:

1. **Запуск лаунчера из исходников для тестирования:**
   ```powershell
   python app/flauncher.pyw
   ```
2. **Пересборка исполняемого файла после правок:**
   ```cmd
   scripts\build_exe.cmd
   ```
   *(Результат помещается в `dist\FEngineeringLauncher\`)*.
3. **Фиксация изменений в репозитории:**
   ```powershell
   git status
   git add .
   git commit -m "feat/fix: краткое описание изменений"
   git push origin main
   ```
4. **Обновление релизного архива:**
   Скрипт сборки пакета для коллег сохранен в:  
   `C:\Users\a9379\.gemini\antigravity\scratch\make_package.py`  
   Скрипт деплоя на Google Диск:  
   `C:\Users\a9379\.gemini\antigravity\scratch\deploy_release.py`

---
*Документ подготовлен ИИ-ассистентом Antigravity (ООО «ФЕРО»).*
