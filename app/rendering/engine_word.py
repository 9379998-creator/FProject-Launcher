"""Движок Word: быстрый DOCX→HTML первично, Word COM — только фолбэк для .doc.

Предоставляет полноценную HTML-оболочку с поддержкой:
- Масштабирования (zoom in / zoom out / wheel zoom);
- Прокрутки (естественный скролл и панорамирование);
- Горячих клавиш (Escape для шага назад, dblclick для переключения полноэкранного режима);
- Контекстного меню и нативного открытия.
"""

from __future__ import annotations

import base64
import html as _html
import json
import os
import subprocess
import time
from pathlib import Path

try:
    from docx import Document
except ImportError:
    Document = None

WORD_COM_TIMEOUT_SECONDS = 120


def _runs_html(paragraph) -> str:
    out = []
    for run in paragraph.runs:
        text = _html.escape(run.text)
        if not text:
            continue
        if run.bold:
            text = f"<b>{text}</b>"
        if run.italic:
            text = f"<i>{text}</i>"
        if run.underline:
            text = f"<u>{text}</u>"
        out.append(text)
    return "".join(out) or _html.escape(paragraph.text)


def _cell_shading(cell) -> str | None:
    try:
        tc_pr = cell._tc.get_or_add_tcPr()
        shd = tc_pr.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}shd")
        if shd is not None:
            fill = shd.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}fill")
            if fill not in (None, "auto", "ffffff"):
                return "#" + fill[-6:]
    except Exception:
        pass
    return None


def _cell_span(cell) -> str:
    try:
        grid_span = cell._tc.get_or_add_tcPr().find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}gridSpan")
        if grid_span is not None:
            val = int(grid_span.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val") or 1)
            if val > 1:
                return f' colspan="{val}"'
    except Exception:
        pass
    return ""


def docx_to_html_string(src: Path) -> tuple[str, dict]:
    """Распарсить DOCX в автономный интерактивный HTML-документ. Возвращает (html, stats)."""
    if Document is None:
        raise RuntimeError("Для просмотра DOCX нужен пакет python-docx")
    t0 = time.perf_counter()
    doc = Document(str(src))
    t_load = (time.perf_counter() - t0) * 1000
    t1 = time.perf_counter()

    body_parts = []
    rels = doc.part.rels
    n_paragraphs = 0
    n_tables = 0
    page_break_count = 1

    # Верхний маркер первой страницы
    body_parts.append('<div class="doc-page-top"><span class="doc-page-num">— Страница 1 —</span></div>')

    # Читаем элементы тела документа строго в порядке их реального следования
    for element in doc.element.body:
        tag_name = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if tag_name == "p":
            from docx.text.paragraph import Paragraph
            p = Paragraph(element, doc)
            has_break = bool(p._p.xpath(".//w:br[@w:type='page']|.//w:lastRenderedPageBreak"))
            if has_break:
                page_break_count += 1
                body_parts.append(f'<div class="doc-page-divider" data-page="{page_break_count}"><span class="doc-page-num">— Страница {page_break_count} —</span></div>')

            if not p.text.strip() and not p._p.xpath(".//w:drawing|.//w:pict"):
                continue

            style = (p.style.name or "").lower()
            if style.startswith("heading 1"):
                tag = "h1"
            elif style.startswith("heading 2"):
                tag = "h2"
            elif style.startswith("heading 3"):
                tag = "h3"
            else:
                tag = "p"
            align = {1: "c", 2: "r", 3: "j"}.get(p.alignment, "")
            cls = f' class="{align}"' if align else ""
            imgs = ""
            for blip in p._p.xpath(".//a:blip"):
                rid = blip.get("{http://schemas.openxmlformats.org/officeDocument/2006"
                               "/relationships}embed")
                if rid in rels:
                    blob = rels[rid].target_part.blob
                    ctype = rels[rid].target_part.content_type
                    imgs += (f'<img src="data:{ctype};base64,'
                             f'{base64.b64encode(blob).decode()}">')
            body_parts.append(f"<{tag}{cls}>{_runs_html(p)}{imgs}</{tag}>")
            n_paragraphs += 1
        elif tag_name == "tbl":
            from docx.table import Table
            tbl = Table(element, doc)
            n_tables += 1
            body_parts.append("<table>")
            for row in tbl.rows:
                body_parts.append("<tr>")
                for cell in row.cells:
                    bg = _cell_shading(cell)
                    style_attr = f' style="background:{bg}"' if bg else ""
                    text = "<br>".join(_runs_html(p) for p in cell.paragraphs)
                    body_parts.append(f"<td{style_attr}{_cell_span(cell)}>{text}</td>")
                body_parts.append("</tr>")
            body_parts.append("</table>")

    doc_content = "".join(body_parts)

    html_page = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8">
<title>{_html.escape(src.stem)}</title>
<style>
html,body{{margin:0;padding:0;background:#e2e8f0;color:#1e293b;font:14px/1.6 "Segoe UI",Arial,sans-serif;overflow:auto}}
#doc-canvas{{display:flex;justify-content:center;padding:24px 16px;min-height:100vh;box-sizing:border-box;transform-origin:top center}}
#doc-sheet{{background:#fff;width:100%;max-width:880px;min-height:1120px;padding:36px 48px;box-shadow:0 4px 20px rgba(0,0,0,.12);border-radius:3px;box-sizing:border-box;position:relative}}
h1{{font-size:22px;line-height:1.3;text-align:center;margin:16px 0 20px}}
h2{{font-size:18px;line-height:1.3;margin:16px 0 12px}}
h3{{font-size:16px;line-height:1.3;margin:14px 0 8px}}
p{{margin:0 0 10px;text-indent:24px}}
p.c{{text-align:center;text-indent:0}}p.r{{text-align:right;text-indent:0}}p.j{{text-align:justify}}
table{{border-collapse:collapse;margin:16px 0;width:100%;table-layout:auto}}
td,th{{border:1px solid #64748b;padding:6px 10px;vertical-align:top;font-size:13px;line-height:1.4}}
th{{background:#f1f5f9;font-weight:600}}
img{{max-width:100%;height:auto;display:block;margin:12px auto}}
.doc-page-top{{text-align:center;color:#94a3b8;font-size:11px;font-weight:600;padding-bottom:18px;margin-bottom:18px;border-bottom:1px solid #f1f5f9;user-select:none;letter-spacing:0.5px}}
.doc-page-divider{{text-align:center;color:#94a3b8;font-size:11px;font-weight:600;padding:18px 0 12px;margin:32px 0 20px;border-top:1px dashed #cbd5e1;user-select:none;letter-spacing:0.5px}}
#doc-floating-page-badge{{position:fixed;bottom:16px;right:24px;background:rgba(30,41,59,.88);backdrop-filter:blur(4px);color:#fff;font-size:12px;font-weight:600;padding:6px 14px;border-radius:999px;box-shadow:0 2px 10px rgba(0,0,0,.25);z-index:1000;pointer-events:none;letter-spacing:.3px;transition:opacity .2s}}
</style></head><body>
<div id="doc-canvas"><div id="doc-sheet">{doc_content}</div></div>
<div id="doc-floating-page-badge">Стр. <span id="cur-p">1</span> из <span id="tot-p">{max(1, page_break_count)}</span></div>
<script>
let scale = 1;
const sheet = document.getElementById('doc-sheet');
const canvas = document.getElementById('doc-canvas');
const curPEl = document.getElementById('cur-p');
const totPEl = document.getElementById('tot-p');

function updatePageCounter() {{
  const dividers = sheet.querySelectorAll('.doc-page-divider');
  const total = Math.max(1, dividers.length ? dividers.length + 1 : Math.ceil(sheet.scrollHeight / 1100));
  totPEl.textContent = total;
  
  const scrollMid = window.scrollY + (window.innerHeight / 3);
  let cur = 1;
  dividers.forEach((d, idx) => {{
    if (d.offsetTop <= scrollMid) {{
      cur = idx + 2;
    }}
  }});
  if (!dividers.length) {{
    cur = Math.min(total, Math.max(1, Math.floor(scrollMid / 1100) + 1));
  }}
  curPEl.textContent = cur;
}}

window.addEventListener('scroll', updatePageCounter, {{ passive: true }});

// Если в документе не было явных разрывов страниц, но он длинный — создаем визуальные маркеры
window.addEventListener('DOMContentLoaded', () => {{
  const dividers = sheet.querySelectorAll('.doc-page-divider');
  if (!dividers.length && sheet.scrollHeight > 1200) {{
    const total = Math.ceil(sheet.scrollHeight / 1100);
    totPEl.textContent = total;
  }}
  updatePageCounter();
}});

function applyZoom(val) {{
  scale = Math.max(0.35, Math.min(3.0, val));
  sheet.style.transform = 'scale(' + scale + ')';
  sheet.style.transformOrigin = 'top center';
}}

window.addEventListener('wheel', (e) => {{
  if (!e.ctrlKey) return;
  e.preventDefault();
  applyZoom(scale * (e.deltaY < 0 ? 1.12 : 0.89));
}}, {{ passive: false }});

window.addEventListener('keydown', (e) => {{
  if (e.key === 'Escape') {{
    parent.postMessage({{ type: 'launcher-escape' }}, '*');
  }}
}});

window.addEventListener('dblclick', (e) => {{
  parent.postMessage({{ type: 'launcher-toggle-full-view' }}, '*');
}});

window.addEventListener('contextmenu', (e) => {{
  e.preventDefault();
  parent.postMessage({{
    type: 'launcher-contextmenu',
    clientX: e.clientX,
    clientY: e.clientY
  }}, '*');
}});

window.addEventListener('message', (e) => {{
  if (!e.data) return;
  if (e.data.type === 'launcher-sheet-zoom') {{
    applyZoom(e.data.value);
  }}
  if (e.data.type === 'launcher-sheet-fit') {{
    applyZoom(1.0);
  }}
}});
</script>
</body></html>'''

    t_gen = (time.perf_counter() - t1) * 1000
    stats = {
        "paragraphs": n_paragraphs,
        "tables": n_tables,
        "parseMs": round(t_load, 1),
        "generateMs": round(t_gen, 1),
        "totalMs": round(t_load + t_gen, 1),
    }
    return html_page, stats


WORD_ENGINE_VERSION = "v4"


def ensure_docx_preview(src: Path, cache_dir: Path) -> dict:
    """Закэшированный DOCX→HTML. Повтор — мгновенный дисковый хит без парсинга."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / "preview.html"
    meta_path = cache_dir / "preview.json"
    stat = src.stat()
    if out.exists() and meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (meta.get("sourceMtimeNs") == stat.st_mtime_ns
                    and meta.get("sourceSize") == stat.st_size
                    and meta.get("engineVersion") == WORD_ENGINE_VERSION):
                meta["cacheHit"] = True
                return meta
        except (OSError, json.JSONDecodeError):
            pass
    page, stats = docx_to_html_string(src)
    out.write_text(page, encoding="utf-8")
    meta = {
        "url": None,  # URL подставляет сервер (/cache/word/html/<key>/preview.html)
        "file": out.name,
        "bytes": out.stat().st_size,
        "sourceMtimeNs": stat.st_mtime_ns,
        "sourceSize": stat.st_size,
        "engineVersion": WORD_ENGINE_VERSION,
        "cacheHit": False,
        **stats,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def ensure_word_pdf(src: Path, target_dir: Path, cache_key: str,
                    convert_script: Path,
                    timeout: int = WORD_COM_TIMEOUT_SECONDS) -> tuple[Path, bool]:
    """COM→PDF с дисковым кэшем (фолбэк только для .doc)."""
    from datetime import datetime as _dt
    if not src.exists():
        raise FileNotFoundError(f"Word-файл не найден: {src}")
    if not src.is_file() or src.suffix.casefold() not in {".doc", ".docx"}:
        raise ValueError(f"Это не Word-файл: {src}")
    if not convert_script.exists():
        raise RuntimeError(f"Скрипт конвертации Word не найден: {convert_script}")
    target_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = target_dir / f"{src.stem}.pdf"
    manifest_path = target_dir / "manifest.json"
    if pdf_path.exists() and pdf_path.stat().st_size > 0 and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (manifest.get("sourcePath") == str(src)
                    and manifest.get("cacheKey") == cache_key
                    and manifest.get("sourceMtimeNs") == src.stat().st_mtime_ns
                    and manifest.get("sourceSize") == src.stat().st_size):
                return pdf_path, True
        except (OSError, json.JSONDecodeError):
            pass
    info = word_to_pdf_via_com(src, pdf_path, convert_script, timeout)
    manifest_path.write_text(
        json.dumps(
            {
                "sourcePath": str(src),
                "sourceName": src.name,
                "sourceMtimeNs": src.stat().st_mtime_ns,
                "sourceSize": src.stat().st_size,
                "cacheKey": cache_key,
                "pdfPath": str(pdf_path),
                "convertedAt": _dt.now().isoformat(timespec="seconds"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return Path(info["pdf"]), False


def word_to_pdf_via_com(src: Path, dst_pdf: Path, convert_script: Path,
                        timeout: int = WORD_COM_TIMEOUT_SECONDS) -> dict:
    """Фолбэк для старых бинарных .doc: Word COM через PowerShell-скрипт."""
    if dst_pdf.exists():
        dst_pdf.unlink()
    t0 = time.perf_counter()
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE
        kwargs["startupinfo"] = si

    proc = subprocess.Popen(
        [
            "powershell",
            "-STA",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(convert_script),
            "-InputPath",
            str(src),
            "-OutputPath",
            str(dst_pdf),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        close_fds=True,
        **kwargs,
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                    capture_output=True,
                    timeout=5,
                    close_fds=True,
                )
            except Exception:
                pass
        try:
            proc.kill()
        except Exception:
            pass
        raise TimeoutError(f"Word COM конвертация превысила таймаут {timeout} с")

    ms = (time.perf_counter() - t0) * 1000
    if proc.returncode != 0:
        message = (stderr.strip() or stdout.strip()
                   or "Word не смог конвертировать документ в PDF")
        raise RuntimeError(message)
    if not dst_pdf.exists() or dst_pdf.stat().st_size <= 0:
        raise RuntimeError("Word не создал PDF для preview")
    return {"pdf": str(dst_pdf), "bytes": dst_pdf.stat().st_size,
            "convertMs": round(ms, 1)}
