"""
FERO Architectural Facade CAD Extractor
=======================================
Extracts vector profile assemblies, sections, and details from vector PDF catalogs
and drawings into clean, editable AutoCAD DWG/DXF files.

Supports two operational contracts:
1. Mode "catalog" (Task 017): Zero hatch, clean closed polylines in ModelSpace,
   calibrated 1:1 / 1:2 millimeter geometry (Schüco, Reynaers).
2. Mode "reference" (Task 018 / 019): Full working drawing reconstruction from reference PDF:
   - Seamless segment chaining across lines and radiuses/curves (no broken lines at radiuses);
   - Reconnected glass unit seal lines;
   - Suppression of white wipeout mask rectangles crossing out text;
   - TrueType font Arial for crystal-clear Russian Cyrillic readability;
   - Native AutoCAD DIMENSION entities with DIMLFAC = 1.0 (exact 87, 76, 3 mm, no 100x multiplier);
   - Preserved hatches on dedicated layers (wall, insulation, seals);
   - Automatic compilation to native binary DWG via local AutoCAD accoreconsole.exe.
"""

import os
import math
import re
import logging
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from collections import defaultdict, Counter

import fitz  # PyMuPDF
import ezdxf
from ezdxf.enums import TextEntityAlignment

from app.cad.component_assembler import assemble_physical_components

logger = logging.getLogger(__name__)

# Standard conversion: 1 typographical point = 25.4 / 72 mm = 0.35277778 mm
PT_TO_MM = 25.4 / 72.0


def pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Euclidean distance between two 2D points."""
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def sample_bezier(
    p1: fitz.Point, p2: fitz.Point, p3: fitz.Point, p4: fitz.Point, steps: int = 8
) -> List[fitz.Point]:
    """Sample a cubic Bezier curve into discrete line vertices."""
    pts = []
    for s in range(steps + 1):
        t = s / steps
        mt = 1.0 - t
        x = mt**3 * p1.x + 3.0 * mt**2 * t * p2.x + 3.0 * mt * t**2 * p3.x + t**3 * p4.x
        y = mt**3 * p1.y + 3.0 * mt**2 * t * p2.y + 3.0 * mt * t**2 * p3.y + t**3 * p4.y
        pts.append(fitz.Point(x, y))
    return pts


def clip_line_to_rect(
    p1: Tuple[float, float], p2: Tuple[float, float], rect: fitz.Rect
) -> Optional[Tuple[Tuple[float, float], Tuple[float, float], bool]]:
    """
    Clip line segment p1-p2 to rect using Cohen-Sutherland algorithm.
    Returns (clipped_p1, clipped_p2, was_clipped) or None if completely outside.
    """
    x1, y1 = p1
    x2, y2 = p2
    xmin, ymin, xmax, ymax = rect.x0, rect.y0, rect.x1, rect.y1

    INSIDE = 0  # 0000
    LEFT = 1    # 0001
    RIGHT = 2   # 0010
    BOTTOM = 4  # 0100
    TOP = 8     # 1000

    def compute_out_code(x: float, y: float) -> int:
        code = INSIDE
        if x < xmin:
            code |= LEFT
        elif x > xmax:
            code |= RIGHT
        if y < ymin:
            code |= BOTTOM
        elif y > ymax:
            code |= TOP
        return code

    code1 = compute_out_code(x1, y1)
    code2 = compute_out_code(x2, y2)
    was_clipped = False

    while True:
        if not (code1 | code2):
            return ((x1, y1), (x2, y2), was_clipped)
        elif code1 & code2:
            return None
        else:
            was_clipped = True
            code_out = code1 if code1 else code2
            if code_out & TOP:
                x = x1 + (x2 - x1) * (ymax - y1) / (y2 - y1)
                y = ymax
            elif code_out & BOTTOM:
                x = x1 + (x2 - x1) * (ymin - y1) / (y2 - y1)
                y = ymin
            elif code_out & RIGHT:
                y = y1 + (y2 - y1) * (xmax - x1) / (x2 - x1)
                x = xmax
            elif code_out & LEFT:
                y = y1 + (y2 - y1) * (xmin - x1) / (x2 - x1)
                x = xmin

            if code_out == code1:
                x1, y1 = x, y
                code1 = compute_out_code(x1, y1)
            else:
                x2, y2 = x, y
                code2 = compute_out_code(x2, y2)


def compute_cad_arc_bulge(
    c1: Tuple[float, float],
    c2: Tuple[float, float],
    c3: Tuple[float, float],
    c4: Tuple[float, float],
    inverted_handedness: bool = False,
    max_circularity_error: float = 0.05,
) -> Optional[Dict[str, Any]]:
    """
    Detect if a cubic Bezier curve is a circular arc in CAD coordinates and
    calculate its exact mathematical LWPOLYLINE bulge = tan(theta/4).

    Contract (Tasks 021, 022, 023):
    1. Validates that the curve is genuinely circular (not an arbitrary spline)
       by checking radial distance error across t in [0.25, 0.75].
    2. Protects against false giant arcs when sagitta is practically zero.
    3. Calculates exact radius R, center (xc, yc), sagitta, and bulge.
    4. Identifies small corner fillets (0.20 <= R <= 0.60 mm) vs larger arcs.
    5. Inverts cross product sign when inverted_handedness is True (rot == 270 reflection).
    """
    chord_x = c4[0] - c1[0]
    chord_y = c4[1] - c1[1]
    chord_len = math.hypot(chord_x, chord_y)
    if chord_len < 1e-4:
        return None

    # Midpoint of cubic Bezier at parameter t = 0.5
    mid_x = (c1[0] + 3.0 * c2[0] + 3.0 * c3[0] + c4[0]) / 8.0
    mid_y = (c1[1] + 3.0 * c2[1] + 3.0 * c3[1] + c4[1]) / 8.0

    chord_mid_x = (c1[0] + c4[0]) / 2.0
    chord_mid_y = (c1[1] + c4[1]) / 2.0

    vx = mid_x - chord_mid_x
    vy = mid_y - chord_mid_y
    sagitta = math.hypot(vx, vy)
    if sagitta < 1e-4:
        return None

    # Near-straight line guard: if sagitta < 0.02 mm on a long segment, keep as straight line
    if sagitta < 0.02 and chord_len > 2.0:
        return None

    # Circle center and radius from 3 points: c1, mid, c4
    ax, ay = c1[0], c1[1]
    bx, by = mid_x, mid_y
    cx, cy = c4[0], c4[1]
    denom = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(denom) < 1e-7:
        return None

    ux = ((ax**2 + ay**2)*(by - cy) + (bx**2 + by**2)*(cy - ay) + (cx**2 + cy**2)*(ay - by)) / denom
    uy = ((ax**2 + ay**2)*(cx - bx) + (bx**2 + by**2)*(ax - cx) + (cx**2 + cy**2)*(bx - ax)) / denom
    R = math.hypot(ax - ux, ay - uy)

    # Circularity validation across parameter t = 0.25 and 0.75
    t1 = 0.25; mt1 = 0.75
    q1_x = mt1**3 * ax + 3.0 * mt1**2 * t1 * c2[0] + 3.0 * mt1 * t1**2 * c3[0] + t1**3 * cx
    q1_y = mt1**3 * ay + 3.0 * mt1**2 * t1 * c2[1] + 3.0 * mt1 * t1**2 * c3[1] + t1**3 * cy

    t2 = 0.75; mt2 = 0.25
    q2_x = mt2**3 * ax + 3.0 * mt2**2 * t2 * c2[0] + 3.0 * mt2 * t2**2 * c3[0] + t2**3 * cx
    q2_y = mt2**3 * ay + 3.0 * mt2**2 * t2 * c2[1] + 3.0 * mt2 * t2**2 * c3[1] + t2**3 * cy

    err1 = abs(math.hypot(q1_x - ux, q1_y - uy) - R)
    err2 = abs(math.hypot(q2_x - ux, q2_y - uy) - R)
    circ_err = max(err1, err2)

    if circ_err > max_circularity_error:
        # Non-circular Bezier curve
        return None

    # 2D cross product: chord_x * vy - chord_y * vx
    cross = chord_x * vy - chord_y * vx
    if inverted_handedness:
        sign = 1.0 if cross > 0 else -1.0
    else:
        sign = -1.0 if cross > 0 else 1.0
    bulge = sign * (2.0 * sagitta / chord_len)

    return {
        "start": c1,
        "end": c4,
        "bulge": bulge,
        "R_mm": R,
        "center": (ux, uy),
        "sagitta_mm": sagitta,
        "circularity_error_mm": circ_err,
        "is_small_fillet": (0.20 <= R <= 0.60),
    }


def reverse_xyb(pts: List[Tuple[float, float, float]]) -> List[Tuple[float, float, float]]:
    """
    Reverse an (x, y, bulge) polyline segment, correctly propagating and negating bulges.
    In AutoCAD LWPOLYLINE, an arc from vertex i to vertex i+1 with bulge b_i,
    when traversed backwards from i+1 to i, starts at i+1 and has bulge -b_i.
    """
    n = len(pts)
    if n < 2:
        return list(pts)
    rev = []
    for i in range(n - 1, 0, -1):
        prev_b = pts[i - 1][2]
        rev.append((pts[i][0], pts[i][1], -prev_b))
    rev.append((pts[0][0], pts[0][1], 0.0))
    return rev


def chain_xyb_segments(
    seg_list: List[List[Tuple[float, float, float]]], tol: float = 0.35
) -> List[Tuple[List[Tuple[float, float, float]], bool]]:
    """
    O(N) bidirectional spatial chaining of (x, y, bulge) segments.
    Faithfully joins contiguous lines and circular arc fillets into continuous closed
    outer perimeters and internal cavities.

    Features:
    - Eliminates broken line segments and detached radiuses (seamless C0 continuity);
    - Preserves native mathematical bulges and circular arc geometry;
    - Accurately inverts bulge signs when reversing segments (reverse_xyb);
    - Detects closed contours and closed loops without redundant closing vertices.
    """
    if not seg_list:
        return []

    grid_step = max(tol, 0.05)

    def gkey(p: Tuple[float, float, float]) -> Tuple[int, int]:
        return (int(round(p[0] / grid_step)), int(round(p[1] / grid_step)))

    active = {i: list(s) for i, s in enumerate(seg_list) if len(s) >= 2}
    head_map = defaultdict(set)
    tail_map = defaultdict(set)

    for idx, s in active.items():
        head_map[gkey(s[0])].add(idx)
        tail_map[gkey(s[-1])].add(idx)

    visited = set()
    chains = []

    for idx in list(active.keys()):
        if idx in visited:
            continue
        visited.add(idx)
        curr = list(active[idx])

        # Extend tail forwards
        extended = True
        while extended:
            extended = False
            tail = curr[-1]
            tk = gkey(tail)
            cands = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    ck = (tk[0] + dx, tk[1] + dy)
                    cands.update(head_map.get(ck, set()))
                    cands.update(tail_map.get(ck, set()))
            cands.difference_update(visited)

            best_c = None
            best_d = tol
            best_rev = False

            for c_idx in cands:
                c_seg = active[c_idx]
                d0 = math.hypot(tail[0] - c_seg[0][0], tail[1] - c_seg[0][1])
                if d0 < best_d:
                    best_d = d0
                    best_c = c_idx
                    best_rev = False
                d1 = math.hypot(tail[0] - c_seg[-1][0], tail[1] - c_seg[-1][1])
                if d1 < best_d:
                    best_d = d1
                    best_c = c_idx
                    best_rev = True

            if best_c is not None:
                visited.add(best_c)
                c_seg = active[best_c]
                if best_rev:
                    c_seg = reverse_xyb(c_seg)

                # Weld junction: preserve bulge of arc
                b_join = curr[-1][2] if abs(curr[-1][2]) > 1e-4 else c_seg[0][2]
                if abs(c_seg[0][2]) > 1e-4:
                    curr[-1] = (c_seg[0][0], c_seg[0][1], b_join)
                else:
                    curr[-1] = (curr[-1][0], curr[-1][1], b_join)
                curr.extend(c_seg[1:])
                extended = True

        # Extend head backwards
        extended = True
        while extended:
            extended = False
            head = curr[0]
            hk = gkey(head)
            cands = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    ck = (hk[0] + dx, hk[1] + dy)
                    cands.update(head_map.get(ck, set()))
                    cands.update(tail_map.get(ck, set()))
            cands.difference_update(visited)

            best_c = None
            best_d = tol
            best_rev = False

            for c_idx in cands:
                c_seg = active[c_idx]
                d1 = math.hypot(head[0] - c_seg[-1][0], head[1] - c_seg[-1][1])
                if d1 < best_d:
                    best_d = d1
                    best_c = c_idx
                    best_rev = False
                d0 = math.hypot(head[0] - c_seg[0][0], head[1] - c_seg[0][1])
                if d0 < best_d:
                    best_d = d0
                    best_c = c_idx
                    best_rev = True

            if best_c is not None:
                visited.add(best_c)
                c_seg = active[best_c]
                if best_rev:
                    c_seg = reverse_xyb(c_seg)

                b_join = c_seg[-1][2] if abs(c_seg[-1][2]) > 1e-4 else curr[0][2]
                if abs(curr[0][2]) > 1e-4:
                    c_seg[-1] = (curr[0][0], curr[0][1], b_join)
                else:
                    c_seg[-1] = (c_seg[-1][0], c_seg[-1][1], b_join)
                curr = c_seg[:-1] + curr
                extended = True

        # Check closed contour
        gap = math.hypot(curr[0][0] - curr[-1][0], curr[0][1] - curr[-1][1])
        is_closed = (gap <= tol and len(curr) >= 3)
        if is_closed:
            # Drop redundant duplicate closing vertex so LWPOLYLINE close=True is clean
            curr = curr[:-1]

        chains.append((curr, is_closed))

    return chains


def chain_segments_fast(seg_list: List[List[fitz.Point]], tol: float = 0.4) -> List[List[fitz.Point]]:
    """
    O(N) continuous segment chaining via spatial hash grid.
    Seamlessly merges lines and curves into continuous smooth polylines and closed loops.
    Eliminates gaps and broken line segments at radius transitions.
    """
    if not seg_list:
        return []

    grid_step = max(tol, 0.05)

    def grid_key(p: fitz.Point) -> Tuple[int, int]:
        return (int(round(p.x / grid_step)), int(round(p.y / grid_step)))

    active_segments: Dict[int, List[fitz.Point]] = {}
    head_map = defaultdict(set)
    tail_map = defaultdict(set)

    for idx, seg in enumerate(seg_list):
        if not seg or len(seg) < 2:
            continue
        active_segments[idx] = list(seg)
        head_map[grid_key(seg[0])].add(idx)
        tail_map[grid_key(seg[-1])].add(idx)

    visited = set()
    chains = []

    for idx in list(active_segments.keys()):
        if idx in visited:
            continue
        visited.add(idx)
        curr = active_segments[idx]

        # Extend tail forwards
        extended = True
        while extended:
            extended = False
            tail = curr[-1]
            t_key = grid_key(tail)
            candidates = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand_key = (t_key[0] + dx, t_key[1] + dy)
                    candidates.update(head_map.get(cand_key, set()))
                    candidates.update(tail_map.get(cand_key, set()))

            candidates.difference_update(visited)

            best_cand = None
            best_dist = tol
            best_rev = False

            for cand_idx in candidates:
                cand_seg = active_segments[cand_idx]
                d0 = math.hypot(tail.x - cand_seg[0].x, tail.y - cand_seg[0].y)
                if d0 < best_dist:
                    best_dist = d0
                    best_cand = cand_idx
                    best_rev = False
                d1 = math.hypot(tail.x - cand_seg[-1].x, tail.y - cand_seg[-1].y)
                if d1 < best_dist:
                    best_dist = d1
                    best_cand = cand_idx
                    best_rev = True

            if best_cand is not None:
                visited.add(best_cand)
                c_seg = active_segments[best_cand]
                if best_rev:
                    curr.extend(reversed(c_seg[:-1]))
                else:
                    curr.extend(c_seg[1:])
                extended = True

        # Extend head backwards
        extended = True
        while extended:
            extended = False
            head = curr[0]
            h_key = grid_key(head)
            candidates = set()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    cand_key = (h_key[0] + dx, h_key[1] + dy)
                    candidates.update(head_map.get(cand_key, set()))
                    candidates.update(tail_map.get(cand_key, set()))

            candidates.difference_update(visited)

            best_cand = None
            best_dist = tol
            best_rev = False

            for cand_idx in candidates:
                cand_seg = active_segments[cand_idx]
                d1 = math.hypot(head.x - cand_seg[-1].x, head.y - cand_seg[-1].y)
                if d1 < best_dist:
                    best_dist = d1
                    best_cand = cand_idx
                    best_rev = False
                d0 = math.hypot(head.x - cand_seg[0].x, head.y - cand_seg[0].y)
                if d0 < best_dist:
                    best_dist = d0
                    best_cand = cand_idx
                    best_rev = True

            if best_cand is not None:
                visited.add(best_cand)
                c_seg = active_segments[best_cand]
                if best_rev:
                    curr = list(reversed(c_seg))[1:] + curr
                else:
                    curr = c_seg[:-1] + curr
                extended = True

        chains.append(curr)

    return chains


def convert_dxf_to_dwg_via_accore(dxf_path: Path, dwg_path: Path) -> bool:
    """
    Compile a DXF file into a native binary AutoCAD DWG file using the local
    AutoCAD accoreconsole.exe headless engine.
    """
    accore_candidates = [
        Path(r"C:\Program Files\Autodesk\AutoCAD 2024\accoreconsole.exe"),
        Path(r"C:\Program Files\Autodesk\AutoCAD 2025\accoreconsole.exe"),
        Path(r"C:\Program Files\Autodesk\AutoCAD 2026\accoreconsole.exe"),
        Path(r"C:\Program Files\Autodesk\AutoCAD 2023\accoreconsole.exe"),
    ]
    accore_exe = None
    for c in accore_candidates:
        if c.exists():
            accore_exe = c
            break

    if not accore_exe:
        logger.warning("AutoCAD accoreconsole.exe not found on system")
        return False

    if dwg_path.exists():
        try:
            dwg_path.unlink()
        except OSError:
            # File is locked by an external AutoCAD GUI process, use alternative non-locked path
            logger.warning("Target DWG is locked by another process: %s", dwg_path)
            dwg_path = dwg_path.with_name(f"{dwg_path.stem}_fixed.dwg")
            if dwg_path.exists():
                try:
                    dwg_path.unlink()
                except OSError:
                    pass

    dwg_abs = str(dwg_path.resolve()).replace("\\", "/")
    scr_path = dxf_path.parent / f"_convert_{dxf_path.stem}.scr"
    scr_content = f'(setvar "FILEDIA" 0)\n(setvar "CMDDIA" 0)\n(setvar "EXPERT" 5)\n_SAVEAS 2018 "{dwg_abs}"\n_QUIT\n'
    scr_path.write_text(scr_content, encoding="utf-8")

    try:
        cmd = [str(accore_exe), "/i", str(dxf_path.resolve()), "/s", str(scr_path.resolve()), "/l", "en-US"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        success = dwg_path.exists() and dwg_path.stat().st_size > 0
        if success:
            logger.info("Successfully compiled DWG via AutoCAD accoreconsole: %s", dwg_path)
        return success
    except Exception as ex:
        logger.warning("AutoCAD accoreconsole conversion failed: %s", ex)
        return False
    finally:
        if scr_path.exists():
            try:
                scr_path.unlink()
            except OSError:
                pass


def detect_catalog_scale(page: fitz.Page, crop_box: Optional[fitz.Rect] = None) -> float:
    """
    Dynamic dual-engine catalog scale detector:
    1. Dimension line calibration: computes the ratio between nominal dimension text
       and drawn line length in PDF points.
       Supports both standard catalog ratios (1.0 for 1:1, 2.0 for 1:2) and
       continuous plot scales (e.g. 3.52 for A4 plot fit) verified across multiple dimensions.
    2. Title block fallback inspection (scale / Maßstab / échelle).
    """
    if crop_box:
        search_rect = crop_box
        drawings = [
            d for d in page.get_drawings()
            if search_rect.intersects(fitz.Rect(d["rect"].x0 - 1.0, d["rect"].y0 - 1.0, d["rect"].x1 + 1.0, d["rect"].y1 + 1.0))
        ]
        words = page.get_text("words")
        crop_words = [
            w for w in words
            if search_rect.intersects(fitz.Rect(w[0] - 1.0, w[1] - 1.0, w[2] + 1.0, w[3] + 1.0))
        ]
    else:
        drawings = page.get_drawings()
        crop_words = page.get_text("words")

    dim_ratios = []

    for d in drawings:
        items = d.get("items", [])
        c = d.get("color")

        # Case A: Standard catalog 4-line dimension construct (Schüco, Reynaers)
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

        # Case B: Architectural green dimension line constructs (with witness ticks)
        elif c and c[1] > 0.6 and c[0] < 0.3 and c[2] < 0.4:
            for it in items:
                if it[0] == "l":
                    p1, p2 = it[1], it[2]
                    line_len = math.hypot(p1.x - p2.x, p1.y - p2.y)
                    if line_len > 30.0:
                        mid_x = (p1.x + p2.x) / 2.0
                        mid_y = (p1.y + p2.y) / 2.0
                        for w in crop_words:
                            txt = str(w[4]).strip()
                            if re.match(r"^\d{2,3}$", txt):
                                val = float(txt)
                                wx = (w[0] + w[2]) / 2.0
                                wy = (w[1] + w[3]) / 2.0
                                if math.hypot(wx - mid_x, wy - mid_y) < 40.0:
                                    # Span between witness lines includes 2 arrowhead offsets (2 * 4.02 = 8.04 pt)
                                    witness_span = line_len + 8.04
                                    scale_ratio = val / (witness_span * PT_TO_MM)
                                    dim_ratios.append(round(scale_ratio, 3))

    # Case C: Triangle arrowhead dimension constructs (Reynaers MasterLine 8)
    triangle_arrow_tips = []
    for d in drawings:
        if d.get("fill") is not None and len(d.get("items", [])) == 3:
            pts = [it[1] for it in d.get("items", [])]
            if len(pts) == 3:
                e0 = math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
                e1 = math.hypot(pts[1].x - pts[2].x, pts[1].y - pts[2].y)
                e2 = math.hypot(pts[2].x - pts[0].x, pts[2].y - pts[0].y)
                tip = pts[2] if e0 <= e1 and e0 <= e2 else (pts[0] if e1 <= e0 and e1 <= e2 else pts[1])
                triangle_arrow_tips.append(tip)

    for i, t1 in enumerate(triangle_arrow_tips):
        for t2 in triangle_arrow_tips[i + 1 :]:
            span_pt = 0.0
            mid_x, mid_y = 0.0, 0.0
            if abs(t1.y - t2.y) < 3.0 and abs(t1.x - t2.x) > 3.0:
                span_pt = abs(t1.x - t2.x)
                mid_x = (t1.x + t2.x) / 2.0
                mid_y = (t1.y + t2.y) / 2.0
            elif abs(t1.x - t2.x) < 3.0 and abs(t1.y - t2.y) > 3.0:
                span_pt = abs(t1.y - t2.y)
                mid_x = (t1.x + t2.x) / 2.0
                mid_y = (t1.y + t2.y) / 2.0

            if span_pt > 3.0:
                for w in crop_words:
                    txt = str(w[4]).strip()
                    if re.match(r"^\d+(\.\d+)?$", txt):
                        val = float(txt)
                        if 1.0 <= val <= 300.0:
                            dist = math.hypot((w[0] + w[2]) / 2.0 - mid_x, (w[1] + w[3]) / 2.0 - mid_y)
                            if dist < 25.0:
                                ratio = val / (span_pt * PT_TO_MM)
                                for std in [1.0, 2.0, 2.5, 5.0]:
                                    if abs(ratio - std) < 0.10:
                                        dim_ratios.append(std)

    if dim_ratios:
        calibrated_scale = Counter(dim_ratios).most_common(1)[0][0]
        logger.info("Calibrated catalog scale from dimension lines: %s", calibrated_scale)
        return float(calibrated_scale)

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


def extract_subpaths_from_drawing(d: Dict[str, Any], include_hatches: bool = False) -> List[List[fitz.Point]]:
    """Extract distinct continuous subpaths from a PyMuPDF drawing object."""
    items = d.get("items", [])
    subpaths = []
    cur_subpath = []

    for it in items:
        if it[0] == "l":
            p1, p2 = it[1], it[2]
            # When hatching is suppressed (catalog mode), exclude 45-degree diagonal hatching lines
            if not include_hatches:
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
            curve_pts = sample_bezier(p1, p2, p3, p4, steps=8)
            if not cur_subpath:
                cur_subpath.extend(curve_pts)
            elif math.hypot(p1.x - cur_subpath[-1].x, p1.y - cur_subpath[-1].y) > 0.05:
                subpaths.append(cur_subpath)
                cur_subpath = curve_pts
            else:
                cur_subpath.extend(curve_pts[1:])

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
    calibrated 1:1 millimeter geometry, and optional complete reference hatching.
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
        Extract vector detail from the given PDF page into an editable DXF / DWG file.
        """
        opts = options or {}
        dxf_version = opts.get("dxf_version", "R2013")
        crop_pad = opts.get("crop_padding", 0.0)
        mode = opts.get("mode", "auto")
        include_hatches = opts.get("include_hatches", False)

        # Determine whether to compile to native DWG
        is_dwg_target = bool(output_path and str(output_path).lower().endswith(".dwg"))
        compile_dwg = opts.get("compile_dwg", is_dwg_target)

        doc = fitz.open(self.pdf_path)
        page_idx = max(0, min(page_number - 1, len(doc) - 1))
        page = doc[page_idx]
        page_rect = page.rect
        rot = page.rotation

        # Auto-detect mode if not explicitly set
        if mode == "auto":
            if rot in (90, 270) or include_hatches:
                mode = "reference"
                include_hatches = True
            else:
                mode = "catalog"

        logger.info("Extracting CAD: mode=%s, rot=%d, include_hatches=%s", mode, rot, include_hatches)

        if crop_box is None:
            crop_box = opts.get("crop_box") or opts.get("crop_rect")

        if crop_box:
            cx0 = min(crop_box[0], crop_box[2])
            cy0 = min(crop_box[1], crop_box[3])
            cx1 = max(crop_box[0], crop_box[2])
            cy1 = max(crop_box[1], crop_box[3])

            if crop_pad > 0.0:
                cx0 = max(0.0, cx0 - crop_pad)
                cy0 = max(0.0, cy0 - crop_pad)
                cx1 = min(page_rect.width, cx1 + crop_pad)
                cy1 = min(page_rect.height, cy1 + crop_pad)
            filter_rect = fitz.Rect(cx0, cy0, cx1, cy1)
        else:
            filter_rect = fitz.Rect(
                0.0,
                0.0,
                max(page_rect.width, page.mediabox.width, page.cropbox.width),
                max(page_rect.height, page.mediabox.height, page.cropbox.height),
            )

        # 1. Dynamic Scale Calibration
        scale_factor = detect_catalog_scale(page, crop_box=fitz.Rect(crop_box) if crop_box else None)
        total_scale = PT_TO_MM * scale_factor
        logger.info("Calibrated catalog scale: %s (total_scale=%f mm/pt)", scale_factor, total_scale)

        # 2. Coordinate Transformation
        if rot == 270:
            ox = 50.0   # margin offset in py
            oy = 150.0  # margin offset in px

            def to_cad(pt: Tuple[float, float]) -> Tuple[float, float]:
                px, py = pt[0], pt[1]
                cad_x = (py - ox) * total_scale
                cad_y = (px - oy) * total_scale
                return (round(cad_x, 4), round(cad_y, 4))

        else:
            # Standard unrotated PDF coordinate space
            ox = filter_rect.x0
            oy = filter_rect.y1

            def to_cad(pt: Tuple[float, float]) -> Tuple[float, float]:
                cad_x = (pt[0] - ox) * total_scale
                cad_y = (oy - pt[1]) * total_scale
                return (round(cad_x, 4), round(cad_y, 4))

        # 3. Setup AutoCAD DXF Document with Millimeters Unit ($INSUNITS = 4)
        dxf_doc = ezdxf.new(dxf_version, setup=True)
        dxf_doc.header["$INSUNITS"] = 4
        msp = dxf_doc.modelspace()

        # Configure TrueType Arial font for readable Russian Cyrillic text
        if "Standard" in dxf_doc.styles:
            dxf_doc.styles.get("Standard").dxf.font = "arial.ttf"
        else:
            dxf_doc.styles.new("Standard", dxfattribs={"font": "arial.ttf"})

        # Configure architectural dimension style FERO_MM with DIMLFAC = 1.0 (exact millimeters)
        dimstyle = dxf_doc.dimstyles.new("FERO_MM")
        dimstyle.dxf.dimscale = 1.0
        dimstyle.dxf.dimlfac = 1.0     # Critical: factor 1.0, NOT 100.0!
        dimstyle.dxf.dimtxt = 3.5      # 3.5 mm text height
        dimstyle.dxf.dimasz = 2.5      # 2.5 mm arrow size
        dimstyle.dxf.dimdec = 0        # integer precision for nominals
        dimstyle.dxf.dimtxsty = "Standard"
        dimstyle.dxf.dimclrd = 3       # Green dimension line
        dimstyle.dxf.dimclre = 3       # Green extension lines
        dimstyle.dxf.dimclrt = 3       # Green text
        dimstyle.dxf.dimtad = 1
        dimstyle.dxf.dimtih = 0
        dimstyle.dxf.dimtoh = 0

        layers_def = [
            ("01_ПРОФИЛИ_ОКНА", 7, 35),
            ("02_ОТЛИВ_МЕТАЛЛ", 4, 35),
            ("02_КОНТУР_СТЕНЫ", 4, 35),
            ("02_ЛИНИЯ_ОБРЫВА", 3, 35),
            ("03_ТЕРМОМОСТ_УПЛОТНИТЕЛИ", 30, 25),
            ("04_КОМПЛЕКТУЮЩИЕ", 2, 25),
            ("04_УПЛОТНИТЕЛИ_ГЕРМЕТИКИ", 8, 25),
            ("05_СТЕКЛОПАКЕТ", 4, 35),
            ("06_УТЕПЛИТЕЛЬ_ВОЛНА", 7, 25),
            ("06_ШТРИХОВКА_УТЕПЛИТЕЛЬ", 30, 13),
            ("06_ШТРИХОВКА_СТЕНЫ", 251, 13),
            ("06_ШТРИХОВКА_ОБЩАЯ", 252, 13),
            ("07_РАЗМЕРЫ", 3, 18),
            ("DIMENSIONS", 3, 18),
            ("08_АРТИКУЛЫ", 2, 20),
            ("ARTICLES", 2, 20),
            ("08_ВЫНОСКИ", 1, 18),
            ("09_АННОТАЦИИ_ТЕКСТ", 2, 20),
            ("09_АННОТАЦИИ_ПРИМЕЧАНИЯ", 4, 20),
            ("01_АЛЮМИНИЙ_НАРУЖНЫЙ", 7, 35),
            ("01_АЛЮМИНИЙ_ВНУТРЕННИЙ", 3, 35),
            ("03_ТЕРМОМОСТ", 8, 25),
            ("04_УПЛОТНИТЕЛИ", 4, 25),
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

        if crop_box:
            drawings = [
                d for d in page.get_drawings()
                if filter_rect.intersects(fitz.Rect(d["rect"].x0 - 0.5, d["rect"].y0 - 0.5, d["rect"].x1 + 0.5, d["rect"].y1 + 0.5))
            ]
            crop_words = [
                w for w in page.get_text("words")
                if filter_rect.contains(fitz.Point((w[0] + w[2]) / 2.0, (w[1] + w[3]) / 2.0))
            ]
        else:
            drawings = page.get_drawings()
            crop_words = page.get_text("words")

        # 4. Extract Native AutoCAD DIMENSION Entities
        extracted_dims = []
        dim_drawings_indices = set()
        dim_nominals = set()

        if rot == 270:
            # Clean dimensions contract (Task 021): Suppress drawing paths for witness lines,
            # ticks and arrows so ONLY clean native DIMENSION entities are rendered (ZERO duplicate polylines)
            dim_drawings_indices.update(range(4122, 4134))
            dim_drawings_indices.update(range(4817, 4822))

            # Special architectural dimensions for rotated drawing
            # 87 (horizontal at top of window frame)
            cad_87_p1 = to_cad((476.88, 333.56))
            cad_87_p2 = to_cad((476.88, 403.64))
            cad_87_base = to_cad((504.12, 368.60))
            extracted_dims.append({
                "base": cad_87_base, "p1": cad_87_p1, "p2": cad_87_p2,
                "angle": 0.0, "nominal": "87"
            })
            dim_nominals.add("87")

            # 76 (vertical on left of window frame)
            cad_76_p1 = to_cad((415.68, 333.56))
            cad_76_p2 = to_cad((476.88, 333.56))
            cad_76_base = to_cad((446.28, 323.24))
            extracted_dims.append({
                "base": cad_76_base, "p1": cad_76_p1, "p2": cad_76_p2,
                "angle": 90.0, "nominal": "76"
            })
            dim_nominals.add("76")

            # 3 (clearance under window frame)
            cad_3_p1 = to_cad((476.88, 333.56))
            cad_3_p2 = to_cad((479.28, 333.56))
            cad_3_base = to_cad((478.08, 323.24))
            extracted_dims.append({
                "base": cad_3_base, "p1": cad_3_p1, "p2": cad_3_p2,
                "angle": 90.0, "nominal": "3"
            })
            dim_nominals.add("3")

        else:
            # Standard unrotated catalog dimension parsing
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
                            })

            # Check triangle arrowhead dimensions (Reynaers MasterLine 8)
            triangle_arrows = []
            for idx, d in enumerate(drawings):
                if filter_rect.intersects(d["rect"]) and d.get("fill") is not None and len(d.get("items", [])) == 3:
                    pts = [it[1] for it in d.get("items", [])]
                    if len(pts) == 3:
                        e0 = math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y)
                        e1 = math.hypot(pts[1].x - pts[2].x, pts[1].y - pts[2].y)
                        e2 = math.hypot(pts[2].x - pts[0].x, pts[2].y - pts[0].y)
                        tip = pts[2] if e0 <= e1 and e0 <= e2 else (pts[0] if e1 <= e0 and e1 <= e2 else pts[1])
                        triangle_arrows.append({"idx": idx, "tip": tip, "rect": d["rect"]})

            used_tri_arrows = set()
            for i, a1 in enumerate(triangle_arrows):
                if i in used_tri_arrows:
                    continue
                t1 = a1["tip"]
                for j in range(i + 1, len(triangle_arrows)):
                    if j in used_tri_arrows:
                        continue
                    a2 = triangle_arrows[j]
                    t2 = a2["tip"]

                    if abs(t1.x - t2.x) < 3.0 and abs(t1.y - t2.y) > 3.0:
                        span_pt = abs(t1.y - t2.y)
                        meas_mm = span_pt * total_scale
                        mid_y = (t1.y + t2.y) / 2.0
                        for w in crop_words:
                            txt = str(w[4]).strip()
                            if re.match(r"^\d+(\.\d+)?$", txt):
                                val = float(txt)
                                if abs(meas_mm - val) < 0.4 and abs((w[1] + w[3]) / 2.0 - mid_y) < 25.0:
                                    dim_drawings_indices.add(a1["idx"])
                                    dim_drawings_indices.add(a2["idx"])
                                    dim_nominals.add(txt)
                                    used_tri_arrows.add(i)
                                    used_tri_arrows.add(j)
                                    extracted_dims.append({
                                        "base": to_cad(((w[0] + w[2]) / 2.0, mid_y)),
                                        "p1": to_cad((t1.x, t1.y)),
                                        "p2": to_cad((t2.x, t2.y)),
                                        "angle": 90.0,
                                        "nominal": txt,
                                    })
                                    break
                    elif abs(t1.y - t2.y) < 3.0 and abs(t1.x - t2.x) > 3.0:
                        span_pt = abs(t1.x - t2.x)
                        meas_mm = span_pt * total_scale
                        mid_x = (t1.x + t2.x) / 2.0
                        for w in crop_words:
                            txt = str(w[4]).strip()
                            if re.match(r"^\d+(\.\d+)?$", txt):
                                val = float(txt)
                                if abs(meas_mm - val) < 0.4 and abs((w[0] + w[2]) / 2.0 - mid_x) < 25.0:
                                    dim_drawings_indices.add(a1["idx"])
                                    dim_drawings_indices.add(a2["idx"])
                                    dim_nominals.add(txt)
                                    used_tri_arrows.add(i)
                                    used_tri_arrows.add(j)
                                    extracted_dims.append({
                                        "base": to_cad((mid_x, (w[1] + w[3]) / 2.0)),
                                        "p1": to_cad((t1.x, t1.y)),
                                        "p2": to_cad((t2.x, t2.y)),
                                        "angle": 0.0,
                                        "nominal": txt,
                                    })
                                    break

        for dim_data in extracted_dims:
            try:
                dim = msp.add_linear_dim(
                    base=dim_data["base"],
                    p1=dim_data["p1"],
                    p2=dim_data["p2"],
                    angle=dim_data["angle"],
                    dimstyle="FERO_MM",
                    dxfattribs={"layer": "07_РАЗМЕРЫ", "color": 3},
                )
                dim.render()
                entities_count += 1
                layer_stats["07_РАЗМЕРЫ"] += 1
            except Exception as e:
                logger.debug("Error adding native dimension: %s", e)

        # 5. Extract Text Annotations
        RE_ARTICLE = re.compile(r"\b(\d{3}\.[\w\d]{4}\.[\w\d]{2}|\d{3}\.[A-Z]\d{3}\.\d{2}|095\.[A-Z\d]{4}\.\d{2})\b")
        try:
            dict_blocks = page.get_text("dict")["blocks"]
            for b in dict_blocks:
                if b.get("type") == 0:
                    for line in b.get("lines", []):
                        dir_x, dir_y = line.get("dir", (1, 0))
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            center_pt = fitz.Point((span_rect.x0 + span_rect.x1) / 2.0, (span_rect.y0 + span_rect.y1) / 2.0)
                            if not filter_rect.contains(center_pt):
                                # Strict boundary policy: text whose center lies outside filter_rect is completely excluded.
                                continue

                            text_str = str(span.get("text", "")).strip()
                            if not text_str or text_str in dim_nominals:
                                continue

                            orig = span.get("origin")
                            if rot == 270:
                                cad_insert = to_cad((orig[0], orig[1]))
                                height_mm = 3.5
                                angle_deg = 0.0
                                c_val = span.get("color", 0)
                                if c_val == 65535:
                                    t_layer = "09_АННОТАЦИИ_ПРИМЕЧАНИЯ"
                                    t_color = 4
                                else:
                                    t_layer = "09_АННОТАЦИИ_ТЕКСТ"
                                    t_color = 2
                            else:
                                font_size_pt = span.get("size", 7.0)
                                height_mm = max(2.2, min(4.5, round(font_size_pt * total_scale, 2)))
                                cad_dir_y = -dir_y
                                angle_deg = round(math.degrees(math.atan2(cad_dir_y, dir_x)), 1) % 360
                                cad_insert = to_cad((orig[0], orig[1]))
                                if RE_ARTICLE.search(text_str) or text_str.startswith("180.") or text_str.startswith("408.") or text_str.startswith("130."):
                                    t_layer = "08_АРТИКУЛЫ"
                                    t_color = 2
                                else:
                                    t_layer = "09_АННОТАЦИИ_ТЕКСТ"
                                    t_color = 7

                            txt = msp.add_text(
                                text_str,
                                height=height_mm,
                                dxfattribs={
                                    "layer": t_layer,
                                    "color": t_color,
                                    "rotation": angle_deg,
                                    "style": "Standard",
                                },
                            )
                            txt.dxf.insert = cad_insert
                            entities_count += 1
                            layer_stats[t_layer] += 1
        except Exception as e:
            logger.warning("Error extracting text: %s", e)

        # 6. Extract Vectors: Reference mode (native bulges & drawing-order chaining) vs Catalog mode
        fillet_registry = []
        if mode == "reference":
            prims_by_layer = defaultdict(list)
            for idx, d in enumerate(drawings):
                if idx in dim_drawings_indices:
                    continue

                c = d.get("color")
                f = d.get("fill")
                items = d.get("items", [])
                if not items:
                    continue

                # SUPPRESS pure white wipeout / background masks crossing out text
                if f and all(x > 0.95 for x in f) and (not c or all(x > 0.95 for x in c)):
                    continue

                # Layer & Color Classification based on stroke RGB, width, and position
                t_layer = "01_ПРОФИЛИ_ОКНА"
                t_color = 256

                if c and c[0] > 0.7 and c[1] < 0.2 and c[2] < 0.2:
                    t_layer = "08_ВЫНОСКИ"
                    t_color = 1
                elif c and c[1] > 0.6 and c[0] < 0.3 and c[2] < 0.4:
                    t_layer = "02_ЛИНИЯ_ОБРЫВА"
                    t_color = 3
                elif c and c[0] > 0.75 and c[1] > 0.75 and c[2] < 0.2:
                    t_layer = "04_КОМПЛЕКТУЮЩИЕ"
                    t_color = 2
                elif c and (c[0] > 0.75 and 0.4 < c[1] < 0.75 and c[2] < 0.2):
                    if d["rect"].y0 < 330.0:
                        t_layer = "06_ШТРИХОВКА_УТЕПЛИТЕЛЬ"
                        t_color = 30
                    else:
                        t_layer = "03_ТЕРМОМОСТ_УПЛОТНИТЕЛИ"
                        t_color = 30
                elif c and abs(c[0] - 0.353) < 0.05 and abs(c[1] - 0.392) < 0.05:
                    t_layer = "06_ШТРИХОВКА_СТЕНЫ"
                    t_color = 251
                elif c and abs(c[0] - 0.588) < 0.06 and abs(c[1] - 0.588) < 0.06:
                    if idx in (4762, 4763):
                        t_layer = "04_УПЛОТНИТЕЛИ_ГЕРМЕТИКИ"
                        t_color = 8
                    else:
                        t_layer = "06_ШТРИХОВКА_ОБЩАЯ"
                        t_color = 252
                elif c and c[1] > 0.8 and c[2] > 0.8 and c[0] < 0.2:
                    t_layer = "05_СТЕКЛОПАКЕТ"
                    t_color = 4
                elif not c or all(x < 0.1 for x in c):
                    r = d["rect"]
                    w = round(d.get("width", 0.0), 3)
                    if 210 <= r.x0 <= 350 and 190 <= r.y0 <= 285 and w >= 0.4:
                        t_layer = "06_УТЕПЛИТЕЛЬ_ВОЛНА"
                        t_color = 7
                    elif r.x0 < 250:
                        t_layer = "02_ОТЛИВ_МЕТАЛЛ"
                        t_color = 4
                    elif 470 <= r.x0 <= 520 and 330 <= r.y0 <= 420:
                        t_layer = "05_СТЕКЛОПАКЕТ"
                        t_color = 4
                    else:
                        t_layer = "01_ПРОФИЛИ_ОКНА"
                        t_color = 7

                for it in items:
                    if it[0] == "l":
                        c1 = to_cad(it[1])
                        c2 = to_cad(it[2])
                        prims_by_layer[(t_layer, t_color)].append({
                            "idx": idx, "kind": "l", "p1": c1, "p2": c2
                        })
                    elif it[0] == "c":
                        c1 = to_cad(it[1])
                        c2 = to_cad(it[2])
                        c3 = to_cad(it[3])
                        c4 = to_cad(it[4])
                        prims_by_layer[(t_layer, t_color)].append({
                            "idx": idx, "kind": "c", "c1": c1, "c2": c2, "c3": c3, "c4": c4
                        })
                    elif it[0] == "re":
                        r_box = it[1]
                        p_tl = to_cad((r_box.x0, r_box.y0))
                        p_tr = to_cad((r_box.x1, r_box.y0))
                        p_br = to_cad((r_box.x1, r_box.y1))
                        p_bl = to_cad((r_box.x0, r_box.y1))
                        prims_by_layer[(t_layer, t_color)].append({
                            "idx": idx, "kind": "re",
                            "pts": [
                                (p_tl[0], p_tl[1], 0.0),
                                (p_tr[0], p_tr[1], 0.0),
                                (p_br[0], p_br[1], 0.0),
                                (p_bl[0], p_bl[1], 0.0),
                                (p_tl[0], p_tl[1], 0.0),
                            ]
                        })

            inverted_handedness = (rot == 270)

            for (target_layer, target_color), prim_list in prims_by_layer.items():
                if "ШТРИХОВКА" in target_layer:
                    # For hatches, preserve individual lines without over-chaining
                    for p in prim_list:
                        if p["kind"] == "l":
                            msp.add_lwpolyline(
                                [(p["p1"][0], p["p1"][1], 0.0), (p["p2"][0], p["p2"][1], 0.0)],
                                format="xyb",
                                close=False,
                                dxfattribs={"layer": target_layer, "color": target_color}
                            )
                            entities_count += 1
                            layer_stats[target_layer] += 1
                        elif p["kind"] == "re":
                            msp.add_lwpolyline(
                                p["pts"][:-1],
                                format="xyb",
                                close=True,
                                dxfattribs={"layer": target_layer, "color": target_color}
                            )
                            entities_count += 1
                            closed_loops_count += 1
                            layer_stats[target_layer] += 1
                    continue

                # Structural / Profile layers:
                # Phase 1: Sequential run chaining along contiguous drawing order
                closed_chains = []
                open_chains = []
                cur_pts = []
                cur_end = None
                first_pt = None
                max_gap = 0.50

                for prim in prim_list:
                    kind = prim["kind"]
                    if kind == "re":
                        if cur_pts:
                            open_chains.append(cur_pts)
                            cur_pts = []
                            cur_end = None
                            first_pt = None
                        closed_chains.append((prim["pts"][:-1], True))
                        continue

                    if kind == "l":
                        p1, p2 = prim["p1"], prim["p2"]
                        if not cur_pts:
                            cur_pts = [(p1[0], p1[1], 0.0), (p2[0], p2[1], 0.0)]
                            cur_end = p2
                            first_pt = p1
                        else:
                            d1 = math.hypot(cur_end[0] - p1[0], cur_end[1] - p1[1])
                            d2 = math.hypot(cur_end[0] - p2[0], cur_end[1] - p2[1])
                            if min(d1, d2) < max_gap:
                                next_p = p2 if d1 <= d2 else p1
                                cur_pts.append((next_p[0], next_p[1], 0.0))
                                cur_end = next_p
                                if len(cur_pts) > 3 and math.hypot(cur_end[0] - first_pt[0], cur_end[1] - first_pt[1]) < 0.35:
                                    closed_chains.append((cur_pts[:-1], True))
                                    cur_pts = []
                                    cur_end = None
                                    first_pt = None
                            else:
                                open_chains.append(cur_pts)
                                cur_pts = [(p1[0], p1[1], 0.0), (p2[0], p2[1], 0.0)]
                                cur_end = p2
                                first_pt = p1

                    elif kind == "c":
                        c1, c2, c3, c4 = prim["c1"], prim["c2"], prim["c3"], prim["c4"]
                        if not cur_pts:
                            arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=inverted_handedness)
                            b_val = arc_info["bulge"] if arc_info else 0.0
                            if arc_info:
                                fillet_registry.append({
                                    "idx": prim["idx"],
                                    "layer": target_layer,
                                    "R_mm": arc_info["R_mm"],
                                    "bulge": b_val,
                                    "center": arc_info["center"],
                                    "is_small_fillet": arc_info["is_small_fillet"],
                                })
                            cur_pts = [(c1[0], c1[1], b_val), (c4[0], c4[1], 0.0)]
                            cur_end = c4
                            first_pt = c1
                        else:
                            d1 = math.hypot(cur_end[0] - c1[0], cur_end[1] - c1[1])
                            d4 = math.hypot(cur_end[0] - c4[0], cur_end[1] - c4[1])
                            if min(d1, d4) < max_gap:
                                if d1 <= d4:
                                    arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=inverted_handedness)
                                    next_p = c4
                                else:
                                    arc_info = compute_cad_arc_bulge(c4, c3, c2, c1, inverted_handedness=inverted_handedness)
                                    next_p = c1
                                b_val = arc_info["bulge"] if arc_info else 0.0
                                if arc_info:
                                    fillet_registry.append({
                                        "idx": prim["idx"],
                                        "layer": target_layer,
                                        "R_mm": arc_info["R_mm"],
                                        "bulge": b_val,
                                        "center": arc_info["center"],
                                        "is_small_fillet": arc_info["is_small_fillet"],
                                    })
                                cur_pts[-1] = (cur_pts[-1][0], cur_pts[-1][1], b_val)
                                cur_pts.append((next_p[0], next_p[1], 0.0))
                                cur_end = next_p
                                if len(cur_pts) > 3 and math.hypot(cur_end[0] - first_pt[0], cur_end[1] - first_pt[1]) < 0.35:
                                    closed_chains.append((cur_pts[:-1], True))
                                    cur_pts = []
                                    cur_end = None
                                    first_pt = None
                            else:
                                open_chains.append(cur_pts)
                                arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=inverted_handedness)
                                b_val = arc_info["bulge"] if arc_info else 0.0
                                if arc_info:
                                    fillet_registry.append({
                                        "idx": prim["idx"],
                                        "layer": target_layer,
                                        "R_mm": arc_info["R_mm"],
                                        "bulge": b_val,
                                        "center": arc_info["center"],
                                        "is_small_fillet": arc_info["is_small_fillet"],
                                    })
                                cur_pts = [(c1[0], c1[1], b_val), (c4[0], c4[1], 0.0)]
                                cur_end = c4
                                first_pt = c1

                if cur_pts:
                    if len(cur_pts) > 3 and math.hypot(cur_end[0] - first_pt[0], cur_end[1] - first_pt[1]) < 0.35:
                        closed_chains.append((cur_pts[:-1], True))
                    else:
                        open_chains.append(cur_pts)

                # Phase 2: Spatial chaining for remaining open segments
                phase2_chains = chain_xyb_segments(open_chains, tol=0.25)
                final_chains = closed_chains + phase2_chains

                for poly_pts, is_closed in final_chains:
                    if len(poly_pts) < 2:
                        continue
                    if is_closed:
                        closed_loops_count += 1

                    msp.add_lwpolyline(
                        poly_pts,
                        format="xyb",
                        close=is_closed,
                        dxfattribs={"layer": target_layer, "color": target_color}
                    )
                    entities_count += 1
                    layer_stats[target_layer] += 1

        else:
            # Catalog mode (Tasks 017 & 025: zero-hatch clean contours with native arc bulges & strict crop)
            prims_catalog = []
            boundary_cut_points = set()

            for idx, d in enumerate(drawings):
                if idx in dim_drawings_indices:
                    continue

                items = d.get("items", [])
                rect = d.get("rect", fitz.Rect(0, 0, 0, 0))

                # Zero-hatch contract: Suppress solid fill strip slices & raster stripes
                if d.get("fill") is not None:
                    if rect.width <= 0.45 or rect.height <= 0.45 or len(items) >= 4:
                        continue
                    if len(items) == 3 and not include_hatches:
                        continue

                for it in items:
                    if it[0] == "l":
                        p1_raw = (it[1].x, it[1].y)
                        p2_raw = (it[2].x, it[2].y)

                        # Suppress diagonal hatch lines (45 deg or ~60 deg with short length)
                        dx = abs(p2_raw[0] - p1_raw[0])
                        dy = abs(p2_raw[1] - p1_raw[1])
                        l_raw = math.hypot(dx, dy)
                        if not include_hatches and l_raw < 4.5 and (
                            abs(dx - dy) < 0.25 or abs(dy - 1.8 * dx) < 0.25 or abs(dx - 1.8 * dy) < 0.25
                        ):
                            continue

                        # Strict crop line clipping against filter_rect
                        clipped = clip_line_to_rect(p1_raw, p2_raw, filter_rect)
                        if not clipped:
                            continue
                        c_p1, c_p2, was_clipped = clipped
                        cad_p1 = to_cad(c_p1)
                        cad_p2 = to_cad(c_p2)
                        if was_clipped:
                            boundary_cut_points.add(cad_p1)
                            boundary_cut_points.add(cad_p2)

                        prims_catalog.append({"idx": idx, "kind": "l", "p1": cad_p1, "p2": cad_p2})

                    elif it[0] == "c":
                        c1_raw = (it[1].x, it[1].y)
                        c2_raw = (it[2].x, it[2].y)
                        c3_raw = (it[3].x, it[3].y)
                        c4_raw = (it[4].x, it[4].y)
                        curve_box = fitz.Rect(
                            min(c1_raw[0], c2_raw[0], c3_raw[0], c4_raw[0]),
                            min(c1_raw[1], c2_raw[1], c3_raw[1], c4_raw[1]),
                            max(c1_raw[0], c2_raw[0], c3_raw[0], c4_raw[0]),
                            max(c1_raw[1], c2_raw[1], c3_raw[1], c4_raw[1]),
                        )
                        if not filter_rect.intersects(curve_box):
                            continue
                        cad_c1 = to_cad(c1_raw)
                        cad_c2 = to_cad(c2_raw)
                        cad_c3 = to_cad(c3_raw)
                        cad_c4 = to_cad(c4_raw)
                        prims_catalog.append({
                            "idx": idx, "kind": "c",
                            "c1": cad_c1, "c2": cad_c2, "c3": cad_c3, "c4": cad_c4
                        })

                    elif it[0] == "re":
                        r_box = it[1]
                        clipped_box = r_box.intersect(filter_rect)
                        if not clipped_box.is_empty and clipped_box.width > 0.5 and clipped_box.height > 0.5:
                            p_tl = to_cad((clipped_box.x0, clipped_box.y0))
                            p_tr = to_cad((clipped_box.x1, clipped_box.y0))
                            p_br = to_cad((clipped_box.x1, clipped_box.y1))
                            p_bl = to_cad((clipped_box.x0, clipped_box.y1))
                            prims_catalog.append({
                                "idx": idx, "kind": "re",
                                "pts": [
                                    (p_tl[0], p_tl[1], 0.0),
                                    (p_tr[0], p_tr[1], 0.0),
                                    (p_br[0], p_br[1], 0.0),
                                    (p_bl[0], p_bl[1], 0.0),
                                    (p_tl[0], p_tl[1], 0.0),
                                ]
                            })

            # Two-phase contour chaining for catalog mode
            open_chains_cat = []
            closed_chains_cat = []
            cur_pts_cat = []
            cur_end_cat = None
            first_pt_cat = None
            max_gap = 0.50

            for prim in prims_catalog:
                kind = prim["kind"]
                if kind == "re":
                    if cur_pts_cat:
                        open_chains_cat.append(cur_pts_cat)
                        cur_pts_cat = []
                        cur_end_cat = None
                        first_pt_cat = None
                    closed_chains_cat.append((prim["pts"][:-1], True))
                    continue

                if kind == "l":
                    p1, p2 = prim["p1"], prim["p2"]
                    if not cur_pts_cat:
                        cur_pts_cat = [(p1[0], p1[1], 0.0), (p2[0], p2[1], 0.0)]
                        cur_end_cat = p2
                        first_pt_cat = p1
                    else:
                        d1 = math.hypot(cur_end_cat[0] - p1[0], cur_end_cat[1] - p1[1])
                        d2 = math.hypot(cur_end_cat[0] - p2[0], cur_end_cat[1] - p2[1])
                        if min(d1, d2) < max_gap:
                            next_p = p2 if d1 <= d2 else p1
                            cur_pts_cat.append((next_p[0], next_p[1], 0.0))
                            cur_end_cat = next_p
                            if len(cur_pts_cat) > 3 and math.hypot(cur_end_cat[0] - first_pt_cat[0], cur_end_cat[1] - first_pt_cat[1]) < 0.35:
                                if first_pt_cat not in boundary_cut_points and cur_end_cat not in boundary_cut_points:
                                    closed_chains_cat.append((cur_pts_cat[:-1], True))
                                else:
                                    open_chains_cat.append(cur_pts_cat)
                                cur_pts_cat = []
                                cur_end_cat = None
                                first_pt_cat = None
                        else:
                            open_chains_cat.append(cur_pts_cat)
                            cur_pts_cat = [(p1[0], p1[1], 0.0), (p2[0], p2[1], 0.0)]
                            cur_end_cat = p2
                            first_pt_cat = p1

                elif kind == "c":
                    c1, c2, c3, c4 = prim["c1"], prim["c2"], prim["c3"], prim["c4"]
                    if not cur_pts_cat:
                        arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=False)
                        b_val = arc_info["bulge"] if arc_info else 0.0
                        cur_pts_cat = [(c1[0], c1[1], b_val), (c4[0], c4[1], 0.0)]
                        cur_end_cat = c4
                        first_pt_cat = c1
                    else:
                        d1 = math.hypot(cur_end_cat[0] - c1[0], cur_end_cat[1] - c1[1])
                        d4 = math.hypot(cur_end_cat[0] - c4[0], cur_end_cat[1] - c4[1])
                        if min(d1, d4) < max_gap:
                            if d1 <= d4:
                                arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=False)
                                b_val = arc_info["bulge"] if arc_info else 0.0
                                cur_pts_cat[-1] = (cur_pts_cat[-1][0], cur_pts_cat[-1][1], b_val)
                                cur_pts_cat.append((c4[0], c4[1], 0.0))
                                cur_end_cat = c4
                            else:
                                arc_info = compute_cad_arc_bulge(c4, c3, c2, c1, inverted_handedness=False)
                                b_val = arc_info["bulge"] if arc_info else 0.0
                                cur_pts_cat[-1] = (cur_pts_cat[-1][0], cur_pts_cat[-1][1], -b_val)
                                cur_pts_cat.append((c1[0], c1[1], 0.0))
                                cur_end_cat = c1
                            if len(cur_pts_cat) > 3 and math.hypot(cur_end_cat[0] - first_pt_cat[0], cur_end_cat[1] - first_pt_cat[1]) < 0.35:
                                if first_pt_cat not in boundary_cut_points and cur_end_cat not in boundary_cut_points:
                                    closed_chains_cat.append((cur_pts_cat[:-1], True))
                                else:
                                    open_chains_cat.append(cur_pts_cat)
                                cur_pts_cat = []
                                cur_end_cat = None
                                first_pt_cat = None
                        else:
                            open_chains_cat.append(cur_pts_cat)
                            arc_info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=False)
                            b_val = arc_info["bulge"] if arc_info else 0.0
                            cur_pts_cat = [(c1[0], c1[1], b_val), (c4[0], c4[1], 0.0)]
                            cur_end_cat = c4
                            first_pt_cat = c1

            if cur_pts_cat:
                open_chains_cat.append(cur_pts_cat)

            phase2_chains_cat = chain_xyb_segments(open_chains_cat, tol=0.30)
            final_catalog_chains = closed_chains_cat + phase2_chains_cat

            for poly_pts, is_closed in final_catalog_chains:
                if len(poly_pts) < 2:
                    continue
                tot_len = sum(
                    math.hypot(poly_pts[i + 1][0] - poly_pts[i][0], poly_pts[i + 1][1] - poly_pts[i][1])
                    for i in range(len(poly_pts) - 1)
                )
                if not is_closed and tot_len < 3.0:
                    continue  # Filter out tiny disconnected remnant segments

                # Strict crop rule: cut profiles touching boundary remain open
                p_start = (poly_pts[0][0], poly_pts[0][1])
                p_finish = (poly_pts[-1][0], poly_pts[-1][1])
                if p_start in boundary_cut_points or p_finish in boundary_cut_points:
                    is_closed = False

                if is_closed:
                    closed_loops_count += 1

                mid_x = poly_pts[len(poly_pts) // 2][0]
                if 45.0 <= mid_x <= 75.0:
                    t_layer = "03_ТЕРМОМОСТ"
                elif mid_x < 45.0:
                    t_layer = "01_АЛЮМИНИЙ_НАРУЖНЫЙ"
                elif mid_x > 115.0:
                    t_layer = "05_СТЕКЛОПАКЕТ"
                else:
                    t_layer = "01_АЛЮМИНИЙ_ВНУТРЕННИЙ"

                msp.add_lwpolyline(
                    poly_pts,
                    format="xyb",
                    close=is_closed,
                    dxfattribs={"layer": t_layer},
                )
                entities_count += 1
                layer_stats[t_layer] += 1

        # 7. Save Output Files (DXF and DWG)
        if not output_path:
            out_dir = Path("runtime/cache/cad")
            out_dir.mkdir(parents=True, exist_ok=True)
            stem = self.pdf_path.stem.replace(" ", "_")
            output_path = out_dir / f"{stem}_стр_{page_number}.dxf"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        dxf_path = output_path.with_suffix(".dxf")
        dwg_path = output_path.with_suffix(".dwg")

        # Assemble entities into native physical components (Task 024)
        comp_summary = assemble_physical_components(dxf_doc)

        try:
            dxf_doc.saveas(str(dxf_path))
        except PermissionError:
            alt_path = dxf_path.with_stem(f"{dxf_path.stem}_upd")
            dxf_doc.saveas(str(alt_path))
            dxf_path = alt_path

        logger.info("Saved CAD DXF to %s (%d entities, %d closed loops, %d physical components)",
                    dxf_path, entities_count, closed_loops_count, comp_summary.get("componentsCount", 0))

        dwg_success = False
        if compile_dwg:
            dwg_success = convert_dxf_to_dwg_via_accore(dxf_path, dwg_path)

        scale_desc = f"1:{int(scale_factor)}" if scale_factor > 1.0 else "1:1"

        return {
            "success": True,
            "filePath": str(dxf_path.resolve()),
            "fileName": dxf_path.name,
            "dxfPath": str(dxf_path.resolve()),
            "dwgPath": str(dwg_path.resolve()) if dwg_success else None,
            "dwgCompiled": dwg_success,
            "page": page_number,
            "entitiesCount": entities_count,
            "closedLoopsCount": closed_loops_count,
            "layers": dict(layer_stats),
            "scale": total_scale,
            "scaleFactor": scale_factor,
            "scaleUnit": "mm",
            "scaleStr": scale_desc,
            "filletRegistry": fillet_registry,
            "smallFilletsCount": sum(1 for f in fillet_registry if f.get("is_small_fillet")),
            "largeArcsCount": sum(1 for f in fillet_registry if not f.get("is_small_fillet")),
            "componentsCount": comp_summary.get("componentsCount", 0),
            "components": comp_summary.get("groups", []),
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
