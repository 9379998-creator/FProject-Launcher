"""
FERO Architectural Facade CAD Extractor
=======================================
Extracts vector profile assemblies, sections, and details from vector PDF catalogs
(Schüco, Reynaers, Wicona, Aluprof) into clean, editable AutoCAD DWG/DXF files.

Task 017 Core Contracts:
1. Editable contours: outer boundaries and inner cavity loops are individual closed
   polylines (LWPOLYLINE with close=True) in ModelSpace (not trapped in monolithic blocks).
2. Zero hatch: hatching is completely excluded from the output CAD geometry.
3. 1:1 real millimeters: dynamic scale detection compensates catalog ratio (1:1 or 1:2),
   ensuring CAD distance matches nominal dimensions (INSUNITS = 4).
4. Native AutoCAD DIMENSION entities with true geometric measurement points.
"""

import os
import math
import re
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict, Counter

import fitz  # PyMuPDF
import ezdxf
from ezdxf.enums import TextEntityAlignment

logger = logging.getLogger(__name__)

# Standard conversion: 1 typographical point = 25.4 / 72 mm = 0.35277778 mm
PT_TO_MM = 25.4 / 72.0


def pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def sample_bezier(
    p1: fitz.Point, p2: fitz.Point, p3: fitz.Point, p4: fitz.Point, steps: int = 8
) -> List[Tuple[float, float]]:
    """Sample a cubic Bezier curve into discrete line vertices."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        mt = 1.0 - t
        x = mt**3 * p1.x + 3.0 * mt**2 * t * p2.x + 3.0 * mt * t**2 * p3.x + t**3 * p4.x
        y = mt**3 * p1.y + 3.0 * mt**2 * t * p2.y + 3.0 * mt * t**2 * p3.y + t**3 * p4.y
        pts.append((round(x, 4), round(y, 4)))
    return pts


def detect_catalog_scale(page: fitz.Page, crop_box: Optional[fitz.Rect] = None) -> float:
    """
    Dynamic dual-engine catalog scale detector:
    1. Dimension line calibration: computes the ratio between nominal dimension text
       and drawn line length in PDF points. Matches standard catalog ratios (1.0 for 1:1, 2.0 for 1:2).
    2. Title block fallback inspection (scale / Maßstab / échelle).
    """
    search_rect = crop_box if crop_box else page.rect
    drawings = [d for d in page.get_drawings() if search_rect.intersects(d["rect"])]

    # 1. Analyze 4-line dimension drawings and dimension witness lines
    dim_ratios = []
    words = page.get_text("words")
    crop_words = [w for w in words if search_rect.intersects(fitz.Rect(w[:4]))]

    for d in drawings:
        items = d.get("items", [])
        if len(items) == 4 and all(it[0] == "l" for it in items):
            lines = [(it[1], it[2]) for it in items]
            horiz = [l for l in lines if abs(l[0].y - l[1].y) < 0.2]
            vert = [l for l in lines if abs(l[0].x - l[1].x) < 0.2]

            # Vertical dimension: measurement is along Y
            if len(horiz) == 2 and len(vert) == 2:
                meas_pt = abs(horiz[0][0].y - horiz[1][0].y)
                dim_x = vert[0][0].x
                mid_y = (horiz[0][0].y + horiz[1][0].y) / 2.0
                if meas_pt > 1.0:
                    for w in crop_words:
                        txt = str(w[4]).strip()
                        if re.match(r"^\d{2,3}$", txt):
                            val = float(txt)
                            if val >= 10.0 and math.hypot((w[0] + w[2]) / 2.0 - dim_x, (w[1] + w[3]) / 2.0 - mid_y) < 25.0:
                                ratio = val / (meas_pt * PT_TO_MM)
                                for std in [1.0, 2.0, 2.5, 5.0]:
                                    if abs(ratio - std) < 0.08:
                                        dim_ratios.append(std)

            # Horizontal dimension: measurement is along X
            elif len(vert) == 2 and len(horiz) == 2:
                meas_pt = abs(vert[0][0].x - vert[1][0].x)
                dim_y = horiz[0][0].y
                mid_x = (vert[0][0].x + vert[1][0].x) / 2.0
                if meas_pt > 1.0:
                    for w in crop_words:
                        txt = str(w[4]).strip()
                        if re.match(r"^\d{2,3}$", txt):
                            val = float(txt)
                            if val >= 10.0 and math.hypot((w[0] + w[2]) / 2.0 - mid_x, (w[1] + w[3]) / 2.0 - dim_y) < 25.0:
                                ratio = val / (meas_pt * PT_TO_MM)
                                for std in [1.0, 2.0, 2.5, 5.0]:
                                    if abs(ratio - std) < 0.08:
                                        dim_ratios.append(std)

    if dim_ratios:
        calibrated_scale = Counter(dim_ratios).most_common(1)[0][0]
        logger.info("Calibrated catalog scale from dimension lines: %s", calibrated_scale)
        return calibrated_scale

    # 2. Fallback: Search full page text for explicit scale indicator
    try:
        full_text = page.get_text()
        m = re.findall(
            r"(?:scale|schaal|maßstab|masstab|échelle)[\s\S]{0,40}?([0-9]+[/:][0-9]+(?:\.[0-9]+)?)",
            full_text,
            re.IGNORECASE,
        )
        if m:
            parts = re.split(r"[/:]", m[0])
            if len(parts) == 2 and float(parts[0]) > 0:
                scale_fac = float(parts[1]) / float(parts[0])
                if scale_fac > 0:
                    logger.info("Detected scale from page title block: %s", scale_fac)
                    return scale_fac
    except Exception as ex:
        logger.warning("Scale search fallback error: %s", ex)

    return 1.0


def extract_subpaths_from_drawing(d: Dict[str, Any]) -> List[List[fitz.Point]]:
    """Extract distinct continuous subpaths from a PyMuPDF drawing object."""
    items = d.get("items", [])
    subpaths = []
    cur_subpath = []

    for it in items:
        if it[0] == "l":
            p1, p2 = it[1], it[2]
            # Exclude 45-degree diagonal hatching lines
            dx = abs(p2.x - p1.x)
            dy = abs(p2.y - p1.y)
            if dx > 1.2 and dy > 1.2 and abs(dx - dy) < 0.35:
                continue

            if not cur_subpath:
                cur_subpath.append(p1)
            elif math.hypot(p1.x - cur_subpath[-1].x, p1.y - cur_subpath[-1].y) > 0.05:
                subpaths.append(cur_subpath)
                cur_subpath = [p1]
            cur_subpath.append(p2)

        elif it[0] == "c":
            p1, p2, p3, p4 = it[1], it[2], it[3], it[4]
            if not cur_subpath:
                cur_subpath.append(p1)
            elif math.hypot(p1.x - cur_subpath[-1].x, p1.y - cur_subpath[-1].y) > 0.05:
                subpaths.append(cur_subpath)
                cur_subpath = [p1]
            for s in range(1, 9):
                t = s / 8.0
                mt = 1.0 - t
                x = mt**3 * p1.x + 3.0 * mt**2 * t * p2.x + 3.0 * mt * t**2 * p3.x + t**3 * p4.x
                y = mt**3 * p1.y + 3.0 * mt**2 * t * p2.y + 3.0 * mt * t**2 * p3.y + t**3 * p4.y
                cur_subpath.append(fitz.Point(x, y))

        elif it[0] == "re":
            r_box = it[1]
            subpaths.append([
                fitz.Point(r_box.x0, r_box.y0),
                fitz.Point(r_box.x1, r_box.y0),
                fitz.Point(r_box.x1, r_box.y1),
                fitz.Point(r_box.x0, r_box.y1),
                fitz.Point(r_box.x0, r_box.y0),
            ])

    if cur_subpath:
        subpaths.append(cur_subpath)

    return subpaths


class PDFCadExtractor:
    """
    Architectural facade CAD extractor:
    Decomposes vector PDF details into clean, editable AutoCAD DWG/DXF files,
    producing individually selectable closed polylines, native AutoCAD DIMENSION entities,
    and calibrated 1:1 millimeter geometry.
    """

    def __init__(self, pdf_path: str | Path):
        self.pdf_path = Path(pdf_path)
        if not self.pdf_path.exists():
            raise FileNotFoundError(f"PDF не найден: {self.pdf_path}")

    def extract_cad(
        self,
        page_number: int,
        crop_box: Optional[Tuple[float, float, float, float]] = None,
        output_path: Optional[str | Path] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extract vector detail from the given PDF page into an editable DXF file.
        
        :param page_number: 1-based page number (e.g. 1)
        :param crop_box: [x0, y0, x1, y1] in PDF point coordinates
        :param output_path: path to save .dxf file
        :param options: additional extraction options
        """
        opts = options or {}
        dxf_version = opts.get("dxf_version", "R2013")
        crop_pad = opts.get("crop_padding", 14.0)

        doc = fitz.open(self.pdf_path)
        page_idx = max(0, min(page_number - 1, len(doc) - 1))
        page = doc[page_idx]
        page_rect = page.rect

        if crop_box:
            cx0 = min(crop_box[0], crop_box[2])
            cy0 = min(crop_box[1], crop_box[3])
            cx1 = max(crop_box[0], crop_box[2])
            cy1 = max(crop_box[1], crop_box[3])

            cx0 = max(0.0, cx0 - crop_pad)
            cy0 = max(0.0, cy0 - crop_pad)
            cx1 = min(page_rect.width, cx1 + crop_pad)
            cy1 = min(page_rect.height, cy1 + crop_pad)
            filter_rect = fitz.Rect(cx0, cy0, cx1, cy1)
        else:
            filter_rect = page_rect

        # 1. Dynamic Scale Calibration (Contract 3)
        scale_factor = detect_catalog_scale(page, filter_rect)
        total_scale = PT_TO_MM * scale_factor
        logger.info("Calibrated catalog scale: %s (total_scale=%f mm/pt)", scale_factor, total_scale)

        # 2. Coordinate Transformation (origin bottom-left of crop)
        ox = filter_rect.x0
        oy = filter_rect.y1

        def to_cad(pt: Tuple[float, float]) -> Tuple[float, float]:
            """Convert PDF point (top-left) to CAD millimeter (bottom-left)."""
            cad_x = (pt[0] - ox) * total_scale
            cad_y = (oy - pt[1]) * total_scale
            return (round(cad_x, 4), round(cad_y, 4))

        # 3. Setup AutoCAD DXF Document with Millimeters Unit ($INSUNITS = 4)
        dxf_doc = ezdxf.new(dxf_version, setup=True)
        dxf_doc.header["$INSUNITS"] = 4
        msp = dxf_doc.modelspace()

        layers_def = [
            ("01_АЛЮМИНИЙ_НАРУЖНЫЙ", 7, 35),
            ("01_АЛЮМИНИЙ_ВНУТРЕННИЙ", 3, 35),
            ("03_ТЕРМОМОСТ", 8, 25),
            ("04_УПЛОТНИТЕЛИ", 4, 25),
            ("05_СТЕКЛОПАКЕТ", 5, 35),
            ("07_РАЗМЕРЫ", 1, 18),
            ("09_АННОТАЦИИ_ТЕКСТ", 7, 20),
        ]
        for name, col, lw in layers_def:
            try:
                l = dxf_doc.layers.add(name, color=col)
                l.dxf.lineweight = lw
            except Exception:
                pass

        layer_stats: Dict[str, int] = defaultdict(int)
        entities_count = 0
        closed_loops_count = 0

        drawings = [d for d in page.get_drawings() if filter_rect.intersects(d["rect"])]
        words = page.get_text("words")
        crop_words = [w for w in words if filter_rect.intersects(fitz.Rect(w[:4]))]

        # 4. Extract Native AutoCAD DIMENSION Entities (Contract 4)
        extracted_dims = []
        dim_drawings_indices = set()
        dim_nominals = set()

        for idx, d in enumerate(drawings):
            items = d.get("items", [])
            if len(items) == 4 and all(it[0] == "l" for it in items):
                lines = [(it[1], it[2]) for it in items]
                horiz = [l for l in lines if abs(l[0].y - l[1].y) < 0.2]
                vert = [l for l in lines if abs(l[0].x - l[1].x) < 0.2]

                # Vertical dimension
                if len(horiz) == 2 and len(vert) == 2:
                    y1, y2 = horiz[0][0].y, horiz[1][0].y
                    dim_x = vert[0][0].x
                    meas_mm = abs(y2 - y1) * total_scale
                    mid_y = (y1 + y2) / 2.0
                    closest_txt = None
                    min_d = 9999.0
                    for w in crop_words:
                        txt = str(w[4]).strip()
                        if re.match(r"^\d{1,3}$", txt):
                            d_txt = math.hypot((w[0] + w[2]) / 2.0 - dim_x, (w[1] + w[3]) / 2.0 - mid_y)
                            if d_txt < min_d:
                                min_d = d_txt
                                closest_txt = (txt, d_txt)
                    if closest_txt and closest_txt[1] < 20.0 and meas_mm >= 3.5:
                        dim_drawings_indices.add(idx)
                        dim_nominals.add(closest_txt[0])
                        extracted_dims.append({
                            "base": to_cad((dim_x, mid_y)),
                            "p1": to_cad((horiz[0][0].x, y1)),
                            "p2": to_cad((horiz[1][0].x, y2)),
                            "angle": 90.0,
                            "nominal": closest_txt[0],
                            "measured_mm": meas_mm,
                        })

                # Horizontal dimension
                elif len(vert) == 2 and len(horiz) == 2:
                    x1, x2 = vert[0][0].x, vert[1][0].x
                    dim_y = horiz[0][0].y
                    meas_mm = abs(x2 - x1) * total_scale
                    mid_x = (x1 + x2) / 2.0
                    closest_txt = None
                    min_d = 9999.0
                    for w in crop_words:
                        txt = str(w[4]).strip()
                        if re.match(r"^\d{1,3}$", txt):
                            d_txt = math.hypot((w[0] + w[2]) / 2.0 - mid_x, (w[1] + w[3]) / 2.0 - dim_y)
                            if d_txt < min_d:
                                min_d = d_txt
                                closest_txt = (txt, d_txt)
                    if closest_txt and closest_txt[1] < 20.0 and meas_mm >= 3.5:
                        dim_drawings_indices.add(idx)
                        dim_nominals.add(closest_txt[0])
                        extracted_dims.append({
                            "base": to_cad((mid_x, dim_y)),
                            "p1": to_cad((x1, vert[0][0].y)),
                            "p2": to_cad((x2, vert[1][0].y)),
                            "angle": 0.0,
                            "nominal": closest_txt[0],
                            "measured_mm": meas_mm,
                        })

        for dim_data in extracted_dims:
            try:
                dim = msp.add_linear_dim(
                    base=dim_data["base"],
                    p1=dim_data["p1"],
                    p2=dim_data["p2"],
                    angle=dim_data["angle"],
                    dxfattribs={"layer": "07_РАЗМЕРЫ"},
                )
                dim.render()
                entities_count += 1
                layer_stats["07_РАЗМЕРЫ"] += 1
            except Exception as e:
                logger.debug("Error adding native dimension: %s", e)

        # 5. Extract Text Annotations (excluding numbers rendered by native DIMENSION)
        try:
            dict_blocks = page.get_text("dict")["blocks"]
            for b in dict_blocks:
                if b.get("type") == 0:
                    for line in b.get("lines", []):
                        dir_x, dir_y = line.get("dir", (1, 0))
                        for span in line.get("spans", []):
                            r = fitz.Rect(span["bbox"])
                            if filter_rect.intersects(r):
                                text_str = str(span.get("text", "")).strip()
                                if not text_str:
                                    continue
                                if text_str in dim_nominals and re.match(r"^\d{1,3}$", text_str):
                                    continue

                                font_size_pt = span.get("size", 7.0)
                                height_mm = max(2.2, min(4.5, round(font_size_pt * total_scale, 2)))
                                cad_dir_y = -dir_y
                                angle_deg = round(math.degrees(math.atan2(cad_dir_y, dir_x)), 1) % 360
                                orig = span.get("origin", (span["bbox"][0], span["bbox"][3]))
                                cad_insert = to_cad(orig)

                                txt = msp.add_text(
                                    text_str,
                                    height=height_mm,
                                    dxfattribs={"layer": "09_АННОТАЦИИ_ТЕКСТ", "rotation": angle_deg},
                                )
                                txt.dxf.insert = cad_insert
                                entities_count += 1
                                layer_stats["09_АННОТАЦИИ_ТЕКСТ"] += 1
        except Exception as e:
            logger.warning("Error extracting text: %s", e)

        # 6. Extract Closed Contours and Cavities into ModelSpace (Contracts 1 & 2)
        for idx, d in enumerate(drawings):
            if idx in dim_drawings_indices:
                continue

            items = d.get("items", [])
            # Skip dimension arrowheads
            if d.get("fill") is not None and len(items) == 3 and 1.0 <= d["rect"].width <= 15.0 and 1.0 <= d["rect"].height <= 15.0:
                continue

            subpaths = extract_subpaths_from_drawing(d)
            for sp in subpaths:
                if len(sp) < 3:
                    continue

                gap = math.hypot(sp[0].x - sp[-1].x, sp[0].y - sp[-1].y)
                is_closed = (gap <= 0.25)
                if is_closed:
                    sp[-1] = sp[0]

                cad_pts = [to_cad((p.x, p.y)) for p in sp]
                avg_cad_x = sum(p[0] for p in cad_pts) / len(cad_pts)

                # Geometry layer assignment based on structural zone
                if 45.0 <= avg_cad_x <= 75.0:
                    layer_name = "03_ТЕРМОМОСТ"
                elif avg_cad_x < 45.0:
                    layer_name = "01_АЛЮМИНИЙ_НАРУЖНЫЙ"
                elif avg_cad_x > 115.0:
                    layer_name = "05_СТЕКЛОПАКЕТ"
                else:
                    layer_name = "01_АЛЮМИНИЙ_ВНУТРЕННИЙ"

                # Contract 1: Add as individual LWPOLYLINE directly into ModelSpace
                msp.add_lwpolyline(
                    cad_pts,
                    close=is_closed,
                    dxfattribs={"layer": layer_name},
                )
                entities_count += 1
                layer_stats[layer_name] += 1
                if is_closed:
                    closed_loops_count += 1

        # 7. Save Output File
        if not output_path:
            out_dir = Path("runtime/cache/cad")
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = self.pdf_path.stem.replace(" ", "_")
            output_path = out_dir / f"{stem}_стр_{page_number}.dxf"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            dxf_doc.saveas(str(output_path))
        except PermissionError:
            alt_path = output_path.with_stem(f"{output_path.stem}_upd")
            dxf_doc.saveas(str(alt_path))
            logger.info("Target file locked by CAD program, saved to %s", alt_path)
            output_path = alt_path

        logger.info("Saved CAD export to %s (%d entities, %d closed loops)", output_path, entities_count, closed_loops_count)
        scale_desc = f"1:{int(scale_factor)}" if scale_factor > 1.0 else "1:1"

        return {
            "success": True,
            "filePath": str(output_path.resolve()),
            "fileName": output_path.name,
            "page": page_number,
            "entitiesCount": entities_count,
            "closedLoopsCount": closed_loops_count,
            "layers": dict(layer_stats),
            "scale": total_scale,
            "scaleFactor": scale_factor,
            "scaleUnit": "mm",
            "scaleStr": scale_desc,
        }


def open_in_cad_program(filepath: str | Path) -> bool:
    """Launch the exported DXF/DWG file in Windows using the default CAD application."""
    p = Path(filepath)
    if not p.exists():
        return False
    try:
        os.startfile(str(p.resolve()))
        return True
    except Exception as e:
        logger.warning("Error opening CAD file: %s", e)
        return False


def export_pdf_page_to_cad(
    pdf_path: str | Path,
    page_number: int,
    crop_box: Optional[Tuple[float, float, float, float]] = None,
    output_path: Optional[str | Path] = None,
    options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convenience functional wrapper for PDFCadExtractor."""
    extractor = PDFCadExtractor(pdf_path)
    return extractor.extract_cad(
        page_number=page_number,
        crop_box=crop_box,
        output_path=output_path,
        options=options,
    )
