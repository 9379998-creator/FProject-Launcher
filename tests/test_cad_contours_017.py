import unittest
import math
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadContours017(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/catalog-pages-796-796.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target Schüco catalog fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)

        # Node 1: TipTronic
        cls.node1_crop = (20.0, 40.0, 565.0, 420.0)
        cls.node1_dxf = cls.out_dir / "test_node1_017.dxf"
        cls.res1 = export_pdf_page_to_cad(
            pdf_path=cls.pdf_path,
            page_number=1,
            crop_box=cls.node1_crop,
            output_path=cls.node1_dxf,
        )
        cls.doc1 = ezdxf.readfile(str(cls.node1_dxf))
        cls.msp1 = cls.doc1.modelspace()

        # Node 2: AWS 70 SL.HI
        cls.node2_crop = (20.0, 425.0, 565.0, 805.0)
        cls.node2_dxf = cls.out_dir / "test_node2_017.dxf"
        cls.res2 = export_pdf_page_to_cad(
            pdf_path=cls.pdf_path,
            page_number=1,
            crop_box=cls.node2_crop,
            output_path=cls.node2_dxf,
        )
        cls.doc2 = ezdxf.readfile(str(cls.node2_dxf))
        cls.msp2 = cls.doc2.modelspace()

    def test_scale_is_1_to_1_for_schueco(self):
        """Contract 3: Schüco catalog should be calibrated to 1:1 scale (scaleFactor = 1.0)."""
        self.assertEqual(self.res1["scaleFactor"], 1.0)
        self.assertEqual(self.res2["scaleFactor"], 1.0)
        self.assertEqual(self.doc1.header.get("$INSUNITS"), 4)  # Millimeters
        self.assertEqual(self.doc2.header.get("$INSUNITS"), 4)

    def test_native_dimension_entities(self):
        """Contract 4: Dimensions must be native AutoCAD DIMENSION entities."""
        dims1 = [e for e in self.msp1 if e.dxftype() == "DIMENSION"]
        dims2 = [e for e in self.msp2 if e.dxftype() == "DIMENSION"]
        self.assertGreater(len(dims1), 0, "Node 1 must have native DIMENSION entities")
        self.assertGreater(len(dims2), 0, "Node 2 must have native DIMENSION entities")

        # Verify dimension measurement for 70 mm frame depth in Node 1
        dists1 = [math.hypot(d.dxf.defpoint3[0] - d.dxf.defpoint2[0], d.dxf.defpoint3[1] - d.dxf.defpoint2[1]) for d in dims1]
        has_70_mm = any(abs(dist - 70.0) < 0.2 for dist in dists1)
        self.assertTrue(has_70_mm, f"Node 1 must have 70.0 mm dimension. Found: {dists1}")

        # Verify dimension measurement for 80 mm in Node 2
        dists2 = [math.hypot(d.dxf.defpoint3[0] - d.dxf.defpoint2[0], d.dxf.defpoint3[1] - d.dxf.defpoint2[1]) for d in dims2]
        has_80_mm = any(abs(dist - 80.0) < 0.2 for dist in dists2)
        self.assertTrue(has_80_mm, f"Node 2 must have 80.0 mm dimension. Found: {dists2}")

    def test_zero_hatch_entities(self):
        """Contract 2: Output DWG/DXF must contain ZERO HATCH entities."""
        hatches1 = [e for e in self.msp1 if e.dxftype() == "HATCH"]
        hatches2 = [e for e in self.msp2 if e.dxftype() == "HATCH"]
        self.assertEqual(len(hatches1), 0, "Contract 2: Zero HATCH entities allowed in Node 1")
        self.assertEqual(len(hatches2), 0, "Contract 2: Zero HATCH entities allowed in Node 2")

    def test_editable_polylines_in_modelspace(self):
        """Contract 1: Contours must be editable polylines in ModelSpace without monolithic INSERT blocks."""
        inserts1 = [e for e in self.msp1 if e.dxftype() == "INSERT"]
        inserts2 = [e for e in self.msp2 if e.dxftype() == "INSERT"]
        self.assertEqual(len(inserts1), 0, "Contract 1: No monolithic INSERT blocks in ModelSpace (Node 1)")
        self.assertEqual(len(inserts2), 0, "Contract 1: No monolithic INSERT blocks in ModelSpace (Node 2)")

        closed_polys1 = [p for p in self.msp1 if p.dxftype() == "LWPOLYLINE" and p.closed]
        closed_polys2 = [p for p in self.msp2 if p.dxftype() == "LWPOLYLINE" and p.closed]
        self.assertGreater(len(closed_polys1), 50, "Node 1 must have closed boundary and cavity polylines")
        self.assertGreater(len(closed_polys2), 50, "Node 2 must have closed boundary and cavity polylines")

    def test_layer_classification(self):
        """Layers must separate outer aluminum, inner aluminum, thermal break, and dimensions."""
        layers1 = {p.dxf.layer for p in self.msp1 if p.dxftype() == "LWPOLYLINE"}
        self.assertIn("01_АЛЮМИНИЙ_НАРУЖНЫЙ", layers1)
        self.assertIn("01_АЛЮМИНИЙ_ВНУТРЕННИЙ", layers1)
        self.assertIn("03_ТЕРМОМОСТ", layers1)


if __name__ == "__main__":
    unittest.main()
