# Checkpoint 2026-08-12 — Vortex Word accepted

## Статус

Этап Word внутри модуля `Вортекс` принят как рабочая контрольная точка.

Пользователь проверил:

- `.doc` отображается и открывается;
- `.docx` отображается и открывается;
- `.gdoc` теперь виден, выбирается и открывается как Google Docs shortcut;
- текущую реализацию можно фиксировать и переходить к Excel.

## Название модуля

Оставлено название `Вортекс`.

Смысл: разные форматы файлов попадают в единый preview-поток Launcher.

## Реализованная схема Word

Для локальных Word-файлов:

```text
DOC/DOCX → Microsoft Word → PDF cache → existing PDF render pipeline
```

Почему так:

- Microsoft Word установлен на текущем компьютере;
- существующий PDF viewer уже принят;
- не нужно писать второй Word;
- можно использовать те же миниатюры, масштаб, лапу, поворот, режимы просмотра и кэш.

## Backend

Добавлены endpoints:

```text
POST /api/word/render
POST /api/word/page
```

Добавлен скрипт:

```text
scripts/convert_word_to_pdf.ps1
```

Он использует Microsoft Word COM automation:

- открывает документ в read-only режиме;
- экспортирует в PDF;
- закрывает документ и Word COM;
- кладёт PDF в `runtime/cache/word/...`.

## Frontend

Добавлено:

- `DOC`, `DOCX`, `GDOC` участвуют в фильтрах;
- `DOC/DOCX` идут в Word preview;
- Word preview после конвертации отображается в обычном PDF viewer;
- кнопка native open для Word называется `Открыть Word`;
- `.gdoc` не рендерится через Word, а показывает карточку без local preview;
- для `.gdoc` кнопка называется `Открыть Google Docs`.

## GDOC правило

`.gdoc` — это не локальный Word-документ, а Google Docs shortcut.

Поэтому:

- не пытаться конвертировать `.gdoc` через Microsoft Word;
- показывать его в дереве и фильтрах;
- позволять выбрать и нажать `Отобразить`;
- в viewer показывать placeholder;
- открывать через Windows/Google Drive.

## Проверка

Реальный smoke test был выполнен на файле:

```text
ссылка на тендер.docx
```

Результат:

- первый прогон: DOCX → PDF → PNG, 1 страница, ошибок 0;
- повторный прогон: примерно 0.5 сек;
- `convertCacheHit=True`;
- `cacheHit=True`.

Пользовательская проверка подтвердила: Word/GDOC работает достаточно хорошо для checkpoint.

## Следующий этап

Переходим к Excel:

```text
XLS/XLSX → Excel export → PDF cache → existing PDF render pipeline
```

Открытые вопросы Excel:

- показывать workbook как набор листов/вкладок;
- учитывать области печати;
- не рендерить огромные пустые области;
- сохранить native open через Excel;
- использовать кэш, если файл не изменился.

