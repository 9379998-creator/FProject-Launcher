# Roadmap

## Phase 0 - Repository and workspace discipline

- Create clean repository.
- Define local runtime rules.
- Stop using old launcher folders as working roots.
- Keep Google Drive object data separate from the live writable runtime.

Status: accepted as project discipline.

## Phase 1 - Object shell and left panel

- Local server.
- Object list.
- Load/update/exclude object actions.
- Tree navigation.
- Format filters.
- Multi-object workflow.
- Search and file selection.

Status: functioning and accepted for current stage.

## Phase 2 - Accepted PDF viewer

- Wide object-tree browsing mode for long file names.
- Mass PDF overview render at `150 DPI`.
- Active/opened page render at `300 DPI`.
- Separate cache for preview and quality renders.
- Visible quality indicator in the viewer.
- Accepted viewer controls: thumbnails, zoom, fit, rotate, pan/hand, standard/medium/full modes.

Status: functioning and accepted for current stage.

## Phase 3 - Design polish

Next work should make the interface lighter and more professional without breaking accepted behaviour.

Targets:

- more airy layout;
- less visual noise;
- better spacing and hierarchy;
- refined buttons;
- cleaner left panel;
- cleaner thumbnail strip;
- subtler viewer overlays;
- consistent progress indicators and captions.

## Phase 4 - Universal preview layer

Launcher should become a universal preview and navigation shell for common project file formats.

Target formats:

- PDF;
- DWG;
- DOC/DOCX;
- XLS/XLSX;
- PNG/JPG/JPEG;
- TIFF;
- GIF;
- optionally PPT/PPTX later.

Important principle: do not reinvent Word, Excel, or AutoCAD. Launcher should preview, match, navigate, and open. Native programs remain authoritative editors.

## Phase 5 - DWG/PDF pairing

DWG files often have matching PDF files.

Desired behaviour:

- detect likely DWG/PDF pairs by name and folder;
- prefer a project rule where paired DWG and PDF files are named one-to-one;
- use the matching PDF as the visual preview for the DWG;
- let the user jump from preview to the DWG file;
- show an action such as `Open in DWG Viewer` / native DWG application;
- open the DWG in the native application when needed.

Status: functioning and accepted for current stage.

Accepted checkpoint:

- `docs/CHECKPOINT_2026-08-12_DWG_ACCEPTED.md`

Remaining optional improvements:

- diagnostics screen for found/suspicious/missing DWG/PDF pairs;
- manual override for rare incorrect pairs;
- per-object pairing report.

## Phase 6 - Word and Excel previews

Desired behaviour:

- Word: preview document pages;
- Excel: preview workbook sheets/tabs;
- keep native Word/Excel opening for real editing;
- decide the implementation strategy after testing conversion options.

Candidate strategies:

- Office/LibreOffice export to PDF/PNG;
- Windows shell thumbnails;
- external converters;
- hybrid preview cache plus native open.

Status: functioning and accepted for current stage.

- Word/DOC/DOCX/GDOC: functioning and accepted for current stage.
- Excel/XLSX/XLSM: functioning and accepted for normal review workbooks.
- XLS: remains visible and natively openable; local HTML conversion needs a
  separate compatibility test.

Accepted Word checkpoint:

- `docs/CHECKPOINT_2026-08-12_VORTEX_WORD_ACCEPTED.md`

Accepted checkpoints:

- `docs/CHECKPOINT_2026-08-12_VORTEX_WORD_ACCEPTED.md`
- `docs/CHECKPOINT_2026-08-13_VORTEX_EXCEL_ACCEPTED.md`
- `docs/CHECKPOINT_2026-08-13_VIEWER_CONTROLS_AND_TREE.md`

Next refinement:

- regression-test the accepted formats with ordinary object folders;
- investigate a safe optional Model Space overview route for DWG files without
  PDF pairs.  The first preview target is the complete model, not a Layout:
  it is an orientation image, while detailed work remains in native CAD.

## Phase 7 - Modules

- Module registry with declared input formats, output, confidence and log.
- Input selection from the active object/tree/filter, not opaque chat-only input.
- Progress telemetry and dry-run/confirmation where results create files.
- Result viewer integration and reproducible run history.
- First candidate: registry-of-invoices ↔ scanned-invoices reconciliation.

## Phase 8 - Pilot deployment

- Local-first Windows installation on other computers.
- Runtime diagnostics: available native applications, cache location and
  supported preview paths.
- Pilots against real project folders of 3–5 users.
- Measure cold first-use time, warm-cache speed, errors and loss of context.
- Keep VPS usage limited to a landing page, documentation and anonymized demo;
  do not move users' live project folders or native-app integration to a VPS.

Product direction and critical market assumptions:

- `docs/PRODUCT_DIRECTION_VISUAL_TRIAGE_AND_MODULES.md`
- `docs/MARKET_CRITICAL_REVIEW_BRIEF.md`

