# Checkpoint — Vortex Excel accepted

Date: 2026-08-13

## User outcome

The Excel preview block is accepted for normal project workbooks.  The user
tested several books, including a workbook of roughly 2,000 rows and a book
with four to five worksheets.  Very large or malformed files may fail or take
too long; they are outside the first navigator target and remain available for
opening in native Excel.

## Product purpose

Launcher helps a user recognise the needed workbook visually, read it without
leaving the object structure, and then open it in Microsoft Excel only when
editing or detailed work is needed.  It does not try to become a replacement
for Excel.

## Accepted architecture

```text
XLSX / XLSM
  -> one cached read-only HTML sheet per workbook tab
  -> same HTML sheet in the large viewer
  -> reduced viewport of that same HTML sheet in the workbook card
  -> native Excel for editing
```

The thumbnail is not independently redrawn.  This is the permanent rule: the
large sheet is the visual source of truth and the card is merely its reduced
view.  It prevents the previously observed errors: incorrect text baseline,
clipped text inside cells, changed row geometry, and differing quality between
the card and large viewer.

## Viewer behaviour accepted

- Workbook cards appear in the rail and retain full file names without
  ellipses.
- The opened workbook name is shown above the sheet tab bar.
- The sheet tab bar supports navigation when many tabs do not fit.
- A sheet supports horizontal/vertical scrolling, zoom and hand panning.
- The technical worksheet notice bar was removed because it duplicated the
  application chrome and reduced readable height.
- The first sheet opens immediately.  Remaining tabs are prepared in the
  background one by one.  Cached API retrieval was measured at about 4–5 ms;
  initial creation of a heavy sheet can take several seconds.
- `Open Excel` remains the route to the native application.

## Limits for the first accepted version

- Primary HTML support: `.xlsx` and `.xlsm`.
- `.xls` stays visible and can be opened in Excel, but is not silently parsed
  by the HTML path.
- Default review limit: up to 2,000 source rows and 100 columns per sheet.
- The normal target is 100–200 rows; 500–2,000 is an exceptional review case.
- Broken or exceptionally heavy books must fail clearly rather than holding up
  normal books.

## What must not be done again

1. Do not build miniature Excel tables with a separate font/row algorithm.
2. Do not derive a thumbnail from a low-resolution raster and later enlarge
   it.
3. Do not build every workbook tab before showing the first sheet.
4. Do not repeat workbook parsing for an already cached sheet request.
5. Do not place technical status text inside the sheet canvas.
6. Do not mark a visual renderer accepted on syntax checks alone: inspect the
   real card and the large sheet in Chrome.

## Verification completed

- `C:\Python314\python.exe -m py_compile app\backend\server.py`
- `node --check app\frontend\app.js`
- `git diff --check`
- `scripts\check_encoding.cmd`
- Chrome visual QA of the cached HTML sheet and Launcher shell.

## Next product step

Treat Excel as accepted and move to ordinary regression testing with normal
object folders.  The next planned Vortex formats are image preview support
(`JPG`, `PNG`, `TIFF`, `GIF`) and later any separately prioritised refinement.
