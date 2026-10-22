"""
FERO Architectural Facade CAD Extractor
Extracts vector profile assemblies, sections, and details from vector PDF catalogs
(Reynaers, Schüco, Wicona, Aluprof) into clean, layered AutoCAD DWG/DXF files.
"""

import os
import math
import re
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import fitz  # PyMuPDF
import ezdxf
from ezdxf.enums import TextEntityAlignment

logger = logging.getLogger(__name__)

# Standard conversion: 1 typographical point = 25.4 / 72 mm = 0.35277778 mm
PT_TO_MM = 25.4 / 72.0


def is_dashed_pattern(dashes: Optional[str]) -> bool:
    """Check if the PDF dash pattern represents a real dashed line (not '[] 0' solid)."""
    if not dashes:
        return False
    d = str(dashes).strip()
    return bool(d and not d.startswith("[]"))


def sample_bezier(p1: fitz.Point, p2: fitz.Point, p3: fitz.Point, p4: fitz.Point, steps: int = 6) -> List[Tuple[float, float]]:
    """Sample a cubic Bezier curve into discrete line vertices."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        mt = 1.0 - t
        x = mt**3 * p1.x + 3.0 * mt**2 * t * p2.x + 3.0 * mt * t**2 * p3.x + t**3 * p4.x
        y = mt**3 * p1.y + 3.0 * mt**2 * t * p2.y + 3.0 * mt * t**2 * p3.y + t**3 * p4.y
        pts.append((x, y))
    return pts


def pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def polygon_area(pts: List[Tuple[float, float]]) -> float:
    """Signed Shoelace polygon area."""
    if len(pts) < 3:
        return 0.0
    area = 0.0
    for i in range(len(pts)):
        j = (i + 1) % len(pts)
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def polygon_perimeter(pts: List[Tuple[float, float]]) -> float:
    """Total perimeter of a polygon."""
    if len(pts) < 2:
        return 0.0
    perim = 0.0
    for i in range(len(pts) - 1):
        perim += pt_dist(pts[i], pts[i + 1])
    return perim


class PDFCadExtractor:
    """
    Intelligent architectural facade extractor:
    Decomposes vector PDF drawings into true CAD elements on separate layers.
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
        Extract vector detail from the given PDF page into a layered DXF file.
        
        :param page_number: 1-based page number (e.g. 131)
        :param crop_box: [x0, y0, x1, y1] in PDF point coordinates
        :param output_path: path to save .dxf file
        :param options: additional extraction options
        """
        opts = options or {}
        join_polylines = opts.get("join_polylines", True)
        dxf_version = opts.get("dxf_version", "R2013")
        chain_tol = opts.get("tolerance", 0.25)  # ~0.08 mm tolerance in PDF points

        doc = fitz.open(self.pdf_path)
        page_idx = max(0, min(page_number - 1, len(doc) - 1))
        page = doc[page_idx]
        page_rect = page.rect

        if crop_box:
            # Normalize crop coordinates
            cx0 = min(crop_box[0], crop_box[2])
            cy0 = min(crop_box[1], crop_box[3])
            cx1 = max(crop_box[0], crop_box[2])
            cy1 = max(crop_box[1], crop_box[3])
            filter_rect = fitz.Rect(cx0, cy0, cx1, cy1)
        else:
            filter_rect = page_rect

        # 1. Fetch raw vector drawings and text
        all_drawings = page.get_drawings()
        drawings = [d for d in all_drawings if filter_rect.intersects(d["rect"])]

        # Fetch text words inside crop
        text_words = []
        scale_factor_detected = 1.0
        try:
            for w in page.get_text("words"):
                wr = fitz.Rect(w[0], w[1], w[2], w[3])
                if filter_rect.intersects(wr):
                    text_words.append(w)
                    # Detect scale indicator (e.g. 1/2, 1:2, 1/5, 1:5, 1/1, 1:1)
                    txt = str(w[4]).strip()
                    m_scale = re.match(r"^1[/:](\d+(\.\d+)?)$", txt)
                    if m_scale:
                        denom = float(m_scale.group(1))
                        if denom > 0:
                            scale_factor_detected = denom  # e.g. 1:2 means we must multiply by 2 to get 1:1 in mm
        except Exception as e:
            logger.warning("Error fetching text words: %s", e)

        # 2. Extract segments, fills, and dimension arrowheads
        raw_segments = []
        arrowheads = []  # Dimension arrow polygons

        for d in drawings:
            fill = d.get("fill")
            color = d.get("color")
            width = d.get("width", 0.0)
            dashes = d.get("dashes")
            is_dashed = is_dashed_pattern(dashes)
            items = d.get("items", [])

            # Check if this drawing is a small filled arrowhead (triangle)
            if fill is not None and len(items) == 3 and d["rect"].width < 14 and d["rect"].height < 14:
                arrow_pts = []
                for it in items:
                    if it[0] == "l":
                        arrow_pts.append((it[1].x, it[1].y))
                if len(arrow_pts) >= 3:
                    arrowheads.append((arrow_pts, d["rect"]))
                continue

            # Process segment items
            for it in items:
                if it[0] == "l":
                    p1 = (it[1].x, it[1].y)
                    p2 = (it[2].x, it[2].y)
                    if pt_dist(p1, p2) > 0.001:
                        raw_segments.append({
                            "points": [p1, p2],
                            "color": color,
                            "fill": fill,
                            "width": width,
                            "dashed": is_dashed,
                        })
                elif it[0] == "c":
                    # Sample Bezier curves into smooth arc lines
                    pts = sample_bezier(it[1], it[2], it[3], it[4], steps=6)
                    raw_segments.append({
                        "points": pts,
                        "color": color,
                        "fill": fill,
                        "width": width,
                        "dashed": is_dashed,
                    })
                elif it[0] == "re":
                    r = it[1]
                    pts = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
                    raw_segments.append({
                        "points": pts,
                        "color": color,
                        "fill": fill,
                        "width": width,
                        "dashed": is_dashed,
                        "closed": True,
                    })

        # 3. Assemble segments into continuous polylines (Chaining)
        assembled_chains = []
        if join_polylines and raw_segments:
            unused = list(raw_segments)
            while unused:
                cur_seg = unused.pop(0)
                cur_pts = list(cur_seg["points"])
                cur_fill = cur_seg["fill"]
                cur_width = cur_seg["width"]
                cur_dashed = cur_seg["dashed"]
                cur_color = cur_seg["color"]

                extended = True
                while extended:
                    extended = False
                    start_pt = cur_pts[0]
                    end_pt = cur_pts[-1]

                    # If already closed loop, stop extending
                    if len(cur_pts) > 2 and pt_dist(start_pt, end_pt) < chain_tol:
                        break

                    for i, other in enumerate(unused):
                        # Don't merge dashed lines with solid lines
                        if other["dashed"] != cur_dashed:
                            continue

                        o_start = other["points"][0]
                        o_end = other["points"][-1]

                        if pt_dist(end_pt, o_start) < chain_tol:
                            cur_pts.extend(other["points"][1:])
                            unused.pop(i)
                            extended = True
                            break
                        elif pt_dist(end_pt, o_end) < chain_tol:
                            cur_pts.extend(other["points"][-2::-1])
                            unused.pop(i)
                            extended = True
                            break
                        elif pt_dist(start_pt, o_end) < chain_tol:
                            cur_pts = other["points"][:-1] + cur_pts
                            unused.pop(i)
                            extended = True
                            break
                        elif pt_dist(start_pt, o_start) < chain_tol:
                            cur_pts = other["points"][::-1][:-1] + cur_pts
                            unused.pop(i)
                            extended = True
                            break

                is_closed = len(cur_pts) > 2 and pt_dist(cur_pts[0], cur_pts[-1]) < chain_tol
                assembled_chains.append({
                    "points": cur_pts,
                    "closed": is_closed,
                    "color": cur_color,
                    "fill": cur_fill,
                    "width": cur_width,
                    "dashed": cur_dashed,
                })
        else:
            assembled_chains = raw_segments

        # 4. Coordinate Transformation & Scale
        # Set origin (0, 0) at the bottom-left of the cropped area
        ox = filter_rect.x0
        oy = filter_rect.y1  # Bottom of crop box in PDF coords
        total_scale = PT_TO_MM * scale_factor_detected

        def to_cad(pt: Tuple[float, float]) -> Tuple[float, float]:
            """Convert PDF point (origin top-left) to CAD millimeter (origin bottom-left)."""
            cad_x = (pt[0] - ox) * total_scale
            cad_y = (oy - pt[1]) * total_scale  # Invert Y so up is positive
            return (round(cad_x, 4), round(cad_y, 4))

        # 5. Build AutoCAD DXF Document
        dxf_doc = ezdxf.new(dxf_version, setup=True)
        msp = dxf_doc.modelspace()

        # Define canonical engineering layers with specific colors and lineweights
        # Lineweights in 1/100 mm: 35 = 0.35mm, 25 = 0.25mm, 18 = 0.18mm
        layers_def = [
            ("01_АЛЮМИНИЙ_РАМА", 7, 35, "CONTINUOUS"),       # White/Black, main profile contour
            ("02_АЛЮМИНИЙ_ШТАПИК", 3, 35, "CONTINUOUS"),     # Green, glazing bead
            ("03_ТЕРМОМОСТ", 8, 25, "CONTINUOUS"),           # Dark gray, polyamide strip
            ("04_УПЛОТНИТЕЛИ", 4, 25, "CONTINUOUS"),         # Cyan, EPDM rubber
            ("05_СТЕКЛОПАКЕТ", 5, 35, "CONTINUOUS"),         # Blue, glass unit
            ("06_КРЕПЕЖ_СТАЛЬ", 2, 25, "CONTINUOUS"),        # Yellow, screws, brackets
            ("07_РАЗМЕРЫ", 1, 18, "CONTINUOUS"),             # Red, dimensions
            ("08_ОСИ", 6, 18, "CENTER"),                     # Magenta, centerlines
            ("09_ТЕКСТ", 7, 20, "CONTINUOUS"),               # Text labels and codes
        ]

        for name, color, weight, ltype in layers_def:
            try:
                layer = dxf_doc.layers.add(name, color=color)
                layer.dxf.lineweight = weight
                if ltype != "CONTINUOUS" and ltype in dxf_doc.linetypes:
                    layer.dxf.linetype = ltype
            except Exception:
                pass

        # 6. Classify and write polylines to layers
        entities_count = 0
        closed_loops_count = 0
        layer_stats: Dict[str, int] = {}

        for ch in assembled_chains:
            pts = ch["points"]
            if len(pts) < 2:
                continue

            cad_pts = [to_cad(p) for p in pts]
            is_closed = ch.get("closed", False)
            is_dashed = ch.get("dashed", False)
            fill = ch.get("fill")

            # Determine Layer
            layer_name = "01_АЛЮМИНИЙ_РАМА"
            if is_dashed:
                layer_name = "08_ОСИ"
            elif is_closed:
                closed_loops_count += 1
                area = polygon_area(cad_pts)
                perim = polygon_perimeter(cad_pts)
                compactness = (perim**2) / (4 * math.pi * area) if area > 0.001 else 999.0

                # Classification heuristic:
                # - Very small dark shapes or high compactness -> Gasket
                # - Intermediate elongated shapes with fills -> Thermal break
                # - Medium compact shapes snapped near glass -> Glazing bead
                # - Large hollow chambers -> Aluminum profile
                if fill is not None and area < 40.0:
                    layer_name = "04_УПЛОТНИТЕЛИ"
                elif area < 80.0 and compactness > 4.5:
                    layer_name = "04_УПЛОТНИТЕЛИ"
                elif fill is not None and 30.0 <= area <= 600.0 and compactness > 3.0:
                    layer_name = "03_ТЕРМОМОСТ"
                elif area < 300.0 and compactness < 3.2:
                    layer_name = "02_АЛЮМИНИЙ_ШТАПИК"
                else:
                    layer_name = "01_АЛЮМИНИЙ_РАМА"

            # Add to DXF
            try:
                msp.add_lwpolyline(
                    cad_pts,
                    close=is_closed,
                    dxfattribs={"layer": layer_name}
                )
                entities_count += 1
                layer_stats[layer_name] = layer_stats.get(layer_name, 0) + 1
            except Exception as e:
                logger.debug("Error adding polyline: %s", e)

        # 7. Add arrowheads to 07_РАЗМЕРЫ
        for arrow_pts, r in arrowheads:
            cad_arrow = [to_cad(p) for p in arrow_pts]
            if len(cad_arrow) >= 3:
                try:
                    msp.add_lwpolyline(
                        cad_arrow,
                        close=True,
                        dxfattribs={"layer": "07_РАЗМЕРЫ"}
                    )
                    entities_count += 1
                    layer_stats["07_РАЗМЕРЫ"] = layer_stats.get("07_РАЗМЕРЫ", 0) + 1
                except Exception:
                    pass

        # 8. Add Text and Annotations to 09_ТЕКСТ or 07_РАЗМЕРЫ
        for w in text_words:
            text_str = str(w[4]).strip()
            if not text_str:
                continue

            x_mid = (w[0] + w[2]) / 2.0
            y_base = w[3]
            cad_x, cad_y = to_cad((x_mid, y_base))
            height_mm = max(2.0, round((w[3] - w[1]) * total_scale, 2))

            # Is this text a dimension number (e.g. 68, 25, 30.47)?
            is_dim_num = bool(re.match(r"^(\d{1,4}(\.\d{1,3})?|\d{1,2}/\d{1,2})$", text_str))
            target_layer = "07_РАЗМЕРЫ" if is_dim_num else "09_ТЕКСТ"

            try:
                txt = msp.add_text(
                    text_str,
                    height=height_mm,
                    dxfattribs={"layer": target_layer}
                )
                txt.set_placement((cad_x, cad_y), align=TextEntityAlignment.BOTTOM_CENTER)
                entities_count += 1
                layer_stats[target_layer] = layer_stats.get(target_layer, 0) + 1
            except Exception as e:
                logger.debug("Error adding text: %s", e)

        # 9. Save output file
        if not output_path:
            out_dir = Path("runtime/cache/cad")
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = self.pdf_path.stem.replace(" ", "_")
            output_path = out_dir / f"{stem}_стр_{page_number}.dxf"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        dxf_doc.saveas(str(output_path))
        logger.info("Saved CAD export to %s (%d entities)", output_path, entities_count)

        scale_desc = f"1:{int(scale_factor_detected)}" if scale_factor_detected > 1.0 else "1:1"

        return {
            "success": True,
            "filePath": str(output_path.resolve()),
            "fileName": output_path.name,
            "page": page_number,
            "entitiesCount": entities_count,
            "closedLoopsCount": closed_loops_count,
            "layers": layer_stats,
            "scale": total_scale,
            "scaleFactor": scale_factor_detected,
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
        options=options
    )
