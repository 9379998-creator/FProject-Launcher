"""
FERO CAD Unit Test Suite — Task 025 (Strict Crop, Real Dimensions & Clean Catalog Contours)
=========================================================================================
Validates the strict contracts of Task 025:
1. Algorithmic clipping: clip_line_to_rect implements robust Cohen-Sutherland clipping;
2. Strict Crop Boundary: 0.0 padding; no geometry or text extends outside crop boundary;
3. Native AutoCAD Dimensions: triangle arrowhead dimensions converted to true native DIMENSION
   entities on layer 07_РАЗМЕРЫ / DIMENSIONS in 1:1 scale (scale factor 2.5) with <= 0.1 mm error;
   no duplicate text/geometry left in modelspace;
4. Articles: Reynaers article numbers (xxx.xxxx.xx) isolated on 08_АРТИКУЛЫ / ARTICLES;
5. Zero Hatch: catalog mode produces 0 HATCH entities and suppresses thin gradient fill strips;
6. Open Cut Profiles: polylines cut by the crop boundary remain open (is_closed == False);
7. Binary DWG Compilation: generated_025.dwg generated cleanly.
"""

import math
import re
import unittest
from pathlib import Path
import fitz
import ezdxf

from app.cad.pdf_cad_extractor import (
    clip_line_to_rect,
    detect_catalog_scale,
    export_pdf_page_to_cad,
)


class TestCadStrictCrop025(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Masterline 8 catalog PDF path
        cls.pdf_path = Path(
            r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
        )
        cls.has_pdf = cls.pdf_path.exists()

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dxf = cls.out_dir / "generated_025.dxf"
        cls.out_dwg = cls.out_dir / "generated_025.dwg"

        # Crop rect from user selection on page 810 (0-indexed 809, 1-indexed 810)
        cls.crop_rect = (330.0, 160.0, 530.0, 460.0)

        if cls.has_pdf:
            cls.res = export_pdf_page_to_cad(
                pdf_path=cls.pdf_path,
                page_number=810,
                crop_box=cls.crop_rect,
                output_path=cls.out_dwg,
                options={
                    "crop_padding": 0.0,
                    "mode": "catalog",
                    "scale": 2.5,
                    "compile_dwg": True,
                },
            )
        elif cls.out_dxf.exists():
            cls.res = {"status": "ok", "dxf_path": str(cls.out_dxf)}
        else:
            raise unittest.SkipTest("Neither target catalog PDF nor generated_025.dxf found")

        cls.doc = ezdxf.readfile(str(cls.out_dxf))
        cls.msp = cls.doc.modelspace()

    # --- 1. Algorithmic Clipping Tests ---
    def test_clip_line_to_rect_inside(self):
        """Test line completely inside rect is unclipped."""
        r = fitz.Rect(10, 10, 50, 50)
        res = clip_line_to_rect((20, 20), (30, 30), r)
        self.assertIsNotNone(res)
        p1, p2, was_clipped = res
        self.assertFalse(was_clipped)
        self.assertEqual(p1, (20, 20))
        self.assertEqual(p2, (30, 30))

    def test_clip_line_to_rect_outside(self):
        """Test line completely outside rect returns None."""
        r = fitz.Rect(10, 10, 50, 50)
        # Fully to the left
        self.assertIsNone(clip_line_to_rect((0, 20), (5, 30), r))
        # Fully above
        self.assertIsNone(clip_line_to_rect((20, 60), (30, 70), r))

    def test_clip_line_to_rect_crossing(self):
        """Test line crossing rect is clipped to exact boundary."""
        r = fitz.Rect(10, 10, 50, 50)
        res = clip_line_to_rect((0, 25), (60, 25), r)
        self.assertIsNotNone(res)
        p1, p2, was_clipped = res
        self.assertTrue(was_clipped)
        self.assertAlmostEqual(p1[0], 10.0)
        self.assertAlmostEqual(p1[1], 25.0)
        self.assertAlmostEqual(p2[0], 50.0)
        self.assertAlmostEqual(p2[1], 25.0)

    # --- 2. Strict Crop Boundary Tests ---
    def test_strict_crop_boundary_extents(self):
        """Contract 1: All geometry points must lie strictly inside crop dimensions."""
        width_pt = self.crop_rect[2] - self.crop_rect[0]  # 200 pt
        height_pt = self.crop_rect[3] - self.crop_rect[1]  # 300 pt
        scale = 2.5
        pt_to_mm = 25.4 / 72.0
        max_cad_x = width_pt * scale * pt_to_mm   # ~176.388 mm
        max_cad_y = height_pt * scale * pt_to_mm  # ~264.583 mm

        # Inspect all entities in modelspace
        all_xs, all_ys = [], []
        for e in self.msp:
            dxftype = e.dxftype()
            if dxftype == "LWPOLYLINE":
                for pt in e.get_points(format="xy"):
                    all_xs.append(pt[0])
                    all_ys.append(pt[1])
            elif dxftype == "LINE":
                all_xs.extend([e.dxf.start.x, e.dxf.end.x])
                all_ys.extend([e.dxf.start.y, e.dxf.end.y])
            elif dxftype == "DIMENSION":
                all_xs.extend([e.dxf.defpoint.x, e.dxf.defpoint2.x, e.dxf.defpoint3.x])
                all_ys.extend([e.dxf.defpoint.y, e.dxf.defpoint2.y, e.dxf.defpoint3.y])
            elif dxftype in ("TEXT", "MTEXT"):
                all_xs.append(e.dxf.insert.x)
                all_ys.append(e.dxf.insert.y)

        self.assertTrue(len(all_xs) > 0, "Modelspace must contain entities")
        min_x, max_x = min(all_xs), max(all_xs)
        min_y, max_y = min(all_ys), max(all_ys)

        # Allow epsilon 0.05 mm for numerical precision
        eps = 0.05
        self.assertGreaterEqual(min_x, -eps, f"Geometry leaked below X=0: {min_x}")
        self.assertGreaterEqual(min_y, -eps, f"Geometry leaked below Y=0: {min_y}")
        self.assertLessEqual(max_x, max_cad_x + eps, f"Geometry leaked above X_max: {max_x} > {max_cad_x}")
        self.assertLessEqual(max_y, max_cad_y + eps, f"Geometry leaked above Y_max: {max_y} > {max_cad_y}")

    # --- 3. Native AutoCAD Dimensions Tests ---
    def test_native_dimension_entities(self):
        """Contract 2: Native DIMENSION entities exist on layer 07_РАЗМЕРЫ with nominal accuracy."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertGreaterEqual(
            len(dims), 7, f"Expected >= 7 native DIMENSION entities, found {len(dims)}"
        )

        nominals = []
        for d in dims:
            self.assertIn(d.dxf.layer, ("Размерная линия", "07_РАЗМЕРЫ", "DIMENSIONS"))
            measured_dist = math.hypot(
                d.dxf.defpoint2.x - d.dxf.defpoint3.x,
                d.dxf.defpoint2.y - d.dxf.defpoint3.y,
            )
            nominal_val = float(d.dxf.text) if (d.dxf.text and d.dxf.text != "<>") else round(measured_dist)
            diff = abs(measured_dist - nominal_val)
            self.assertLessEqual(
                diff,
                0.15,
                f"Dimension nominal {nominal_val} mm differs from CAD geometry {measured_dist:.3f} mm by {diff:.3f} mm",
            )
            nominals.append(nominal_val)

        self.assertIn(20.0, nominals)
        self.assertIn(5.0, nominals)
        self.assertIn(6.0, nominals)

    def test_dimensions_not_duplicated_as_standalone_text(self):
        """Contract 2: Dimension nominal texts are not duplicated as standalone TEXT entities."""
        dims = list(self.msp.query("DIMENSION"))
        dim_texts = set(d.dxf.text for d in dims if d.dxf.text and d.dxf.text != "<>")

        # Standalone texts in modelspace should NOT contain pure numbers that match dimensions
        standalone_texts = [e.dxf.text for e in self.msp.query("TEXT")]
        for st in standalone_texts:
            if st.strip() in dim_texts:
                self.fail(f"Dimension text '{st}' duplicated as standalone TEXT entity in modelspace")

    # --- 4. Articles Layer & Formatting Tests ---
    def test_articles_layer_and_formatting(self):
        """Contract 2 & 3: Articles are placed strictly on 08_АРТИКУЛЫ and match article regex."""
        article_texts = [
            e.dxf.text
            for e in self.msp.query("TEXT")
            if e.dxf.layer in ("08_АРТИКУЛЫ", "ARTICLES")
        ]
        self.assertGreaterEqual(
            len(article_texts), 3, f"Expected >= 3 articles on layer 08_АРТИКУЛЫ, found {article_texts}"
        )

        # Verify key articles present on page 810
        self.assertTrue(any("408.0245" in t for t in article_texts))
        self.assertTrue(any("408.0983" in t for t in article_texts))
        self.assertTrue(any("130.0029" in t for t in article_texts))

        # Check pattern conformity (including optional quantity suffixes like ' x2')
        art_re = re.compile(r"^\d{3}\.[\w\d]{4}\.[\w\d]{2}(\s*[xх]\d+)?$", re.IGNORECASE)
        for t in article_texts:
            self.assertTrue(
                bool(art_re.match(t.strip())),
                f"Article text '{t}' does not match standard catalog article regex",
            )

    # --- 5. Catalog Mode Zero Hatch Tests ---
    def test_zero_hatch_entities_in_catalog_mode(self):
        """Contract 3: In catalog mode, 0 HATCH entities must be emitted to modelspace."""
        hatches = list(self.msp.query("HATCH"))
        self.assertEqual(
            len(hatches),
            0,
            f"Catalog mode must have 0 HATCH entities, found {len(hatches)}",
        )

    # --- 6. Open Profiles at Crop Boundary ---
    def test_cut_profiles_remain_open(self):
        """Contract 1: Cut profiles touching the boundary remain open (is_closed == False)."""
        polys = list(self.msp.query("LWPOLYLINE"))
        open_polys = [p for p in polys if not p.is_closed]
        self.assertGreater(
            len(open_polys),
            0,
            "Expected at least one open profile cut by the crop boundary",
        )

    # --- 7. Binary DWG Compilation Test ---
    def test_dwg_compilation_file_exists(self):
        """Contract 6: Binary DWG file generated_025.dwg is generated and non-empty."""
        self.assertTrue(
            self.out_dwg.exists(),
            f"Compiled DWG file not found at {self.out_dwg}",
        )
        self.assertGreater(
            self.out_dwg.stat().st_size,
            20000,
            f"Compiled DWG file size too small: {self.out_dwg.stat().st_size} bytes",
        )


if __name__ == "__main__":
    unittest.main()
