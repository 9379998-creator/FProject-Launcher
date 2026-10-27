"""
FERO CAD Unit Test Suite — Task 023 (Small Fillet Radius Rule & Verification)
=============================================================================
Validates the strict contracts of Task 023 and 022:
1. Characteristic small fillets (0.3–0.5 mm): verified against native PDF geometry;
2. Circularity validation: cubic Bezier curves must have radial error < 0.05 mm;
3. Anti-clamping policy: large arcs (R > 1.0 mm, glass seals) are NOT forced to 0.3/0.5 mm;
4. Tangent continuity (C1): corner fillets seamlessly transition orthogonal lines (|b| ~ 0.4142);
5. Clean dimensions & preserved accessories: zero duplicate polylines over dimensions,
   clean yellow rubber gasket (04_КОМПЛЕКТУЮЩИЕ) and TrueType Cyrillic text;
6. Binary DWG compilation: produces uzel_po_nizu_okna_generated_023.dwg via accoreconsole.
"""

import math
import unittest
from pathlib import Path

import ezdxf

from app.cad.pdf_cad_extractor import (
    export_pdf_page_to_cad,
    compute_cad_arc_bulge,
    reverse_xyb,
)


class TestCadFilletValidation023(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_023.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_023.dxf"

        # Execute extraction with Task 023 circularity validation and fillet registry
        cls.res = export_pdf_page_to_cad(
            pdf_path=cls.pdf_path,
            page_number=1,
            output_path=cls.out_dwg,
            options={
                "mode": "reference",
                "include_hatches": True,
                "compile_dwg": True,
            },
        )

        cls.doc = ezdxf.readfile(str(cls.out_dxf))
        cls.msp = cls.doc.modelspace()

    def test_fillet_registry_and_small_radii_range(self):
        """Contract 1: Fillet registry identifies small fillets in the ~0.3-0.5 mm diagnostic range."""
        registry = self.res.get("filletRegistry", [])
        self.assertGreater(len(registry), 500, f"Expected >500 fillets in registry, found {len(registry)}")

        small_fillets = [f for f in registry if f.get("is_small_fillet")]
        self.assertGreater(
            len(small_fillets),
            300,
            f"Expected >300 small fillets in 0.20-0.60 mm range, found {len(small_fillets)}",
        )

        # Check modal radius: characteristic profile corner radius is around 0.37 mm
        radii = [f["R_mm"] for f in small_fillets]
        median_r = sorted(radii)[len(radii) // 2]
        self.assertAlmostEqual(
            median_r,
            0.37,
            delta=0.08,
            msg=f"Median small fillet radius ({median_r:.3f} mm) must be close to ~0.3-0.5 mm guideline",
        )

    def test_anti_clamping_policy_preserves_large_arcs(self):
        """Contract 2: Large arcs (R > 1.0 mm, glass seals, frame radii) must NOT be clamped to 0.3-0.5 mm."""
        registry = self.res.get("filletRegistry", [])
        large_arcs = [f for f in registry if not f.get("is_small_fillet") and f.get("R_mm", 0.0) > 1.0]

        self.assertGreater(
            len(large_arcs),
            50,
            f"Expected >50 large arcs (R > 1.0 mm) preserved without clamping, found {len(large_arcs)}",
        )

        # Confirm existence of large glass seals / menisci (R > 8.0 mm)
        huge_arcs = [f for f in large_arcs if f["R_mm"] > 8.0]
        self.assertGreater(
            len(huge_arcs),
            10,
            f"Expected >10 large arcs with R > 8.0 mm (glass seal / contours), found {len(huge_arcs)}",
        )

    def test_circularity_validation_accuracy(self):
        """Contract 3: Evaluates radial distance error across curve to ensure true circular geometry."""
        # Quarter circle test
        c1 = (0.0, 1.0)
        c2 = (0.0, 0.4477)
        c3 = (0.4477, 0.0)
        c4 = (1.0, 0.0)
        info = compute_cad_arc_bulge(c1, c2, c3, c4, inverted_handedness=False)

        self.assertIsNotNone(info)
        self.assertAlmostEqual(info["R_mm"], 1.0, places=2)
        self.assertAlmostEqual(info["center"][0], 1.0, places=2)
        self.assertAlmostEqual(info["center"][1], 1.0, places=2)
        self.assertLess(info["circularity_error_mm"], 0.01)

        # Distorted non-circular curve test must be rejected
        c2_distorted = (0.8, 1.2)
        c3_distorted = (0.2, -0.4)
        info_distorted = compute_cad_arc_bulge(c1, c2_distorted, c3_distorted, c4, max_circularity_error=0.05)
        self.assertIsNone(info_distorted, "Distorted non-circular curve must be rejected by circularity check")

    def test_tangent_continuity_and_bulge_signs(self):
        """Contract 4: 90-degree corner fillets must exhibit seamless tangent continuity (|b| ~ 0.4142)."""
        pos_fillets = 0
        neg_fillets = 0

        for p in self.msp.query("LWPOLYLINE"):
            pts = p.get_points(format="xyb")
            for pt in pts:
                b = pt[2]
                if abs(abs(b) - 0.4142) < 0.005:
                    if b > 0:
                        pos_fillets += 1
                    else:
                        neg_fillets += 1

        self.assertGreater(pos_fillets, 50, f"Expected >50 CCW fillets, found {pos_fillets}")
        self.assertGreater(neg_fillets, 50, f"Expected >50 CW fillets, found {neg_fillets}")

    def test_yellow_gasket_and_insulation_preserved(self):
        """Contract 5: Approved yellow rubber gasket and insulation hatch must remain intact."""
        gasket_polys = [p for p in self.msp.query("LWPOLYLINE") if p.dxf.layer == "04_КОМПЛЕКТУЮЩИЕ"]
        self.assertGreaterEqual(len(gasket_polys), 100, f"Yellow gasket polylines missing, found {len(gasket_polys)}")

        foam_hatch = [p for p in self.msp.query("LWPOLYLINE") if p.dxf.layer == "06_ШТРИХОВКА_УТЕПЛИТЕЛЬ"]
        self.assertGreater(len(foam_hatch), 500, f"Foam hatch lines missing, found {len(foam_hatch)}")

    def test_clean_dimensions_zero_overlap(self):
        """Contract 6: Dimensions must remain clean native DIMENSION entities with zero overlapping polylines."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertEqual(len(dims), 3, f"Expected exactly 3 native DIMENSION entities, found {len(dims)}")

        dim_boxes = [
            (335.0, 325.0, 345.0, 410.0),
            (335.0, 405.0, 345.0, 412.0),
            (350.0, 435.0, 445.0, 445.0),
        ]
        duplicates = []
        for p in self.msp.query("LWPOLYLINE"):
            pts = p.get_points()
            for b in dim_boxes:
                if all(b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3] for pt in pts):
                    duplicates.append((p.dxf.layer, pts))

        self.assertEqual(len(duplicates), 0, f"Duplicate polylines over dimensions found: {duplicates}")

    def test_dwg_binary_output_valid(self):
        """Contract 7: Binary DWG must be successfully generated and compiled via local AutoCAD engine."""
        self.assertTrue(self.out_dwg.exists(), f"DWG file does not exist: {self.out_dwg}")
        self.assertGreater(self.out_dwg.stat().st_size, 50000, "DWG file too small")
        self.assertTrue(self.res["dwgCompiled"], "DWG compilation failed")


if __name__ == "__main__":
    unittest.main()
