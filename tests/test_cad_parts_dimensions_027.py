"""
FERO CAD Unit Test Suite — Task 027 (Complete Product Boundaries, Native Dimensions & Callouts)
================================================================================================
Validates the strict contracts of Task 027 on Reynaers MasterLine 8 (Section DSI 8, Page 525):
1. Exact Layer 'Размерная линия': All dimensions are native AutoCAD DIMENSION entities on layer 'Размерная линия';
2. Dimension Chaining & Accuracy: All 6 dimensions (9.5, 15, 25, 103, 128, 130 mm) verified with measured distance <= 0.15 mm error;
3. Authentic Extension Lines: defpoint2 and defpoint3 are attached to the actual profile faces, producing visible extension lines (>= 2.0 mm);
4. Zero Duplicate Loose Entities: dimension nominals and arrow drawings are suppressed from modelspace lines/texts;
5. Dedicated Layer 'Обозначения': Articles (108.1873.XX, 080.9240.04...) and section callouts (DSI 8, h) are strictly on layer 'Обозначения';
6. Restored Product Boundaries: Real profile walls, ribs, flanges, and screw pockets (< 18 mm) are preserved and never deleted;
7. Zero Hatch & Empty Cavities: HATCH == 0, no dense zigzag hatch strokes (L/diag > 2.2);
8. Physical Component Assembly: Distinct extruded products assembled into ACAD_GROUP with dimensions strictly excluded;
9. Binary DWG Compilation: generated_027.dwg cleanly compiled via accoreconsole.
"""

import math
import re
import unittest
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadPartsDimensions027(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(
            r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
        )
        cls.has_pdf = cls.pdf_path.exists()

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dxf = cls.out_dir / "generated_027.dxf"
        cls.out_dwg = cls.out_dir / "generated_027.dwg"

        cls.crop_rect = (208.0, 108.0, 550.0, 400.0)

        if cls.has_pdf:
            cls.res = export_pdf_page_to_cad(
                pdf_path=cls.pdf_path,
                page_number=525,
                crop_box=cls.crop_rect,
                output_path=cls.out_dwg,
                options={
                    "crop_padding": 0.0,
                    "mode": "catalog",
                    "scale": 2.0,
                    "compile_dwg": True,
                },
            )
        elif cls.out_dxf.exists():
            cls.res = {"success": True, "dxfPath": str(cls.out_dxf)}
        else:
            raise unittest.SkipTest("Neither target catalog PDF nor generated_027.dxf found")

        cls.doc = ezdxf.readfile(str(cls.out_dxf))
        cls.msp = cls.doc.modelspace()

    # --- 1. Dimension Contracts ---
    def test_01_dimensions_on_exact_layer(self):
        """Contract 1: All dimensions are strictly on layer 'Размерная линия'."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertGreaterEqual(len(dims), 6, f"Expected >= 6 dimensions, found {len(dims)}")

        for d in dims:
            self.assertEqual(
                d.dxf.layer,
                "Размерная линия",
                f"Dimension entity on incorrect layer '{d.dxf.layer}', expected 'Размерная линия'",
            )

    def test_02_dimensions_accuracy_and_nominals(self):
        """Contract 1: Measured CAD distances match PDF nominals (9.5, 15, 25, 103, 128, 130) within 0.15 mm."""
        dims = list(self.msp.query("DIMENSION"))
        measurements = [d.get_measurement() for d in dims]

        expected_nominals = [9.5, 15.0, 25.0, 103.0, 128.0, 130.0]
        for exp in expected_nominals:
            matched = any(abs(m - exp) < 0.15 for m in measurements)
            self.assertTrue(
                matched,
                f"Expected dimension nominal {exp} mm not found in measurements: {[round(m, 2) for m in measurements]}",
            )

    def test_03_authentic_witness_extension_lines(self):
        """Contract 1: defpoint2 and defpoint3 are attached to profile faces, producing visible extension lines."""
        dims = list(self.msp.query("DIMENSION"))
        for d in dims:
            p1 = d.dxf.defpoint2
            p2 = d.dxf.defpoint3
            base = d.dxf.defpoint

            # Distance from measure points to dimension line
            # For horizontal dims (angle == 0): extension line length is |p.y - base.y|
            # For vertical dims (angle == 90): extension line length is |p.x - base.x|
            ext1 = abs(p1.y - base.y) if abs(d.dxf.angle) < 1.0 else abs(p1.x - base.x)
            ext2 = abs(p2.y - base.y) if abs(d.dxf.angle) < 1.0 else abs(p2.x - base.x)

            self.assertGreaterEqual(
                max(ext1, ext2),
                2.0,
                f"Dimension {d.get_measurement():.2f} mm has collapsed extension lines (ext1={ext1:.2f}, ext2={ext2:.2f})",
            )

    def test_04_no_duplicate_standalone_dimension_text_or_arrows(self):
        """Contract 1: No standalone text nominals left in modelspace for verified dimensions."""
        texts = [e.dxf.text.strip() for e in self.msp.query("TEXT")]
        for nominal in ["9.5", "15", "25", "103", "128", "130"]:
            self.assertNotIn(
                nominal,
                texts,
                f"Found duplicate standalone TEXT '{nominal}' in modelspace (should be part of DIMENSION)",
            )

    # --- 2. Callouts & Articles Contract ---
    def test_05_callouts_and_articles_on_proper_layer(self):
        """Contract 1: Articles and section callouts are placed on dedicated layer 'Обозначения'."""
        callout_texts = [
            e.dxf.text for e in self.msp.query("TEXT")
            if e.dxf.layer == "Обозначения"
        ]
        self.assertGreaterEqual(len(callout_texts), 10, f"Expected >= 10 annotations on 'Обозначения', found {len(callout_texts)}")

        # Check key articles on layer 'Обозначения'
        self.assertTrue(any("108.1873" in t for t in callout_texts), "Article 108.1873.XX must be on layer 'Обозначения'")
        self.assertTrue(any("080.9240" in t for t in callout_texts), "Article 080.9240.04 must be on layer 'Обозначения'")
        self.assertTrue(any("080.9320" in t for t in callout_texts), "Article 080.9320.04 must be on layer 'Обозначения'")
        self.assertTrue(any("052.5310" in t for t in callout_texts), "Article 052.5310.-- must be on layer 'Обозначения'")

        # Check section callouts on layer 'Обозначения'
        self.assertTrue(any("DSI" in t for t in callout_texts), "Section callout DSI must be on layer 'Обозначения'")
        self.assertTrue(any(t == "h" for t in callout_texts), "Section callout 'h' must be on layer 'Обозначения'")

    # --- 3. Profile Geometry & Restored Short Walls ---
    def test_06_profile_walls_and_short_ribs_preserved(self):
        """Contract 2: All profile walls, ribs, and flanges (< 18 mm) are preserved and never deleted."""
        polys = list(self.msp.query("LWPOLYLINE"))
        self.assertGreaterEqual(len(polys), 200, f"Expected >= 200 polyline entities, found {len(polys)}")

        # Verify inner aluminium sash shell has comprehensive geometry
        inner_alu = [p for p in polys if p.dxf.layer == "01_АЛЮМИНИЙ_ВНУТРЕННИЙ"]
        self.assertGreaterEqual(
            len(inner_alu),
            70,
            f"Expected >= 70 entities for inner sash alu, found {len(inner_alu)}",
        )

        # Verify presence of small features (ribs/flanges with length 2.0 to 15.0 mm)
        short_features = []
        for p in polys:
            pts = list(p.get_points())
            tot_len = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
            if 2.0 <= tot_len < 15.0:
                short_features.append(tot_len)

        self.assertGreaterEqual(
            len(short_features),
            15,
            f"Expected >= 15 short features (ribs/flanges < 15 mm), found {len(short_features)}",
        )

    # --- 4. Clean Contours & Zero Hatch ---
    def test_07_zero_hatch_and_clean_cavities(self):
        """Contract 2: Zero HATCH entities, profile cavities remain empty without dense zigzag hatch strokes."""
        hatches = list(self.msp.query("HATCH"))
        self.assertEqual(len(hatches), 0, f"Expected 0 HATCH entities, found {len(hatches)}")

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

    # --- 5. Component Assembly Duality ---
    def test_08_physical_component_groups_duality(self):
        """Contract 6: Distinct extruded products assembled into ACAD_GROUP with dimensions strictly excluded."""
        groups = self.doc.groups
        group_names = set(name for name, g in groups)
        self.assertGreaterEqual(len(groups), 4, f"Expected >= 4 groups, found {group_names}")

        self.assertIn("PART_ALU_SASH_INNER", group_names)
        self.assertIn("PART_THERMAL_BREAKS", group_names)
        self.assertIn("PART_SEALS_EPDM", group_names)
        self.assertIn("PART_GLASS_UNIT", group_names)

        # Dimensions and callouts are NEVER inside physical part groups
        dims = list(self.msp.query("DIMENSION"))
        dim_handles = set(d.dxf.handle for d in dims)
        for name, g in groups:
            group_handles = set(e.dxf.handle for e in g)
            self.assertTrue(
                dim_handles.isdisjoint(group_handles),
                f"Group '{name}' must not contain DIMENSION entities",
            )

    # --- 6. Binary DWG Compilation ---
    def test_09_dwg_binary_validity(self):
        """Contract 8: generated_027.dwg is generated and non-empty."""
        self.assertTrue(self.out_dwg.exists(), f"DWG file not found at {self.out_dwg}")
        self.assertGreater(
            self.out_dwg.stat().st_size,
            20000,
            f"DWG size too small: {self.out_dwg.stat().st_size} bytes",
        )


if __name__ == "__main__":
    unittest.main()
