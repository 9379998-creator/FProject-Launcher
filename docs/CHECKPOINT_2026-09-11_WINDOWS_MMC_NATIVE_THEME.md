# Checkpoint — Windows / MMC Native Utility Theme & Rotation Rules

Date: 2026-09-11
Branch: `checkpoint/windows-mmc-native-theme`

## Accepted Design Direction: Windows MMC Native Style

Launcher v3 officially adopts the classical Windows administrative utility style (Microsoft Management Console / Windows Explorer) as its primary design language:

1. **Technocratic Utility & High Information Density**:
   - Compact tree rows (22px) with sharp, clean hierarchy and vertical guide lines.
   - Razor-thin (5px) native Windows scrollbars without buttons.
   - MMC-style header banner with blue accent gradient and clear contextual title.
   - Native-feel selection highlights (`#ebf4fc` background, `#3399ff` border, dark text).
   - Format extension bar (`#formatStrip`) strictly limited to 2 lines (45px) with neat scroll.

2. **Clean Information Presentation (Zero Clutter)**:
   - Completely eliminated all "150 DPI" / "300 DPI" labels, progress mentions, and floating badges.
   - Clean, professional status messages focused on progress and file counts rather than technical render internals.

3. **Rotation Architecture & Mode Separation**:
   - **Mode 1 (Standard Mode)**: Rotating (`⟳`) rotates **only the central preview document** (`#pdfPageImage`). The thumbnail list in the left rail is locked (`transform: none !important;`) and never rotates.
   - **Mode 2 (Medium / Thumbnails Ribbon)**: Rotation is **completely excluded and blocked**.
     - The rotate button is hidden from controls (`display: none !important` and `hidden = true`).
     - Clicking rotate in Mode 2 is ignored.
     - Thumbnail cards maintain strict true aspect ratios without distortion.
     - Zoom controls (`+` / `-` / `Вписать`) zoom the thumbnail ribbon proportionally.
   - **Mode 3 (Full Screen Mode)**: Rotates the full-screen central document view.

## Strategic Rationale

- **Zero Cognitive Load**: Engineers, designers, and project managers work primarily in Windows, AutoCAD, Excel, and Explorer. The native OS aesthetic is instantly familiar and non-distracting.
- **Form Follows Function**: The interface recedes into the background so the engineering content (drawings, specifications, estimates) takes center stage.
- **Symbiosis of Utility & Usability**: Direct access to local filesystem paths (`Открыть в Проводнике`, `Скопировать путь`) combined with rapid document preview and sheet switching.
