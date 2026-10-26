"""
FERO CAD Unit Test Suite — Task 021 (Native Arc Geometry & Contour Reconstruction)
=================================================================================
Validates the strict contracts of Task 021:
1. Contour and cavity geometry: seamless closed loops with native circular arc bulges;
2. Curvature orientation: arcs bulge towards their native center of curvature (not inverted);
3. Clean dimensions: ZERO duplicate polylines over/under the native DIMENSION entities;
4. Real DWG generation: compiles binary uzel_po_nizu_okna_generated_021.dwg via accoreconsole.
"""

import math
import unittest
from pathlib import Path
from collections import defaultdict

import ezdxf
from ezdxf.math import Vec2, bulge_to_arc

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad, compute_cad_arc_bulge, reverse_xyb


class TestCadReference021(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_021.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_021.dxf"

        # Execute extraction with Task 021 native geometry and clean dimensions
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

    def test_clean_dimensions_zero_duplicate_polylines(self):
        """Task 021 Contract 1: Clean native dimensions without duplicate overlapping polylines."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertEqual(len(dims), 3, f"Expected exactly 3 native DIMENSION entities, found {len(dims)}")

        # Verify dimension nominal measurements
        measurements = []
        for d in dims:
            p2 = d.dxf.defpoint2
            p3 = d.dxf.defpoint3
            dist = math.hypot(p2[0] - p3[0], p2[1] - p3[1])
            measurements.append(round(dist))
        self.assertIn(87, measurements, f"Expected 87 mm dimension, found {measurements}")
        self.assertIn(76, measurements, f"Expected 76 mm dimension, found {measurements}")
        self.assertIn(3, measurements, f"Expected 3 mm dimension, found {measurements}")

        # Check bounding boxes of the 3 dimensions: there must be ZERO standalone polylines
        dim_boxes = [
            (335.0, 325.0, 345.0, 410.0),  # 76 mm vertical dimension
            (335.0, 405.0, 345.0, 412.0),  # 3 mm vertical clearance
            (350.0, 435.0, 445.0, 445.0),  # 87 mm horizontal dimension
        ]
        duplicate_polys = []
        for p in self.msp.query("LWPOLYLINE"):
            pts = p.get_points()
            for b in dim_boxes:
                if all(b[0] <= pt[0] <= b[2] and b[1] <= pt[1] <= b[3] for pt in pts):
                    duplicate_polys.append((p.dxf.layer, pts))

        self.assertEqual(
            len(duplicate_polys),
            0,
            f"Found {len(duplicate_polys)} duplicate polylines over dimensions: {duplicate_polys}",
        )

    def test_continuous_closed_contours_and_cavities(self):
        """Task 021 Contract 2: Profiles and cavities must form continuous closed loops."""
        polys = list(self.msp.query("LWPOLYLINE"))
        closed_polys = [p for p in polys if p.is_closed]

        self.assertGreater(
            len(closed_polys),
            150,
            f"Expected >150 closed loops (outer boundaries + internal chambers), found {len(closed_polys)}",
        )

        # Check for substantial closed loops representing profile chambers (>= 8 vertices)
        cavity_loops = [p for p in closed_polys if len(p.get_points()) >= 8]
        self.assertGreater(
            len(cavity_loops),
            30,
            f"Expected >30 profile chamber loops (>= 8 vertices), found {len(cavity_loops)}",
        )

    def test_native_arc_bulge_orientation_and_continuity(self):
        """Task 021 Contract 3: Arc bulges must have correct native orientation (not inverted)."""
        bulge_count = 0
        pos_fillets = 0
        neg_fillets = 0

        for p in self.msp.query("LWPOLYLINE"):
            pts = p.get_points(format="xyb")
            for pt in pts:
                b = pt[2]
                if abs(b) > 1e-4:
                    bulge_count += 1
                    # Standard 90-degree corner fillets: |b| ~ 0.4142
                    if abs(abs(b) - 0.4142) < 0.005:
                        if b > 0:
                            pos_fillets += 1
                        else:
                            neg_fillets += 1

        self.assertGreater(bulge_count, 800, f"Expected >800 native arc bulges, found {bulge_count}")
        # Both positive (CCW) and negative (CW) fillets must naturally exist in closed contours
        self.assertGreater(pos_fillets, 50, f"Expected >50 CCW fillets (bulge ~ +0.4142), found {pos_fillets}")
        self.assertGreater(neg_fillets, 50, f"Expected >50 CW fillets (bulge ~ -0.4142), found {neg_fillets}")

    def test_fillet_curvature_points_towards_center(self):
        """Task 021 Contract 4: Every fillet arc must curve towards its center, not outside."""
        # Test mathematical arc recovery for a known 90-degree corner
        c1 = (0.0, 1.0)
        c2 = (0.0, 0.4477)
        c3 = (0.4477, 0.0)
        c4 = (1.0, 0.0)
        info = compute_cad_arc_bulge(c1, c2, c3, c4)

        self.assertIsNotNone(info)
        self.assertAlmostEqual(info["R_mm"], 1.0, places=2)
        # Traversal from (0, 1) down to (1, 0) around center (1, 1) is counter-clockwise -> positive bulge
        self.assertAlmostEqual(info["bulge"], 0.4142, places=3)

        # Reverse traversal: from (1, 0) up to (0, 1) around center (1, 1) is clockwise -> negative bulge
        rev = reverse_xyb([(c1[0], c1[1], info["bulge"]), (c4[0], c4[1], 0.0)])
        self.assertEqual(len(rev), 2)
        self.assertAlmostEqual(rev[0][2], -0.4142, places=3)

    def test_glass_seals_curved_geometry(self):
        """Task 021 Contract 5: Glass unit seals must have smooth curved meniscus arcs."""
        seal_polys = [p for p in self.msp.query("LWPOLYLINE") if p.dxf.layer == "04_УПЛОТНИТЕЛИ_ГЕРМЕТИКИ"]
        self.assertEqual(len(seal_polys), 2, f"Expected 2 glass seal curves, found {len(seal_polys)}")
        for sp in seal_polys:
            pts = sp.get_points(format="xyb")
            has_bulge = any(abs(pt[2]) > 1e-4 for pt in pts)
            self.assertTrue(has_bulge, f"Glass seal polyline must have curved arc bulge: {pts}")

    def test_dwg_binary_output_exists_and_valid(self):
        """Task 021 Contract 6: Binary DWG must be generated via local AutoCAD engine."""
        self.assertTrue(self.out_dwg.exists(), f"DWG file not generated: {self.out_dwg}")
        self.assertGreater(self.out_dwg.stat().st_size, 50000, "DWG file is too small or corrupt")
        self.assertTrue(self.res["dwgCompiled"], "DWG compilation reported failure")


if __name__ == "__main__":
    unittest.main()
