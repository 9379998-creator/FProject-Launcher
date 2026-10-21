# Decisions

## 2026-08-11 — Separate Launcher from knowledge base

Launcher is an application and must live in its own repository. The knowledge base remains a repository for approved rules, workflows, and reusable knowledge.

## 2026-08-11 — Local runtime on C:\

The live Launcher runtime should run from a local Windows `C:` workspace. Google Drive can store object files and archives, but it should not be the live writable runtime root.

## 2026-08-12 - PDF preview-first pipeline accepted

Mass PDF display should not render every selected PDF page in full quality upfront.

Accepted model:

- render mass PDF overview at `150 DPI`;
- render the currently opened page at `300 DPI`;
- store both outputs in cache;
- show a visible quality indicator in the viewer;
- preserve the accepted PDF viewer controls and behaviour.

This replaced the earlier all-pages-at-300-DPI approach because Poppler rendering, not Google Drive file access, was measured as the main time cost for already available files.

## 2026-08-12 - Wide tree selection mode accepted

When browsing an object's internal file tree, the right workspace may be used as a wide tree area so long file names are readable.

After the user presses `Отобразить`, the right workspace returns to the PDF viewer with thumbnails and the main page view.

## 2026-08-12 - Native applications remain authoritative editors

Launcher should not become a second Word, Excel, or AutoCAD.

For non-PDF formats the goal is preview, navigation, matching, and quick opening:

- DWG should be paired with matching PDF previews when available;
- Word should ideally expose page previews;
- Excel should ideally expose sheet/tab previews;
- native applications remain the place for full editing.

## 2026-08-12 - DWG uses PDF preview plus native open

DWG is not rendered as a native CAD canvas inside Launcher.

Decision:

- use the matching PDF as the visual preview for a DWG file;
- open the original DWG through Windows default application when the user asks;
- keep DWG files without PDF pairs visible and selectable;
- show a `Нет PDF-пары` placeholder for DWG files without a preview.

Reason:

- DWG viewers differ by workstation;
- AutoCAD/DWG TrueView are better native tools for actual DWG inspection;
- Launcher's job is fast navigation, preview, and selection.

## 2026-08-12 - DWG/PDF matching must be semantic, not only numeric

DWG/PDF file names are not always one-to-one by sheet number.

Decision:

- normalize project codes such as `АР2-2-2` and `АР2.2.2`;
- compare cleaned meaningful tails of file names;
- use long phrase and token-sequence similarity;
- keep strict guards against different sections and different explicit parts.

Reason:

- real project files can differ by sheet number while clearly describing the same drawing;
- false negatives are common with numeric-only matching;
- false positives across different sections are more dangerous than missing a rare pair.

## 2026-08-12 - Vortex Word preview uses Word-to-PDF cache

Word documents are previewed through the existing PDF pipeline.

Decision:

- `.doc` and `.docx` are converted by Microsoft Word to PDF cache;
- generated PDFs are rendered by the accepted PDF preview pipeline;
- `.gdoc` is treated as a Google Docs shortcut, not as a local Word document;
- `.gdoc` is visible/selectable/openable but does not get a local preview.

Reason:

- Microsoft Word is installed locally;
- the PDF viewer is already accepted;
- building a second Word viewer is unnecessary;
- Google Docs shortcuts are links, not actual DOCX content.
