# Checkpoint — shared viewer controls and readable tree

Date: 2026-08-13

## Accepted result

The Launcher is accepted for continued regression testing of normal project
folders.  The object tree is visually readable in both its wide browsing mode
and the compact left panel.  Folder, subfolder and file hierarchy is shown by
distinct rows and connecting lines, with compact folder widths based on the
name and counter rather than the whole screen width.

The lower viewer panel is now a single accepted control set across PDF, DWG
previews, Word and Excel:

- zoom out / zoom in;
- `Вписать` with a full unwrapped label;
- rotate;
- hand / arrow mode;
- standard, medium and full viewing modes;
- the appropriate native-open action for the selected file type.

## Important correction

Excel uses an HTML iframe layer above the PDF stage.  A generic display rule
could previously override its `hidden` attribute, leaving the inactive iframe
above a valid PDF or DWG image.  The user would then see a thumbnail but a
blank large area.  The CSS rule now explicitly maps `.excel-viewer[hidden]`
to `display: none`.

Excel rotation is implemented through the same bottom-panel button as PDF and
DWG.  A cache version change ensures previously stored Excel sheet HTML is
rebuilt with the rotation message handler instead of retaining an old page.

## Rules learned from rejected attempts

1. Do not create a separate, reduced control panel for Excel or Word.
2. Do not use experimental browser-shaped/overlapping Excel tabs, SVG tab
   backgrounds, or pseudo-element caps.  They created white artefacts and a
   delayed active state.  Ordinary rounded HTML buttons are the accepted tabs.
3. Do not hide a viewer layer with JavaScript alone if CSS can restore its
   display; use a `[hidden]` display rule for overlays.
4. Do not accept a cross-format viewer change without testing both the source
   mode and an unrelated mode that shares the same stage.

## Verification completed

- JavaScript syntax check;
- Python compile;
- UTF-8 encoding check;
- `git diff --check`;
- browser QA: PDF control bar and a real Excel workbook, including visible
  rotate and a 70-pixel-wide `Вписать` control.

## Next decision

Do not start automatic DWG rendering as the default path.  Continue using
accepted DWG/PDF pairing for files that have a reliable PDF counterpart.
Create a bounded research prototype for DWG files without a PDF pair.  The
default preview target is the complete Model Space, fitted to its drawing
extents: its role is quick orientation, not a precise printable sheet.
Launcher must not use whichever tab happened to be active when the DWG was
last saved.  If the model cannot be exported or has unusable extents, show a
clear no-preview state and retain `Открыть DWG`.
