# Vortex Excel: benchmark PDF-converter

## Purpose

Choose a reliable local application for optional PDF creation from Excel workbooks. The criterion for this test is conversion speed and unattended operation, not visual preference.

## Applications tested

- Microsoft Excel LTSC Professional Plus 2024, licensed and available through COM automation;
- SoftMaker FreeOffice 2024 PlanMaker, available through COM automation.

WPS Office was intentionally excluded from this comparison.

## Test workbooks

All files were read from `C:\Users\a9379\Downloads`.

| Workbook | Sheets | Largest used range | Test role |
| --- | ---: | --- | --- |
| `КП Легенда корпус 7.2 — рабочая копия для заполнения (1).xlsx` | 6 | 1,023 rows × 32 columns | multi-sheet commercial workbook |
| `РЕЕСТР СЧЕТОВ _ ДЕМО.xlsx` | 4 | 4,935 rows × 20 columns | long register |

## Results

| Operation | Excel | PlanMaker |
| --- | ---: | ---: |
| Open `КП Легенда` | 3.27 s | 4.24 s |
| Open `РЕЕСТР СЧЕТОВ` | 6.76 s | 5.46 s |
| Export `КП Легенда` to PDF | 33.41 s, 17 pages | no unattended PDF API |
| Export `РЕЕСТР СЧЕТОВ` to PDF | 26.84 s, 125 pages | no unattended PDF API |

## Decision

Use **Microsoft Excel** for optional automatic PDF assets:

`XLS/XLSX/XLSM → Excel COM → optional PDF asset / thumbnail`.

PlanMaker opens the long test workbook roughly one second faster, and may remain a preferred manual editing/viewing application. However, its exposed automation API offers `Open`, `SaveAs` and `PrintOut`, but no direct PDF export. The installed PlanMaker documentation describes PDF generation as an interactive `File → PDF export` dialog. That would require fragile UI clicking for every workbook and cannot be used as a reliable Launcher cache pipeline.

The PDF result is **not** the intended primary Excel viewer. The preferred Vortex Excel experience is a read-only sheet view: a book exposes worksheet tabs, each tab keeps spreadsheet geometry and can be scrolled horizontally and vertically without an Excel application frame. PDF can remain an optional overview/thumbnail artifact.

## Consequence for user workflow

- Launcher keeps a workbook as one book with named sheet tabs; it does not split the original into separate source documents.
- The primary view is an HTML sheet cache preserving column widths, row heights, merges and basic formatting.
- PDF generation through Excel remains available only for an optional overview/thumbnail asset.
- Native opening remains configurable through Windows; a user may still open/edit an XLSX in PlanMaker if that is the preferred application.
- The next product test is browser QA: select one XLSX in Launcher, press `Отобразить`, switch worksheet tabs and pan a sheet in both directions.
