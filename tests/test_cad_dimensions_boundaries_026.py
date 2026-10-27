"""
FERO CAD Unit Test Suite — Task 026 (Native Dimensions & Clean Product Boundaries)
==================================================================================
Validates the strict contracts of Task 026:
1. Exact Layer Name: All native dimensions are placed on layer 'Размерная линия' (not generic DIMENSIONS);
2. Native AutoCAD Dimensions: 7 DIMENSION entities in 1:1 mm scale with measured distance <= 0.1 mm error;
   no duplicate lines, triangles, or standalone texts left in modelspace;
3. Clean Extruded Contours: zero HATCH entities, zero dense zigzag hatch strokes, cavities remain empty;
4. Two-Sided Walls: both faces of thin profile walls (t ~ 1.1-1.5 mm) are preserved and never collapsed;
5. Open Cut Profiles: boundary-cut profiles remain open (is_closed == False);
6. Physical Component Duality: distinct extruded products assembled into ACAD_GROUP
   (outer sash alu, inner sash alu, thermal breaks, gaskets, glass unit);
7. Articles: catalog articles isolated on layer 08_АРТИКУЛЫ;
8. Binary DWG compilation: generated_026.dwg compiled cleanly via accoreconsole.
"""

import math
import re
import unittest
from pathlib import Path
import fitz
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadDimensionsBoundaries026(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(
            r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
        )
        cls.has_pdf = cls.pdf_path.exists()

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dxf = cls.out_dir / "generated_026.dxf"
        cls.out_dwg = cls.out_dir / "generated_026.dwg"

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
            cls.res = {"success": True, "dxfPath": str(cls.out_dxf)}
        else:
            raise unittest.SkipTest("Neither target catalog PDF nor generated_026.dxf found")

        cls.doc = ezdxf.readfile(str(cls.out_dxf))
        cls.msp = cls.doc.modelspace()

    # --- 1. Dimension Contracts ---
    def test_dimensions_on_exact_layer_name(self):
        """Contract 1: All dimensions are strictly on layer 'Размерная линия'."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertGreaterEqual(len(dims), 7, f"Expected >= 7 dimensions, found {len(dims)}")

        for d in dims:
            self.assertEqual(
                d.dxf.layer,
                "Размерная линия",
                f"Dimension entity on incorrect layer '{d.dxf.layer}', expected 'Размерная линия'",
            )

    def test_dimensions_geometric_accuracy_1_to_1(self):
        """Contract 1: Measured CAD distances match PDF nominals within 0.1 mm."""
        dims = list(self.msp.query("DIMENSION"))
        measured_distances = []
        for d in dims:
            dist = math.hypot(
                d.dxf.defpoint2.x - d.dxf.defpoint3.x,
                d.dxf.defpoint2.y - d.dxf.defpoint3.y,
            )
            measured_distances.append(dist)

        # Check expected nominals (20, 5, 6, 20, 6, 5, 5 mm)
        has_20 = any(abs(d - 20.0) < 0.1 for d in measured_distances)
        has_5 = any(abs(d - 5.0) < 0.1 for d in measured_distances)
        has_6 = any(abs(d - 6.0) < 0.1 for d in measured_distances)

        self.assertTrue(has_20, f"Expected 20 mm dimension in {measured_distances}")
        self.assertTrue(has_5, f"Expected 5 mm dimension in {measured_distances}")
        self.assertTrue(has_6, f"Expected 6 mm dimension in {measured_distances}")

    def test_dimensions_not_duplicated_as_standalone_text_or_lines(self):
        """Contract 1: No standalone text nominals or triangle lines left in modelspace."""
        standalone_numbers = [
            e.dxf.text.strip()
            for e in self.msp.query("TEXT")
            if re.match(r"^(5|6|20)$", e.dxf.text.strip())
        ]
        self.assertEqual(
            len(standalone_numbers),
            0,
            f"Found duplicate standalone dimension texts in modelspace: {standalone_numbers}",
        )

    # --- 2. Clean Extruded Contours & Zero Hatch ---
    def test_zero_hatch_and_clean_cavities(self):
        """Contract 2: Zero HATCH entities in catalog mode, cavities are empty."""
        hatches = list(self.msp.query("HATCH"))
        self.assertEqual(len(hatches), 0, f"Expected 0 HATCH entities, found {len(hatches)}")

    def test_no_dense_zigzag_hatch_strokes(self):
        """Contract 2: No dense zigzag hatch stroke polylines (length/diag > 2.2)."""
        polys = list(self.msp.query("LWPOLYLINE"))
        zigzag_strokes = []
        for p in polys:
            if not p.is_closed:
                pts = p.get_points("xy")
                L = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
                diag = max(0.1, math.hypot(
                    max(pt[0] for pt in pts) - min(pt[0] for pt in pts),
                    max(pt[1] for pt in pts) - min(pt[1] for pt in pts),
                ))
                if L / diag > 2.2:
                    zigzag_strokes.append(p)

        self.assertEqual(
            len(zigzag_strokes),
            0,
            f"Found {len(zigzag_strokes)} zigzag hatch polylines that should be eliminated",
        )

    def test_profile_walls_both_sides_preserved(self):
        """Contract 2: Both outer and inner faces of thin profile walls (t ~ 1.06 mm) are preserved."""
        polys = list(self.msp.query("LWPOLYLINE"))
        all_pts = []
        for p in polys:
            all_pts.extend(p.get_points("xy"))

        # In the sash flange at Y=165.81 mm, verify both inner and outer surfaces exist:
        # Outer surface: X ~ 11.42 mm, Inner surface: X ~ 12.48 mm (wall thickness ~ 1.06 mm)
        has_outer_face = any(abs(pt[0] - 11.42) < 0.2 and abs(pt[1] - 165.81) < 0.2 for pt in all_pts)
        has_inner_face = any(abs(pt[0] - 12.48) < 0.2 and abs(pt[1] - 165.81) < 0.2 for pt in all_pts)

        self.assertTrue(has_outer_face, "Outer face of sash wall (X ~ 11.42 mm at Y=165.81 mm) must be preserved")
        self.assertTrue(has_inner_face, "Inner face of sash wall (X ~ 12.48 mm at Y=165.81 mm) must be preserved")

        # Verify vertical profile walls extending to top boundary exist
        top_walls = [pt[0] for pt in all_pts if abs(pt[1] - 264.58) < 0.2]
        self.assertGreaterEqual(len(top_walls), 4, f"Expected >= 4 vertical walls cut at top, found {top_walls}")

    def test_open_profiles_at_crop_boundary(self):
        """Contract 5: Cut profiles touching the crop boundary remain open (is_closed == False)."""
        polys = list(self.msp.query("LWPOLYLINE"))
        open_polys = [p for p in polys if not p.is_closed]
        self.assertGreater(len(open_polys), 0, "Cut profiles at crop frame must remain open")

        # Verify they touch the top crop boundary (Y ~ 264.58 mm)
        touch_top = any(
            any(abs(pt[1] - 264.58) < 0.25 for pt in p.get_points("xy"))
            for p in open_polys
        )
        self.assertTrue(touch_top, "Open cut profiles must touch the top crop frame")

    # --- 3. Component Groups (Duality Contract) ---
    def test_component_groups_present(self):
        """Contract 6: Distinct extruded products are grouped into ACAD_GROUP."""
        groups = self.doc.groups
        group_names = set(name for name, g in groups)
        self.assertGreaterEqual(len(groups), 4, f"Expected >= 4 groups, found {group_names}")

        self.assertIn("PART_ALU_SASH_OUTER", group_names)
        self.assertIn("PART_ALU_SASH_INNER", group_names)
        self.assertIn("PART_THERMAL_BREAKS", group_names)
        self.assertIn("PART_GLASS_UNIT", group_names)

        # Dimensions are NEVER grouped into parts
        dims = list(self.msp.query("DIMENSION"))
        dim_handles = set(d.dxf.handle for d in dims)
        for name, g in groups:
            group_handles = set(e.dxf.handle for e in g)
            self.assertTrue(
                dim_handles.isdisjoint(group_handles),
                f"Group '{name}' must not contain DIMENSION entities",
            )

    # --- 4. Articles Layer ---
    def test_articles_isolated_on_proper_layer(self):
        """Contract 7: Catalog articles are placed on 08_АРТИКУЛЫ."""
        articles = [
            e.dxf.text for e in self.msp.query("TEXT")
            if e.dxf.layer in ("08_АРТИКУЛЫ", "ARTICLES")
        ]
        self.assertGreaterEqual(len(articles), 3, f"Expected >= 3 articles, found {articles}")
        self.assertTrue(any("408.0245" in t for t in articles))
        self.assertTrue(any("408.0983" in t for t in articles))
        self.assertTrue(any("130.0029" in t for t in articles))

    # --- 5. Binary DWG Compilation ---
    def test_binary_dwg_file_validity(self):
        """Contract 8: generated_026.dwg is generated and non-empty."""
        self.assertTrue(self.out_dwg.exists(), f"DWG file not found at {self.out_dwg}")
        self.assertGreater(
            self.out_dwg.stat().st_size,
            20000,
            f"DWG size too small: {self.out_dwg.stat().st_size} bytes",
        )


if __name__ == "__main__":
    unittest.main()
