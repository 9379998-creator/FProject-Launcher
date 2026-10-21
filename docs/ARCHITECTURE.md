# Architecture

Launcher v3 is split into four explicit layers.

## 1. Frontend

Browser UI for object navigation, filters, thumbnails, and document viewing.

## 2. Backend

Local Python API server that indexes selected object folders and serves prepared manifests/assets to the frontend.

## 3. Render pipeline

Format-specific preparation layer.

Current PDF model:

- mass overview render: `150 DPI`;
- active/opened page render: `300 DPI`;
- both levels are cached separately;
- the frontend shows which quality is currently displayed.

This keeps large PDF batches usable without waiting for every page to be rendered in full quality.

## 4. Runtime data

Local writable data: caches, manifests, logs, generated previews. Runtime data is not committed to GitHub.

## 5. Future universal preview layer

Launcher should become a universal preview and navigation shell for common project files, not a replacement for native editors.

Target format families:

- PDF: rendered and viewed inside Launcher;
- DWG: preview through paired PDF when possible, open native DWG when needed;
- Word: page previews, native editing in Word;
- Excel: sheet/tab previews, native editing in Excel;
- images: direct preview for PNG/JPG/JPEG/TIFF/GIF where practical.
