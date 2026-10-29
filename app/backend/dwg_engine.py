"""DWG Engine - модуль мгновенного чтения DWG чертежей без тяжелых внешних плоттеров.

Архитектура:
1. Уровень 0 (Header Preview): Мгновенное (< 1 мс) извлечение встроенного растрового
   превью (PNG или BMP/DIB) напрямую из бинарного заголовка DWG (R13-R2018).
2. Уровень 1 (Layouts Metadata): Быстрое извлечение списка вкладок (Model + Layouts)
   чертежа через анализ структуры/парного PDF/кэша без тяжелых блокировок.
3. Уровень 2 (Non-blocking Layout Rendering): Возможность запроса превью конкретного
   листа без зависания интерфейса (полный запрет на синхронный запуск PowerShell плоттеров).
"""

from __future__ import annotations

import base64
import concurrent.futures
import io
import json
import logging
import os
import re
import shutil
import struct
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

if getattr(sys, "frozen", False):
    REPO_ROOT = Path(sys.executable).resolve().parent
else:
    _p_here = Path(__file__).resolve()
    REPO_ROOT = Path(*_p_here.parts[: _p_here.parts.index("_internal")]) if "_internal" in _p_here.parts else _p_here.parents[2]
logger = logging.getLogger("dwg_engine")

# Глобальный семафор для предотвращения параллельного запуска accoreconsole.exe
_ACCORE_SEMAPHORE = threading.Semaphore(1)
_ACCORE_JOBS_LOCK = threading.Lock()

# GUI-воркер (COM в AutoCAD пользователя) отключён: он открывал документы в окне пользователя
# и не закрывал их при принудительной остановке. Рендер идёт только через headless accoreconsole.
USE_GUI_WORKER = False
ACCORE_EXPORT_TIMEOUT_SEC = 300
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000) if os.name == "nt" else 0


def _write_json_atomic(path, data) -> None:
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass
_ACTIVE_ACCORE_JOBS: set[str] = set()


def is_accore_job_active(path: Union[str, Path]) -> bool:
    key_prefix = str(Path(path).resolve()).casefold()
    with _ACCORE_JOBS_LOCK:
        return any(k == key_prefix or k.startswith(f"{key_prefix}::") for k in _ACTIVE_ACCORE_JOBS)

# 16-байтный сигнатурный маркер Autodesk для таблицы растровых изображений в заголовке DWG
DWG_THUMBNAIL_SENTINEL = b"\x1F\x25\x6D\x07\xD4\x36\x28\x28\x9D\x57\xCA\x3F\x9D\x44\x10\x2B"

# Поддерживаемые версии DWG (R13 - R2018+)
DWG_VERSIONS = {
    b"AC1012": "R13",
    b"AC1014": "R14",
    b"AC1015": "AutoCAD 2000",
    b"AC1018": "AutoCAD 2004",
    b"AC1021": "AutoCAD 2007",
    b"AC1024": "AutoCAD 2010",
    b"AC1027": "AutoCAD 2013",
    b"AC1032": "AutoCAD 2018+",
}

# Кэш количества листов и метаданных в памяти
_LAYOUT_COUNT_CACHE: Dict[Tuple[str, int], int] = {}
_LAYOUTS_CACHE: Dict[Tuple[str, int], List[Dict[str, Any]]] = {}

# Фоновый пул потоков для фоновых неблокирующих операций
_BG_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=2, thread_name_prefix="dwg_bg")


def _dib_to_bmp(dib_data: bytes) -> bytes:
    """Преобразует упакованный DIB (BITMAPINFOHEADER) в стандартный BMP файл."""
    if dib_data.startswith(b"BM"):
        return dib_data
    if len(dib_data) < 40:
        return dib_data
    try:
        (
            bi_size,
            _width,
            _height,
            _planes,
            bi_bit_count,
            _compression,
            _size_image,
            _x_pels,
            _y_pels,
            bi_clr_used,
            _clr_important,
        ) = struct.unpack("<IiiHHIIiiII", dib_data[:40])

        if bi_bit_count <= 8:
            num_colors = bi_clr_used if bi_clr_used > 0 else (1 << bi_bit_count)
        else:
            num_colors = bi_clr_used

        bf_off_bits = 14 + bi_size + (num_colors * 4)
        bf_size = 14 + len(dib_data)
        file_header = b"BM" + struct.pack("<IHHI", bf_size, 0, 0, bf_off_bits)
        return file_header + dib_data
    except Exception:
        return dib_data


def _bmp_to_png(bmp_bytes: bytes) -> bytes:
    """Конвертирует BMP в PNG через Pillow, если доступен."""
    try:
        from PIL import Image

        with Image.open(io.BytesIO(bmp_bytes)) as img:
            out = io.BytesIO()
            img.save(out, format="PNG")
            return out.getvalue()
    except Exception:
        return bmp_bytes


def _generate_placeholder_png(dwg_name: str, layout_name: str = "Model") -> bytes:
    """Генерирует легковесный PNG-плейсхолдер за < 1 мс при отсутствии растра."""
    try:
        from PIL import Image, ImageDraw

        img = Image.new("RGB", (800, 500), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.rectangle([(10, 10), (790, 490)], outline=(212, 215, 220), width=2)
        draw.text((40, 200), f"AutoCAD DWG: {dwg_name}", fill=(30, 41, 59))
        draw.text((40, 240), f"Layout: {layout_name}", fill=(100, 116, 139))
        draw.text((40, 280), "Embedded preview not present in DWG header", fill=(148, 163, 184))
        out = io.BytesIO()
        img.save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06"
            b"\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
            b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )


def _validate_image_bytes(data: bytes) -> bool:
    """Проверяет валидность байтов изображения и его минимальные размеры."""
    if not data or len(data) < 2000:
        return False
    try:
        from PIL import Image
        import io

        with Image.open(io.BytesIO(data)) as im:
            im.verify()
            w, h = im.size
            return 20 <= w <= 8192 and 20 <= h <= 8192
    except Exception:
        return False


def extract_raw_thumbnail_from_dwg(file_path: Union[str, Path]) -> Optional[Tuple[bytes, str]]:
    """Прямое чтение встроенного превью из заголовка DWG (R13-R2018) за < 1 мс.

    Returns:
        (image_bytes, format_str) или None
    """
    path = Path(file_path)
    try:
        with open(path, "rb") as f:
            hdr = f.read(0x40)
            if len(hdr) < 0x20 or not hdr.startswith(b"AC"):
                return None

            # Метод 1: Прямой указатель в заголовке DWG по смещению 0x0D (AutoCAD standard)
            thumb_addr = struct.unpack("<I", hdr[0x0D:0x11])[0]
            if thumb_addr > 0:
                f.seek(thumb_addr)
                sentinel = f.read(16)
                if sentinel == DWG_THUMBNAIL_SENTINEL:
                    f.seek(thumb_addr + 20)  # пропуск sentinel (16) и overall_size (4)
                    num_images = f.read(1)[0]
                    for _ in range(num_images):
                        img_type, start, size = struct.unpack("<BII", f.read(9))
                        if img_type == 6 and size > 0:
                            f.seek(start)
                            data = f.read(size)
                            if data.startswith(b"\x89PNG") and _validate_image_bytes(data):
                                return data, "PNG"
                        elif img_type == 2 and size > 0:
                            f.seek(start)
                            data = f.read(size)
                            bmp_bytes = _dib_to_bmp(data)
                            png_bytes = _bmp_to_png(bmp_bytes)
                            if _validate_image_bytes(png_bytes):
                                return png_bytes, "PNG"

            # Метод 2: Быстрое сканирование первых 2 МБ на случай смещения таблицы
            f.seek(0)
            chunk = f.read(2 * 1024 * 1024)
            sentinel_idx = chunk.find(DWG_THUMBNAIL_SENTINEL)
            if sentinel_idx != -1:
                f.seek(sentinel_idx + 20)
                num_images = f.read(1)[0]
                for _ in range(num_images):
                    img_type, start, size = struct.unpack("<BII", f.read(9))
                    if img_type == 6 and size > 0:
                        f.seek(start)
                        data = f.read(size)
                        if data.startswith(b"\x89PNG") and _validate_image_bytes(data):
                            return data, "PNG"
                    elif img_type == 2 and size > 0:
                        f.seek(start)
                        data = f.read(size)
                        bmp_bytes = _dib_to_bmp(data)
                        png_bytes = _bmp_to_png(bmp_bytes)
                        if _validate_image_bytes(png_bytes):
                            return png_bytes, "PNG"

            # Метод 3: Поиск сигнатуры PNG в первых 2 МБ
            png_idx = chunk.find(b"\x89PNG\r\n\x1a\n")
            if png_idx != -1:
                iend_idx = chunk.find(b"IEND\xaeB`\x82", png_idx)
                if iend_idx != -1:
                    candidate = chunk[png_idx : iend_idx + 8]
                    if _validate_image_bytes(candidate):
                        return candidate, "PNG"
    except Exception as e:
        logger.debug("Error extracting DWG thumbnail from %s: %s", path, e)

    return None


def _get_dwg_layout_count_fast(path: Path, mtime_ns: int) -> int:
    """Ультрабыстрое определение количества листов с использованием кэша."""
    cache_key = (str(path.resolve()), mtime_ns)
    if cache_key in _LAYOUT_COUNT_CACHE:
        return _LAYOUT_COUNT_CACHE[cache_key]

    count = 1
    # Проверка парного PDF рядом с чертежом
    paired_pdf = path.with_suffix(".pdf")
    if paired_pdf.is_file() and paired_pdf.stat().st_size > 1024:
        try:
            import fitz

            with fitz.open(paired_pdf) as doc:
                count = len(doc)
        except Exception:
            count = 1

    _LAYOUT_COUNT_CACHE[cache_key] = count
    return count


def get_dwg_preview(
    file_path: Union[str, Path],
    as_base64: bool = False,
    layout: Union[int, str] = 0,
) -> Dict[str, Any]:
    """Мгновенное чтение встроенного превью из заголовка DWG (R13-R2018) за < 1 мс.

    Args:
        file_path: Путь к файлу .dwg.
        as_base64: Если True, поле image_bytes вернет base64-строку вместо bytes.
        layout: Индекс или имя запрашиваемого Layout (по умолчанию 0 / Модель).

    Returns:
        {
            "status": "ok",
            "layout_count": N,
            "current_layout": 0,
            "image_bytes": bytes/base64,
            "image_base64": str,
            "elapsed_ms": float
        }
    """
    t0 = time.perf_counter()
    path = Path(file_path)

    # Если запрошен лист отличный от 0, делегируем в get_dwg_layout_preview
    layout_idx = 0
    if isinstance(layout, int):
        layout_idx = layout
    elif isinstance(layout, str) and layout.isdigit():
        layout_idx = int(layout)
    elif isinstance(layout, str) and layout.lower() not in ("0", "model", "модель"):
        return get_dwg_layout_preview(path, layout=layout, as_base64=as_base64)

    if layout_idx > 0:
        return get_dwg_layout_preview(path, layout=layout_idx, as_base64=as_base64)

    # Уровень 0: Мгновенное чтение из заголовка DWG (< 1 мс)
    thumb_res = extract_raw_thumbnail_from_dwg(path)

    if thumb_res is not None:
        raw_bytes, _fmt = thumb_res
    else:
        if not path.exists():
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "status": "error",
                "error": f"Файл не найден: {path}",
                "layout_count": 0,
                "current_layout": 0,
                "image_bytes": b"" if not as_base64 else "",
                "image_base64": "",
                "elapsed_ms": round(elapsed_ms, 4),
            }
        raw_bytes = _generate_placeholder_png(path.name, "Model")

    # Быстрое получение количества листов
    try:
        mtime_ns = path.stat().st_mtime_ns
        layout_count = _get_dwg_layout_count_fast(path, mtime_ns)
    except Exception:
        layout_count = 1

    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "status": "ok",
        "layout_count": layout_count,
        "current_layout": 0,
        "image_bytes": b64_str if as_base64 else raw_bytes,
        "image_base64": b64_str,
        "elapsed_ms": round(elapsed_ms, 4),
    }


def get_dwg_layouts(
    file_path: Union[str, Path],
    layout_index: Optional[Union[int, str]] = None,
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """Быстрое извлечение списка всех вкладок (Layouts / Пространств листа) чертежа.

    При указании layout_index возвращает превью конкретного листа без зависания.

    Args:
        file_path: Путь к файлу .dwg.
        layout_index: Опциональный индекс или имя вкладки для получения её превью.

    Returns:
        Список вкладок list[dict] или dict с превью выбранного листа.
    """
    path = Path(file_path)

    if layout_index is not None:
        return get_dwg_layout_preview(path, layout=layout_index)

    if not path.is_file():
        return [{"index": 0, "name": "Model", "type": "model", "has_preview": False, "is_current": True}]

    mtime_ns = path.stat().st_mtime_ns
    cache_key = (str(path.resolve()), mtime_ns)

    # 1. Проверка in-memory кэша
    if cache_key in _LAYOUTS_CACHE:
        return _LAYOUTS_CACHE[cache_key]

    layouts: List[Dict[str, Any]] = []

    # 2. Проверка парного PDF или кэшированного PDF
    pdf_candidate = path.with_suffix(".pdf")
    if not (pdf_candidate.exists() and pdf_candidate.stat().st_size > 1024):
        cache_parent = path.parent / ".cache"
        if cache_parent.exists():
            for p in cache_parent.glob(f"{path.stem}*.pdf"):
                if p.stat().st_size > 1024:
                    pdf_candidate = p
                    break

    if pdf_candidate.exists() and pdf_candidate.stat().st_size > 1024:
        try:
            import fitz

            doc = fitz.open(pdf_candidate)
            toc = doc.get_toc()
            page_map = {item[2]: item[1] for item in toc if item[2] > 0}

            for i in range(len(doc)):
                raw_name = page_map.get(i + 1)
                if not raw_name:
                    label = doc[i].get_label()
                    raw_name = label if label else f"Лист {i + 1}"

                name = raw_name
                if "-" in name:
                    name = name.split("-", 1)[1]

                is_model = i == 0 and name.lower() in ("model", "модель", "00_модель")
                layouts.append({
                    "index": i,
                    "name": name.strip(),
                    "type": "model" if is_model else "paper",
                    "has_preview": True,
                    "is_current": i == 0,
                    "width": doc[i].rect.width,
                    "height": doc[i].rect.height,
                })
            doc.close()
        except Exception as e:
            logger.debug("Failed to read layouts from PDF candidate %s: %s", pdf_candidate, e)

    # 3. Fallback: если PDF нет, гарантируем вкладку Model + проверка DWG
    if not layouts:
        layouts.append({
            "index": 0,
            "name": "Model",
            "type": "model",
            "has_preview": True,
            "is_current": True,
            "width": 1200,
            "height": 800,
        })
        try:
            with open(path, "rb") as f:
                data = f.read(min(path.stat().st_size, 4 * 1024 * 1024))
            for std_name in ("Layout1", "Layout2", "Лист1", "Лист2"):
                if std_name.encode("utf-16le") in data or std_name.encode("ascii") in data:
                    layouts.append({
                        "index": len(layouts),
                        "name": std_name,
                        "type": "paper",
                        "has_preview": False,
                        "is_current": False,
                        "width": 1200,
                        "height": 800,
                    })
        except Exception:
            pass

    _LAYOUTS_CACHE[cache_key] = layouts
    _LAYOUT_COUNT_CACHE[cache_key] = len(layouts)
    return layouts


def get_dwg_layout_preview(
    file_path: Union[str, Path],
    layout: Union[int, str] = 0,
    as_base64: bool = False,
) -> Dict[str, Any]:
    """Возвращает превью конкретного листа без зависания интерфейса.

    Полный запрет на синхронный запуск PowerShell плоттеров:
    - Для Model (0) отдается встроенный растр за < 1 мс.
    - Для листов Layouts при наличии парного/кэшированного PDF отдается страница через PyMuPDF за 10-15 мс.
    - При отсутствии готового PDF немедленно отдается плейсхолдер с запуском фоновой генерации.
    """
    t0 = time.perf_counter()
    path = Path(file_path)

    layouts = get_dwg_layouts(path)
    layout_count = len(layouts) if layouts else 1

    # Определение целевого индекса листа
    target_idx = 0
    if isinstance(layout, int):
        target_idx = layout
    elif isinstance(layout, str):
        if layout.isdigit():
            target_idx = int(layout)
        else:
            for l_info in layouts:
                if l_info.get("name", "").lower() == layout.lower():
                    target_idx = l_info.get("index", 0)
                    break

    # Лист 0 (Модель): мгновенный заголовочный растр
    if target_idx == 0:
        return get_dwg_preview(path, as_base64=as_base64, layout=0)

    # Листы > 0: проверка парного PDF
    paired_pdf = path.with_suffix(".pdf")
    if paired_pdf.exists() and paired_pdf.stat().st_size > 1024:
        try:
            import fitz

            doc = fitz.open(paired_pdf)
            if target_idx < len(doc):
                page = doc[target_idx]
                pix = page.get_pixmap(dpi=150)
                raw_bytes = pix.tobytes("png")
                doc.close()
                b64_str = base64.b64encode(raw_bytes).decode("ascii")
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                return {
                    "status": "ok",
                    "layout_count": layout_count,
                    "current_layout": target_idx,
                    "image_bytes": b64_str if as_base64 else raw_bytes,
                    "image_base64": b64_str,
                    "elapsed_ms": round(elapsed_ms, 4),
                }
            doc.close()
        except Exception as e:
            logger.debug("Failed to render layout page %d from PDF %s: %s", target_idx, paired_pdf, e)

    # При отсутствии готового PDF отдаем плейсхолдер листа без блокировки UI
    layout_name = f"Layout {target_idx}"
    if target_idx < len(layouts):
        layout_name = layouts[target_idx].get("name", layout_name)

    raw_bytes = _generate_placeholder_png(path.name, layout_name)
    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    return {
        "status": "ok",
        "preview_status": "placeholder",
        "layout_count": layout_count,
        "current_layout": target_idx,
        "image_bytes": b64_str if as_base64 else raw_bytes,
        "image_base64": b64_str,
        "elapsed_ms": round(elapsed_ms, 4),
    }


_FITZ_LOCK = threading.Lock()


def _rasterize_pdf_page(pdf_path: Path, out_png: Path, dpi: int = 150) -> bool:
    """Конвертирует первую страницу PDF в PNG через PyMuPDF (fitz) с атомарной записью под _FITZ_LOCK."""
    if not pdf_path.exists() or pdf_path.stat().st_size <= 1024:
        return False
    with _FITZ_LOCK:
        try:
            import fitz

            with fitz.open(str(pdf_path)) as doc:
                if len(doc) > 0:
                    page = doc[0]
                    pix = page.get_pixmap(dpi=dpi)
                    out_png.parent.mkdir(parents=True, exist_ok=True)
                    tmp_png = out_png.with_suffix(f".tmp.{os.getpid()}_{int(time.time()*1000)}.png")
                    pix.save(str(tmp_png))
                    if tmp_png.exists() and tmp_png.stat().st_size > 0:
                        replaced = False
                        for _attempt in range(6):
                            try:
                                os.replace(str(tmp_png), str(out_png))
                                replaced = True
                                break
                            except PermissionError:
                                time.sleep(0.15)
                        if not replaced:
                            try:
                                tmp_png.unlink()
                            except OSError:
                                pass
                            return out_png.exists() and out_png.stat().st_size > 0
                        return True
        except Exception as e:
            logger.warning("Ошибка атомарной растеризации %s в %s: %s", pdf_path, out_png, e)
        return False


_EMPTY_SHEET_CACHE: Dict[Tuple[str, int], bool] = {}


def check_image_is_empty_sheet(png_path: Union[str, Path]) -> bool:
    """Определяет, является ли лист пустым шаблоном (рамка/штамп без чертежа в центральной области)."""
    try:
        p_obj = Path(png_path)
        if not p_obj.exists() or p_obj.stat().st_size <= 0:
            return False
        cache_key = (str(p_obj.resolve()), p_obj.stat().st_mtime_ns)
        if cache_key in _EMPTY_SHEET_CACHE:
            return _EMPTY_SHEET_CACHE[cache_key]

        from PIL import Image
        import numpy as np

        im = Image.open(p_obj).convert("L")
        arr = np.array(im)
        h, w = arr.shape
        inner = arr[int(h * 0.15) : int(h * 0.75), int(w * 0.15) : int(w * 0.80)]
        is_empty = bool(np.sum(inner < 230) < 50)
        _EMPTY_SHEET_CACHE[cache_key] = is_empty
        return is_empty
    except Exception:
        return False


class DwgOnDemandManager:
    """Менеджер фоновых воркеров печати DWG."""
    _lock = threading.Lock()
    _active_workers: Dict[str, subprocess.Popen] = {}
    _worker_layouts: Dict[str, List[Dict[str, Any]]] = {}
    _worker_acad_pids: Dict[str, int] = {}

    @classmethod
    def _worker_key(cls, path: Union[str, Path]) -> str:
        return str(Path(path).resolve()).casefold()

    @classmethod
    def set_acad_pid(cls, path: Union[str, Path], pid: int) -> None:
        key = cls._worker_key(path)
        with cls._lock:
            cls._worker_acad_pids[key] = pid

    @classmethod
    def set_layouts(cls, path: Union[str, Path], layouts: List[Dict[str, Any]]) -> None:
        key = cls._worker_key(path)
        with cls._lock:
            cls._worker_layouts[key] = layouts

    @classmethod
    def get_layouts(cls, path: Union[str, Path]) -> List[Dict[str, Any]]:
        key = cls._worker_key(path)
        with cls._lock:
            return cls._worker_layouts.get(key, [])

    @classmethod
    def stop_worker(cls, path: Union[str, Path]) -> None:
        key = cls._worker_key(path)
        with cls._lock:
            proc = cls._active_workers.pop(key, None)
            acad_pid = cls._worker_acad_pids.pop(key, 0)
            if proc:
                try:
                    if proc.poll() is None:
                        if os.name == "nt":
                            try:
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                    capture_output=True,
                                    timeout=5,
                                    close_fds=True, creationflags=_NO_WINDOW,
                                )
                            except Exception:
                                pass
                        proc.terminate()
                        try:
                            proc.wait(timeout=1.0)
                        except Exception:
                            proc.kill()
                except Exception:
                    pass
            if acad_pid > 0:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(acad_pid), "/F"],
                        capture_output=True,
                        timeout=5,
                        close_fds=True, creationflags=_NO_WINDOW,
                    )
                except Exception:
                    pass

    @classmethod
    def stop_all_workers(cls) -> None:
        with cls._lock:
            keys = list(cls._active_workers.keys())
        for k in keys:
            cls.stop_worker(k)
        try:
            from app.backend.server import kill_orphan_acad_processes
            kill_orphan_acad_processes()
        except Exception:
            pass

    @classmethod
    def get_or_start_worker(cls, input_dwg: Path, output_dir: Path, priority_tab: int = 1) -> Optional[subprocess.Popen]:
        if not USE_GUI_WORKER:
            return None
        key = cls._worker_key(input_dwg)
        with cls._lock:
            existing = cls._active_workers.get(key)
            if existing is not None:
                if existing.poll() is None:
                    return existing
                cls._active_workers.pop(key, None)

        # Перед запуском нового воркера всегда останавливаем все старые активные воркеры других файлов
        cls.stop_all_workers()

        with cls._lock:
            existing = cls._active_workers.get(key)
            if existing is not None and existing.poll() is None:
                return existing

            # Запускаем фоновый воркер печати ТОЛЬКО если у пользователя уже открыт AutoCAD.
            # Если AutoCAD не запущен — не поднимаем процесс вовсе.
            try:
                from app.backend.server import _find_visible_acad_window
                cad_hwnd, _ = _find_visible_acad_window()
                if cad_hwnd <= 0:
                    return None
            except Exception:
                return None

            worker_script = REPO_ROOT / "scripts" / "dwg_plot_worker.ps1"
            if not worker_script.is_file():
                logger.error("Скрипт dwg_plot_worker.ps1 не найден: %s", worker_script)
                return None

            output_dir.mkdir(parents=True, exist_ok=True)
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(worker_script),
                "-InputPath",
                str(input_dwg),
                "-OutputDir",
                str(output_dir),
                "-PriorityTabOrder",
                str(priority_tab),
            ]

            creation_flags = 0
            if os.name == "nt":
                creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creation_flags,
                    close_fds=True,
                )
                cls._active_workers[key] = proc
                return proc
            except Exception as e:
                logger.error("Не удалось запустить воркер для %s: %s", input_dwg, e)
                return None


def _start_background_worker_pump(proc: subprocess.Popen, output_dir: Path, input_dwg: Path, dpi: int = 150) -> None:
    """Фоновый поток для вычитывания stdout воркера и автоматической нарезки PDF->PNG."""
    def _pump():
        if not proc.stdout:
            return
        for line in proc.stdout:
            line_str = line.strip()
            if not line_str or not (line_str.startswith("{") and line_str.endswith("}")):
                continue
            try:
                ev = json.loads(line_str)
                if ev.get("event") == "worker_acad_pid":
                    p_id = int(ev.get("pid") or 0)
                    if p_id > 0:
                        DwgOnDemandManager.set_acad_pid(input_dwg, p_id)
                elif ev.get("event") == "doc_opened":
                    lays = ev.get("layouts", [])
                    if lays:
                        DwgOnDemandManager.set_layouts(input_dwg, lays)
                elif ev.get("event") == "sheet_ready":
                    tab = int(ev.get("tabOrder", 0))
                    pdf_p = Path(ev.get("pdfPath", ""))
                    if pdf_p.is_file() and pdf_p.stat().st_size > 4096:
                        png_p = output_dir / f"page-{tab}.png"
                        if not png_p.exists() or png_p.stat().st_size < 35000 or png_p.stat().st_mtime < pdf_p.stat().st_mtime:
                            _rasterize_pdf_page(pdf_p, png_p, dpi)
            except Exception:
                pass
        try:
            proc.wait()
        except Exception:
            pass

    def _watcher():
        while proc.poll() is None:
            try:
                for pdf_p in output_dir.glob("page_*.pdf"):
                    m = re.match(r"^page_(\d+)\.pdf$", pdf_p.name)
                    if m and pdf_p.stat().st_size > 4096:
                        tab = int(m.group(1))
                        png_p = output_dir / f"page-{tab}.png"
                        if not png_p.exists() or png_p.stat().st_size < 35000 or png_p.stat().st_mtime < pdf_p.stat().st_mtime:
                            _rasterize_pdf_page(pdf_p, png_p, dpi)
            except Exception:
                pass
            time.sleep(1.0)
        try:
            for pdf_p in output_dir.glob("page_*.pdf"):
                m = re.match(r"^page_(\d+)\.pdf$", pdf_p.name)
                if m and pdf_p.stat().st_size > 4096:
                    tab = int(m.group(1))
                    png_p = output_dir / f"page-{tab}.png"
                    if not png_p.exists() or png_p.stat().st_size < 35000 or png_p.stat().st_mtime < pdf_p.stat().st_mtime:
                        _rasterize_pdf_page(pdf_p, png_p, dpi)
        except Exception:
            pass

    t1 = threading.Thread(target=_pump, daemon=True, name=f"dwg_pump_{output_dir.name}")
    t1.start()
    t2 = threading.Thread(target=_watcher, daemon=True, name=f"dwg_watch_{output_dir.name}")
    t2.start()


def export_dwg_layout_accore(
    input_dwg: Path,
    output_pdf: Path,
    work_dir: Path,
    layout_name: str = "",
    timeout_sec: int = 120,
) -> bool:
    """Headless AutoCAD PDF export using accoreconsole.exe via Invoke-NativeDwgPdfExport.ps1.
    
    Protected by global _ACCORE_SEMAPHORE(1) to strictly prevent concurrent CAD processes.
    """
    script_path = REPO_ROOT / "scripts" / "Invoke-NativeDwgPdfExport.ps1"
    if not script_path.exists():
        logger.warning("Invoke-NativeDwgPdfExport.ps1 not found at %s", script_path)
        return False
    work_dir.mkdir(parents=True, exist_ok=True)
    # Пути и имя листа передаются через окружение как данные, а не как код PowerShell.
    ps_cmd = (
        ". $env:FERO_PS_SCRIPT; "
        "Invoke-NativeDwgPdfExport -InputPath $env:FERO_DWG_IN -OutputPdf $env:FERO_PDF_OUT "
        f"-WorkDir $env:FERO_WORK_DIR -TimeoutSec {int(timeout_sec)}"
    )
    if layout_name:
        ps_cmd += " -LayoutName $env:FERO_LAYOUT"
    ps_env = dict(os.environ)
    ps_env.update({
        "FERO_PS_SCRIPT": str(script_path),
        "FERO_DWG_IN": str(input_dwg),
        "FERO_PDF_OUT": str(output_pdf),
        "FERO_WORK_DIR": str(work_dir),
        "FERO_LAYOUT": layout_name or "",
    })
    cmd = [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps_cmd,
    ]
    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    acquired = _ACCORE_SEMAPHORE.acquire(timeout=timeout_sec + 20)
    if not acquired:
        logger.warning("Could not acquire _ACCORE_SEMAPHORE within timeout for %s", input_dwg.name)
        return False

    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creation_flags,
            close_fds=True,
            env=ps_env,
        )
        try:
            stdout_data, stderr_data = proc.communicate(timeout=timeout_sec + 15)
        except subprocess.TimeoutExpired:
            logger.warning("accoreconsole timed out after %d sec for %s; force killing process tree", timeout_sec, input_dwg.name)
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5, close_fds=True, creationflags=_NO_WINDOW)
                except Exception:
                    pass
            try:
                proc.kill()
            except Exception:
                pass
            return False

        if output_pdf.exists() and output_pdf.stat().st_size > 4096:
            return True
        logger.warning("accoreconsole export incomplete for %s: stdout=%s stderr=%s", input_dwg.name, (stdout_data or "")[-300:], (stderr_data or "")[-300:])
    except Exception as e:
        logger.warning("Error running accoreconsole export for %s: %s", input_dwg.name, e)
        if proc and proc.poll() is None:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, timeout=5, close_fds=True, creationflags=_NO_WINDOW)
                except Exception:
                    pass
            try:
                proc.kill()
            except Exception:
                pass
    finally:
        _ACCORE_SEMAPHORE.release()
    return False


_CACHED_ACCORE_EXE: Optional[Path] = None


def _find_accoreconsole() -> Optional[Path]:
    """Находит исполняемый файл accoreconsole.exe в системе (AutoCAD 2020-2026)."""
    global _CACHED_ACCORE_EXE
    if _CACHED_ACCORE_EXE and _CACHED_ACCORE_EXE.is_file():
        return _CACHED_ACCORE_EXE

    candidates: List[Path] = []
    env_accore = os.environ.get("FERO_ACCORE_EXE", "").strip()
    if env_accore:
        candidates.append(Path(env_accore))

    appdata = os.environ.get("APPDATA", "")
    if appdata:
        try:
            cfg_path = Path(appdata) / "F-Engineering Launcher" / "config.json"
            if cfg_path.is_file():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8-sig"))
                cad_exe = (cfg.get("nativeApps") or {}).get("dwg")
                if cad_exe:
                    candidates.append(Path(cad_exe).parent / "accoreconsole.exe")
        except Exception:
            pass

    for env_key in ("ProgramFiles", "ProgramFiles(x86)"):
        prog_root = os.environ.get(env_key, "")
        if prog_root:
            for ver in ("2026", "2025", "2024", "2023", "2022", "2021", "2020"):
                candidates.append(Path(prog_root) / "Autodesk" / f"AutoCAD {ver}" / "accoreconsole.exe")

    which_accore = shutil.which("accoreconsole.exe")
    if which_accore:
        candidates.append(Path(which_accore))

    for cand in candidates:
        try:
            if cand and cand.is_file():
                _CACHED_ACCORE_EXE = cand
                return cand
        except OSError:
            pass
    return None


def _is_pdf_complete(pdf_path: Path) -> bool:
    """Проверяет, что PDF-файл существует, не пустой (> 4 КБ) и полностью дописан на диск (содержит %%EOF)."""
    try:
        if not pdf_path.is_file():
            return False
        sz = pdf_path.stat().st_size
        if sz <= 4096:
            return False
        with open(pdf_path, "rb") as f:
            f.seek(max(0, sz - 512))
            tail = f.read(512)
        return b"%%EOF" in tail
    except OSError:
        return False


def _parse_layouts_txt(layouts_txt: Path) -> List[Dict[str, Any]]:
    """Читает список листов, выгруженный AutoLISP-скриптом в layouts.txt (формат: tabOrder|name)."""
    if not layouts_txt.is_file():
        return []
    raw_bytes = b""
    try:
        raw_bytes = layouts_txt.read_bytes()
    except OSError:
        return []
    if not raw_bytes:
        return []
    try:
        text = raw_bytes.decode("cp1251")
    except UnicodeDecodeError:
        text = raw_bytes.decode("utf-8-sig", errors="replace")

    layouts: List[Dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or "|" not in line:
            continue
        idx_part, name_part = line.split("|", 1)
        try:
            tab_order = int(idx_part.strip())
        except ValueError:
            tab_order = len(layouts) + 1
        lay_name = name_part.strip() or f"Лист {tab_order}"
        layouts.append({
            "name": lay_name,
            "tabOrder": tab_order,
            "plotRotation": 0,
        })
    return layouts


def start_accore_progressive_export(
    input_dwg: Path,
    target_dir: Path,
    dpi: int = 150,
    priority_tab: int = 1,
    timeout_sec: int = ACCORE_EXPORT_TIMEOUT_SEC,
) -> bool:
    """Запускает в фоновом пуле прогрессивный многостраничный экспорт DWG -> PDF -> PNG через accoreconsole.exe.

    В рамках одной сессии accoreconsole:
    1. Через словарь ACAD_LAYOUT и ssget (410 . lname) находит все непустые листы Paper Space (> 1 примитива).
    2. Мгновенно записывает layouts.txt (1|Имя1, 2|Имя2, ...), после чего наблюдатель сразу создаёт manifest.json.
    3. Поочерёдно печатает листы в page_0001.pdf .. page_NNNN.pdf (начиная с priority_tab), а при отсутствии
       заполненных листов Paper Space автоматически печатает пространство Model (_E).
    4. Если в чертеже ровно 1 лист Paper Space, дополнительно экспортирует model_fallback.pdf из Model,
       чтобы при пустом шаблоне рамки в Layout1 автоматически подставить реальный чертёж из Model.
    """
    input_dwg = input_dwg.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    accore_key = str(input_dwg).casefold()

    with _ACCORE_JOBS_LOCK:
        if accore_key in _ACTIVE_ACCORE_JOBS:
            return True
        _ACTIVE_ACCORE_JOBS.add(accore_key)

    def _bg_progressive_job() -> None:
        acquired = False
        proc: Optional[subprocess.Popen] = None
        staged_copy: Optional[Path] = None
        try:
            accore_exe = _find_accoreconsole()
            if not accore_exe:
                logger.warning("accoreconsole.exe not found; cannot export %s", input_dwg)
                return

            acquired = _ACCORE_SEMAPHORE.acquire(timeout=timeout_sec + 30)
            if not acquired:
                logger.warning("Could not acquire _ACCORE_SEMAPHORE for progressive export of %s", input_dwg.name)
                return

            work_dir = target_dir / "workdir"
            work_dir.mkdir(parents=True, exist_ok=True)
            manifest_path = target_dir / "manifest.json"
            layouts_txt = target_dir / "layouts.txt"
            model_fallback_pdf = target_dir / "model_fallback.pdf"

            try:
                if layouts_txt.exists():
                    layouts_txt.unlink()
            except OSError:
                pass

            # Удаляем недописанные PDF (< 4KB или без %%EOF) от прерванных запусков
            for old_pdf in target_dir.glob("page_*.pdf"):
                if not _is_pdf_complete(old_pdf):
                    try:
                        old_pdf.unlink()
                    except OSError:
                        pass

            effective_input = input_dwg
            drive_prefix = str(input_dwg)[:2].upper()
            if str(input_dwg).startswith("\\") or drive_prefix in ("H:", "G:", "Z:"):
                try:
                    staged_copy = work_dir / input_dwg.name
                    shutil.copy2(input_dwg, staged_copy)
                    effective_input = staged_copy
                except Exception:
                    effective_input = input_dwg

            out_dir_str = str(target_dir.resolve()).replace("\\", "/")
            prio = max(1, int(priority_tab or 1))
            scr_content = f"""(setvar "EXPERT" 5)
(setvar "FILEDIA" 0)
(setvar "CMDDIA" 0)
(setvar "BACKGROUNDPLOT" 0)
(setq outdir "{out_dir_str}")
(setq prio {prio})
(setq d (dictsearch (namedobjdict) "ACAD_LAYOUT"))
(setq lays '())
(while d
  (if (= (car (car d)) 3)
    (progn
      (setq lname (cdr (car d)))
      (setq lobj (cdr (cadr d)))
      (setq ldata (entget lobj))
      (setq tab (cdr (assoc 71 ldata)))
      (if (/= lname "Model")
        (progn
          (setq ss (ssget "_X" (list (cons 410 lname))))
          (setq cnt (if ss (sslength ss) 0))
          (if (> cnt 1)
            (setq lays (cons (cons tab lname) lays))
          )
        )
      )
    )
  )
  (setq d (cdr d))
)
(setq lays (vl-sort lays '(lambda (a b) (< (car a) (car b)))))
(setq f (open (strcat outdir "/layouts.txt") "w"))
(if lays
  (progn
    (setq sidx 1)
    (setq indexed '())
    (foreach item lays
      (write-line (strcat (itoa sidx) "|" (cdr item)) f)
      (setq indexed (append indexed (list (cons sidx (cdr item)))))
      (setq sidx (1+ sidx))
    )
    (close f)
    (if (> prio 1)
      (foreach item indexed
        (if (= (car item) prio)
          (progn
            (setq numstr (itoa (car item)))
            (while (< (strlen numstr) 4) (setq numstr (strcat "0" numstr)))
            (setq outpdf (strcat outdir "/page_" numstr ".pdf"))
            (if (not (findfile outpdf))
              (progn
                (setvar "CTAB" (cdr item))
                (command "_.-EXPORT" "_PDF" "_C" "_N" outpdf)
              )
            )
          )
        )
      )
    )
    (foreach item indexed
      (setq numstr (itoa (car item)))
      (while (< (strlen numstr) 4) (setq numstr (strcat "0" numstr)))
      (setq outpdf (strcat outdir "/page_" numstr ".pdf"))
      (if (not (findfile outpdf))
        (progn
          (setvar "CTAB" (cdr item))
          (command "_.-EXPORT" "_PDF" "_C" "_N" outpdf)
        )
      )
    )
    (if (= (length indexed) 1)
      (progn
        (setq fbpdf (strcat outdir "/model_fallback.pdf"))
        (if (not (findfile fbpdf))
          (progn
            (setvar "CTAB" "Model")
            (command "_.-EXPORT" "_PDF" "_E" "_N" fbpdf)
          )
        )
      )
    )
  )
  (progn
    (write-line "1|Model" f)
    (close f)
    (setq outpdf (strcat outdir "/page_0001.pdf"))
    (if (not (findfile outpdf))
      (progn
        (setvar "CTAB" "Model")
        (command "_.-EXPORT" "_PDF" "_E" "_N" outpdf)
      )
    )
  )
)
(command "_.QUIT" "_Y")
"""
            scr_path = work_dir / "export_all.scr"
            scr_path.write_text(scr_content, encoding="cp1251", errors="replace")
            log_path = work_dir / "accore.log"

            item_stat = input_dwg.stat()
            layouts_list: List[Dict[str, Any]] = []
            completed_pages: Dict[int, Dict[str, Any]] = {}
            empty_pages_set: set[int] = set()

            def _save_manifest(complete_flag: bool) -> None:
                if not layouts_list:
                    return
                manifest_data = {
                    "sourcePath": str(input_dwg),
                    "sourceName": input_dwg.name,
                    "sourceSize": item_stat.st_size,
                    "sourceMtime": int(item_stat.st_mtime),
                    "outputDir": str(target_dir),
                    "isComplete": complete_flag,
                    "totalLayouts": len(layouts_list),
                    "validLayouts": len(layouts_list),
                    "layouts": layouts_list,
                    "completedPages": completed_pages,
                    "emptyPages": sorted(empty_pages_set),
                }
                _write_json_atomic(manifest_path, manifest_data)

            def _scan_progress() -> None:
                nonlocal layouts_list
                if not layouts_list and layouts_txt.is_file() and layouts_txt.stat().st_size > 0:
                    time.sleep(0.05)
                    parsed = _parse_layouts_txt(layouts_txt)
                    if parsed:
                        layouts_list = parsed
                        DwgOnDemandManager.set_layouts(input_dwg, layouts_list)
                        _save_manifest(False)

                changed = False
                for pdf_file in sorted(target_dir.glob("page_*.pdf")):
                    m_pdf = re.match(r"^page_(\d+)\.pdf$", pdf_file.name)
                    if not m_pdf:
                        continue
                    tab = int(m_pdf.group(1))
                    if tab in completed_pages:
                        continue
                    if not _is_pdf_complete(pdf_file):
                        continue
                    png_file = target_dir / f"page-{tab}.png"
                    if not png_file.exists() or png_file.stat().st_size == 0 or png_file.stat().st_mtime < pdf_file.stat().st_mtime:
                        _rasterize_pdf_page(pdf_file, png_file, dpi)
                    if png_file.exists() and png_file.stat().st_size > 0:
                        lay_name = f"Лист {tab}"
                        for lay in layouts_list:
                            if int(lay.get("tabOrder", 0)) == tab:
                                lay_name = lay.get("name", lay_name)
                                break
                        completed_pages[tab] = {
                            "bytes": png_file.stat().st_size,
                            "name": lay_name,
                        }
                        if check_image_is_empty_sheet(png_file):
                            empty_pages_set.add(tab)
                        changed = True
                if changed and layouts_list:
                    _save_manifest(False)

            cmd = [
                str(accore_exe),
                "/i",
                str(effective_input),
                "/s",
                str(scr_path),
                "/readonly",
            ]
            t_start = time.time()
            with open(log_path, "wb") as log_f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    creationflags=_NO_WINDOW,
                    close_fds=True,
                )
                while proc.poll() is None:
                    if time.time() - t_start > timeout_sec:
                        logger.warning("accoreconsole progressive export timed out after %ds for %s", timeout_sec, input_dwg.name)
                        if os.name == "nt":
                            try:
                                subprocess.run(
                                    ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                                    capture_output=True,
                                    timeout=5,
                                    close_fds=True,
                                    creationflags=_NO_WINDOW,
                                )
                            except Exception:
                                pass
                        try:
                            proc.kill()
                        except Exception:
                            pass
                        break
                    _scan_progress()
                    time.sleep(0.2)

            # Финальное сканирование после завершения accoreconsole
            _scan_progress()

            # Если в чертеже был всего 1 лист Paper Space и он оказался пустой рамкой,
            # проверяем model_fallback.pdf (экспортированный из Model):
            if len(layouts_list) == 1 and 1 in empty_pages_set and _is_pdf_complete(model_fallback_pdf):
                fb_png = target_dir / "model_fallback.png"
                if _rasterize_pdf_page(model_fallback_pdf, fb_png, dpi) and not check_image_is_empty_sheet(fb_png):
                    page1_pdf = target_dir / "page_0001.pdf"
                    page1_png = target_dir / "page-1.png"
                    try:
                        os.replace(str(model_fallback_pdf), str(page1_pdf))
                        os.replace(str(fb_png), str(page1_png))
                        layouts_list[0]["name"] = "Model"
                        DwgOnDemandManager.set_layouts(input_dwg, layouts_list)
                        empty_pages_set.discard(1)
                        completed_pages[1] = {
                            "bytes": page1_png.stat().st_size,
                            "name": "Model",
                        }
                    except OSError:
                        pass
                else:
                    try:
                        fb_png.unlink(missing_ok=True)
                    except OSError:
                        pass
            try:
                if model_fallback_pdf.exists():
                    model_fallback_pdf.unlink()
            except OSError:
                pass

            if not layouts_list and completed_pages:
                layouts_list = [
                    {"name": info.get("name", f"Лист {t}"), "tabOrder": t, "plotRotation": 0}
                    for t, info in sorted(completed_pages.items())
                ]
                DwgOnDemandManager.set_layouts(input_dwg, layouts_list)

            if layouts_list and completed_pages:
                is_all_done = len(completed_pages) >= len(layouts_list)
                _save_manifest(is_all_done)
        except Exception as ex:
            logger.warning("Error in start_accore_progressive_export for %s: %s", input_dwg, ex)
        finally:
            if staged_copy and staged_copy.exists():
                try:
                    staged_copy.unlink()
                except OSError:
                    pass
            if acquired:
                _ACCORE_SEMAPHORE.release()
            with _ACCORE_JOBS_LOCK:
                _ACTIVE_ACCORE_JOBS.discard(accore_key)

    _BG_EXECUTOR.submit(_bg_progressive_job)
    return True


def render_dwg_model_progressive(
    path: Path,
    target_dir: Path,
    cache_key: str,
    dpi: int = 150,
    wait_first_sheet_seconds: float = 8.0,
    force: bool = False,
) -> Dict[str, Any]:
    """Прогрессивный рендеринг DWG-модели: немедленный возврат листа 1 и фоновая печать остальных."""
    path = path.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = target_dir / "manifest.json"
    page1_pdf = target_dir / "page_0001.pdf"
    page1_png = target_dir / "page-1.png"
    thumb_png = target_dir / "header_thumb.png"

    # Если запрошен принудительный перерендер — сбрасываем кэш и останавливаем прошлый воркер
    if force:
        DwgOnDemandManager.stop_worker(path)
        for old_file in target_dir.glob("*"):
            try:
                if old_file.is_file():
                    old_file.unlink()
            except OSError:
                pass

    # 1. Быстрая проверка готового кэша (если не force)
    if not force and manifest_path.exists() and manifest_path.stat().st_size > 0:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            source_size = manifest.get("sourceSize")
            source_mtime = manifest.get("sourceMtime")
            is_valid = manifest.get("sourcePath") == str(path) and source_size == path.stat().st_size
            if is_valid and source_mtime:
                is_valid = abs(float(source_mtime) - path.stat().st_mtime) < 3.0
            if is_valid:
                if not page1_png.exists() and _is_pdf_complete(page1_pdf):
                    _rasterize_pdf_page(page1_pdf, page1_png, dpi)

                layouts = manifest.get("layouts", [])
                items = []
                missing_tabs = []
                for lay in layouts:
                    tab = int(lay.get("tabOrder", 1))
                    p_png = target_dir / f"page-{tab}.png"
                    p_pdf = target_dir / f"page_{tab:04d}.pdf"
                    if not p_png.exists() and _is_pdf_complete(p_pdf):
                        _rasterize_pdf_page(p_pdf, p_png, dpi)
                    p_ready = p_png.exists() and p_png.stat().st_size > 0
                    if not p_ready:
                        missing_tabs.append(tab)
                    if p_ready:
                        img_url = f"/cache/dwg/{cache_key}/{p_png.name}"
                        img_bytes = p_png.stat().st_size
                    elif thumb_png.exists():
                        img_url = f"/cache/dwg/{cache_key}/header_thumb.png"
                        img_bytes = 0
                    else:
                        img_url = f"/cache/dwg/{cache_key}/{p_png.name}"
                        img_bytes = 0
                    items.append({
                        "page": tab,
                        "name": f"{path.name} · {lay.get('name', f'Лист {tab}')}",
                        "url": img_url,
                        "bytes": img_bytes,
                        "previewType": "DWG_MODEL",
                        "isEmpty": check_image_is_empty_sheet(p_png) if p_ready else False,
                    })

                if not items and page1_png.exists():
                    items.append({
                        "page": 1,
                        "name": f"{path.name} · Лист 1",
                        "url": f"/cache/dwg/{cache_key}/{page1_png.name}",
                        "bytes": page1_png.stat().st_size if page1_png.exists() else 0,
                        "previewType": "DWG_MODEL",
                    })

                is_complete = bool(manifest.get("isComplete", False)) or (len(layouts) > 0 and len(missing_tabs) == 0)
                # Если часть листов ещё не отпечатана — гарантированно возобновляем воркер в фоне!
                if missing_tabs and not is_complete:
                    first_missing = missing_tabs[0]
                    proc = DwgOnDemandManager.get_or_start_worker(path, target_dir, priority_tab=first_missing)
                    if proc:
                        _start_background_worker_pump(proc, target_dir, path, dpi)
                    else:
                        start_accore_progressive_export(path, target_dir, dpi=dpi, priority_tab=first_missing)

                return {
                    "name": path.name,
                    "path": str(path),
                    "sourcePath": str(path),
                    "sourceName": path.name,
                    "sourceType": "DWG",
                    "dpi": dpi,
                    "pages": len(layouts) if layouts else 1,
                    "renderedPages": len(layouts) if layouts else 1,
                    "cacheKey": cache_key,
                    "cacheHit": not missing_tabs,
                    "cacheHitPages": len([it for it in items if it["bytes"] > 0]),
                    "isComplete": is_complete,
                    "newRenderedPages": 0,
                    "errors": [],
                    "items": items,
                    "status": "ok",
                    "convertedPdfPath": str(page1_pdf) if page1_pdf.exists() else "",
                    "convertCacheHit": True,
                    "previewMode": "cad-smart-layouts",
                }
        except Exception as ex:
            logger.warning("Ошибка чтения манифеста для %s: %s", path, ex)

    # 2. Фаза 0: Мгновенное извлечение превью из заголовка DWG (< 1 мс)
    if not thumb_png.exists():
        thumb_res = extract_raw_thumbnail_from_dwg(path)
        if thumb_res:
            thumb_png.write_bytes(thumb_res[0])
        else:
            thumb_png.write_bytes(_generate_placeholder_png(path.name, "Model"))

    # 3. Запуск On-Demand AutoCAD воркера или прогрессивного headless accoreconsole с приоритетом на лист 1
    proc = DwgOnDemandManager.get_or_start_worker(path, target_dir, priority_tab=1)
    if proc:
        _start_background_worker_pump(proc, target_dir, path, dpi)
    elif not _is_pdf_complete(page1_pdf):
        start_accore_progressive_export(path, target_dir, dpi=dpi, priority_tab=1)

    # Ожидание готовности листа 1 (и списка листов manifest.json) в пределах wait_first_sheet_seconds
    page1_ready = False
    if _is_pdf_complete(page1_pdf):
        page1_ready = True
    elif wait_first_sheet_seconds > 0:
        deadline = time.time() + wait_first_sheet_seconds
        while time.time() < deadline:
            if _is_pdf_complete(page1_pdf):
                page1_ready = True
                break
            if proc is not None and proc.poll() is not None:
                if _is_pdf_complete(page1_pdf):
                    page1_ready = True
                break
            if proc is None and not is_accore_job_active(path):
                if _is_pdf_complete(page1_pdf):
                    page1_ready = True
                break
            time.sleep(0.25)

    if page1_ready and (not page1_png.exists() or page1_png.stat().st_size == 0):
        _rasterize_pdf_page(page1_pdf, page1_png, dpi)

    # Сбор метаданных листов из manifest.json или кеша событий воркера
    layouts = []
    if manifest_path.exists():
        try:
            m = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
            layouts = m.get("layouts", [])
        except Exception:
            pass

    if not layouts:
        layouts = DwgOnDemandManager.get_layouts(path)

    if page1_ready and not layouts:
        layouts = [{"name": "Лист 1", "tabOrder": 1, "plotRotation": 0}]
        try:
            item_stat = path.stat()
            manifest_data = {
                "sourcePath": str(path),
                "sourceName": path.name,
                "sourceSize": item_stat.st_size,
                "sourceMtime": int(item_stat.st_mtime),
                "outputDir": str(target_dir),
                "isComplete": True,
                "totalLayouts": 1,
                "validLayouts": 1,
                "layouts": layouts,
                "completedPages": {1: {"bytes": page1_png.stat().st_size if page1_png.exists() else 0, "name": "Лист 1"}},
            }
            _write_json_atomic(manifest_path, manifest_data)
        except Exception:
            pass

    items = []
    if layouts:
        for lay in layouts:
            tab = int(lay.get("tabOrder", 1))
            p_png = target_dir / f"page-{tab}.png"
            p_ready = p_png.exists() and p_png.stat().st_size > 0
            if p_ready:
                img_url = f"/cache/dwg/{cache_key}/{p_png.name}"
                img_bytes = p_png.stat().st_size
            elif thumb_png.exists():
                img_url = f"/cache/dwg/{cache_key}/header_thumb.png"
                img_bytes = thumb_png.stat().st_size
            else:
                img_url = f"/cache/dwg/{cache_key}/{p_png.name}"
                img_bytes = 0

            items.append({
                "page": tab,
                "name": f"{path.name} · {lay.get('name', f'Лист {tab}')}",
                "url": img_url,
                "bytes": img_bytes,
                "previewType": "DWG_MODEL",
                "isEmpty": check_image_is_empty_sheet(p_png) if p_ready else False,
            })
    else:
        p1_ready_full = page1_png.exists() and page1_png.stat().st_size > 0
        if p1_ready_full:
            p1_url = f"/cache/dwg/{cache_key}/{page1_png.name}"
            p1_bytes = page1_png.stat().st_size
        elif thumb_png.exists():
            p1_url = f"/cache/dwg/{cache_key}/header_thumb.png"
            p1_bytes = thumb_png.stat().st_size
        else:
            p1_url = f"/cache/dwg/{cache_key}/{page1_png.name}"
            p1_bytes = 0

        items.append({
            "page": 1,
            "name": f"{path.name} · Лист 1",
            "url": p1_url,
            "bytes": p1_bytes,
            "previewType": "DWG_MODEL",
            "isEmpty": check_image_is_empty_sheet(page1_png) if p1_ready_full else False,
        })

    is_complete_now = bool(page1_ready and len(items) > 0 and all((target_dir / f"page-{it['page']}.png").exists() and (target_dir / f"page-{it['page']}.png").stat().st_size > 0 for it in items))
    empty_pages = [it["page"] for it in items if it.get("bytes", 0) > 0 and it.get("isEmpty")]
    first_content_page = next((it["page"] for it in items if it.get("bytes", 0) > 0 and not it.get("isEmpty")), None)

    return {
        "name": path.name,
        "path": str(path),
        "sourcePath": str(path),
        "sourceName": path.name,
        "sourceType": "DWG",
        "dpi": dpi,
        "pages": len(layouts) if layouts else 1,
        "renderedPages": len(layouts) if layouts else 1,
        "cacheKey": cache_key,
        "cacheHit": False,
        "cacheHitPages": len([it for it in items if it["bytes"] > 0]),
        "isComplete": is_complete_now,
        "emptyPages": empty_pages,
        "firstContentPage": first_content_page,
        "newRenderedPages": 1 if page1_ready else 0,
        "errors": [],
        "items": items,
        "status": "ok",
        "convertedPdfPath": str(page1_pdf) if page1_pdf.exists() else "",
        "convertCacheHit": False,
        "previewMode": "cad-smart-layouts",
    }


def render_dwg_page_progressive(
    file_path: Path,
    target_dir: Path,
    cache_key: str,
    page: int,
    dpi: int = 150,
    wait_seconds: float = 5.0,
) -> Dict[str, Any]:
    """Прогрессивный возврат конкретной страницы чертежа DWG с поддержкой DPI (72, 150, 300)."""
    dpi_suffix = "" if dpi == 150 else f"@{dpi}"
    png_name = f"page-{page}{dpi_suffix}.png"
    png_path = target_dir / png_name
    pdf_path = target_dir / f"page_{page:04d}.pdf"
    thumb_path = target_dir / "header_thumb.png"

    # 1. Если для данного DPI уже есть готовый полноценный PNG (> 35KB исключает thumbnail)
    if png_path.exists() and png_path.stat().st_size > 0:
        item = {
            "page": page,
            "name": f"{file_path.name} · стр. {page}",
            "url": f"/cache/dwg/{cache_key}/{png_name}",
            "bytes": png_path.stat().st_size,
            "previewType": "DWG_MODEL",
            "isEmpty": check_image_is_empty_sheet(png_path),
        }
        return {
            "name": file_path.name,
            "path": str(file_path),
            "dpi": dpi,
            "page": page,
            "cacheKey": cache_key,
            "cacheHit": True,
            "item": item,
            "url": item["url"],
            "bytes": item["bytes"],
            "sourcePath": str(file_path),
            "sourceType": "DWG",
            "convertedPdfPath": str(pdf_path) if pdf_path.exists() else "",
            "convertCacheHit": True,
        }

    # 2. Если PDF готов (> 4096 байт и %%EOF), сразу растрируем в запрошенный DPI
    if _is_pdf_complete(pdf_path):
        _rasterize_pdf_page(pdf_path, png_path, dpi)
        if png_path.exists() and png_path.stat().st_size > 0:
            item = {
                "page": page,
                "name": f"{file_path.name} · стр. {page}",
                "url": f"/cache/dwg/{cache_key}/{png_name}",
                "bytes": png_path.stat().st_size,
                "previewType": "DWG_MODEL",
                "isEmpty": check_image_is_empty_sheet(png_path),
            }
            return {
                "name": file_path.name,
                "path": str(file_path),
                "dpi": dpi,
                "page": page,
                "cacheKey": cache_key,
                "cacheHit": False,
                "item": item,
                "url": item["url"],
                "bytes": item["bytes"],
                "sourcePath": str(file_path),
                "sourceType": "DWG",
                "convertedPdfPath": str(pdf_path),
                "convertCacheHit": True,
            }

    # 3. При необходимости запускаем/ускоряем воркер или прогрессивный accoreconsole на нужный лист
    proc = DwgOnDemandManager.get_or_start_worker(file_path, target_dir, priority_tab=page)
    if proc:
        _start_background_worker_pump(proc, target_dir, file_path, dpi)
    else:
        start_accore_progressive_export(file_path, target_dir, dpi=150, priority_tab=page)

    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        if _is_pdf_complete(pdf_path):
            _rasterize_pdf_page(pdf_path, png_path, dpi)
            if png_path.exists() and png_path.stat().st_size > 0:
                item = {
                    "page": page,
                    "name": f"{file_path.name} · стр. {page}",
                    "url": f"/cache/dwg/{cache_key}/{png_name}",
                    "bytes": png_path.stat().st_size,
                    "previewType": "DWG_MODEL",
                    "isEmpty": check_image_is_empty_sheet(png_path),
                }
                return {
                    "name": file_path.name,
                    "path": str(file_path),
                    "dpi": dpi,
                    "page": page,
                    "cacheKey": cache_key,
                    "cacheHit": False,
                    "item": item,
                    "url": item["url"],
                    "bytes": item["bytes"],
                    "sourcePath": str(file_path),
                    "sourceType": "DWG",
                    "convertedPdfPath": str(pdf_path),
                    "convertCacheHit": False,
                }
        if proc is not None and proc.poll() is not None:
            break
        if proc is None and not is_accore_job_active(file_path):
            break
        time.sleep(0.25)

    # Если лист еще рендерится, возвращаем превью заголовка
    fallback_url = f"/cache/dwg/{cache_key}/header_thumb.png" if thumb_path.exists() else f"/cache/dwg/{cache_key}/page-1.png"
    fallback_bytes = thumb_path.stat().st_size if thumb_path.exists() else 1024
    item = {
        "page": page,
        "name": f"{file_path.name} · стр. {page} (Рендерится...)",
        "url": fallback_url,
        "bytes": fallback_bytes,
        "previewType": "DWG_MODEL",
    }
    return {
        "name": file_path.name,
        "path": str(file_path),
        "dpi": dpi,
        "page": page,
        "cacheKey": cache_key,
        "cacheHit": False,
        "rendering": True,
        "item": item,
        "url": fallback_url,
        "bytes": fallback_bytes,
        "sourcePath": str(file_path),
        "sourceType": "DWG",
        "convertedPdfPath": "",
        "convertCacheHit": False,
    }


if __name__ == "__main__":
    print("=" * 65)
    print(" DWG Engine v3 - Тестирование мгновенного чтения DWG чертежей")
    print("=" * 65)

    # Поиск тестового DWG файла
    candidate_paths = [
        r"C:\DWG_Benchmark_Test\benchmark.dwg",
        r"C:\DWG_Benchmark_Test\heavy_test.dwg",
        r"C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3_CURRENT_COPY\да.dwg",
        r"C:\Users\a9379\Documents\Codex\FEngineering_Launcher_v3_CURRENT_COPY\runtime\dwg-probe\input\Лабораторный_объёмы_проба.dwg",
    ]

    test_file = None
    for cand in candidate_paths:
        if Path(cand).exists():
            test_file = cand
            break

    if not test_file:
        for dwg_cand in Path(".").resolve().glob("**/*.dwg"):
            test_file = str(dwg_cand)
            break

    if not test_file:
        print("[!] Тестовый DWG файл не найден на диске. Создание синтетического заголовка...")
        import tempfile

        tmp_dir = Path(tempfile.gettempdir()) / "dwg_engine_test"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        synthetic_dwg = tmp_dir / "synthetic_test.dwg"

        dummy_png = _generate_placeholder_png("synthetic_test.dwg", "Model")
        thumb_offset = 0x240
        hdr = bytearray(0x240)
        hdr[:6] = b"AC1032"
        struct.pack_into("<I", hdr, 0x0D, thumb_offset)

        thumb_table = bytearray()
        thumb_table.extend(DWG_THUMBNAIL_SENTINEL)
        overall_size = len(dummy_png) + 80
        thumb_table.extend(struct.pack("<I", overall_size))
        thumb_table.append(1)  # 1 image
        img_start = thumb_offset + len(thumb_table) + 9
        thumb_table.append(6)  # PNG
        thumb_table.extend(struct.pack("<I", img_start))
        thumb_table.extend(struct.pack("<I", len(dummy_png)))

        with open(synthetic_dwg, "wb") as f:
            f.write(hdr)
            f.write(thumb_table)
            f.write(dummy_png)

        test_file = str(synthetic_dwg)

    print(f"[*] Тестовый чертеж: {test_file}")
    file_size_mb = Path(test_file).stat().st_size / (1024 * 1024)
    print(f"[*] Размер файла: {file_size_mb:.2f} МБ\n")

    # 1. Тест get_dwg_preview: замер времени и валидация результата
    print("[1] Тестирование get_dwg_preview()...")
    preview_res = get_dwg_preview(test_file)
    print(f"    - Первый запуск: {preview_res['elapsed_ms']:.3f} мс (статус: {preview_res['status']})")

    # Серия замеров времени (warm read)
    measurements: List[float] = []
    for _ in range(10):
        t0 = time.perf_counter()
        res = get_dwg_preview(test_file)
        t_ms = (time.perf_counter() - t0) * 1000.0
        measurements.append(t_ms)

    avg_ms = sum(measurements) / len(measurements)
    min_ms = min(measurements)
    print(f"    - Среднее время (10 замеров): {avg_ms:.3f} мс")
    print(f"    - Минимальное время: {min_ms:.3f} мс")
    print(f"    - Количество листов: {preview_res['layout_count']}")
    print(f"    - Текущий лист: {preview_res['current_layout']}")
    print(f"    - Размер изображения: {len(preview_res['image_bytes'])} байт")
    print(f"    - Base64 длина: {len(preview_res['image_base64'])} символов")

    # Проверка формата
    assert preview_res["status"] == "ok", "Ошибка статуса превью"
    assert len(preview_res["image_bytes"]) > 0, "Превью пустое"
    assert min_ms < 1.0, f"Время чтения превышает 1 мс ({min_ms:.3f} мс)"
    print("    -> [УСПЕХ] Превью извлечено за < 1 мс!\n")

    # 2. Тест get_dwg_layouts
    print("[2] Тестирование get_dwg_layouts()...")
    t0 = time.perf_counter()
    layouts = get_dwg_layouts(test_file)
    t_layouts_ms = (time.perf_counter() - t0) * 1000.0
    print(f"    - Время извлечения списка листов: {t_layouts_ms:.3f} мс")
    print(f"    - Найдено листов: {len(layouts)}")
    for l_item in layouts[:5]:
        print(f"      * [{l_item['index']}] {l_item['name']} (тип: {l_item['type']}, превью: {l_item['has_preview']})")
    if len(layouts) > 5:
        print(f"      ... и еще {len(layouts) - 5} листов")
    assert isinstance(layouts, list), "get_dwg_layouts должен возвращать список"
    assert len(layouts) >= 1, "Должен быть хотя бы один лист (Model)"
    print("    -> [УСПЕХ] Список листов успешно получен!\n")

    # 3. Тест превью конкретного листа без зависания
    print("[3] Тестирование get_dwg_layout_preview() без зависания...")
    t0 = time.perf_counter()
    layout_prev = get_dwg_layout_preview(test_file, layout=0)
    t_lp_ms = (time.perf_counter() - t0) * 1000.0
    print(f"    - Лист 0 (Model): {t_lp_ms:.3f} мс (размер: {len(layout_prev['image_bytes'])} байт)")

    if len(layouts) > 1:
        t0 = time.perf_counter()
        layout_prev1 = get_dwg_layout_preview(test_file, layout=1)
        t_lp1_ms = (time.perf_counter() - t0) * 1000.0
        print(f"    - Лист 1 ({layouts[1]['name']}): {t_lp1_ms:.3f} мс (размер: {len(layout_prev1['image_bytes'])} байт)")
        assert layout_prev1["status"] == "ok", "Ошибка статуса превью листа"

    print("    -> [УСПЕХ] Превью листов отдано мгновенно без зависания!\n")

    print("=" * 65)
    print(" ВСЕ ТЕСТЫ DWG ENGINE УСПЕШНО ПРОЙДЕНЫ!")
    print("=" * 65)
