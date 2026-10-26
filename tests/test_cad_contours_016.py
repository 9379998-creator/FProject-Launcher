import unittest
import math
from pathlib import Path
import ezdxf
import fitz

from app.cad.pdf_cad_extractor import PDFCadExtractor, export_pdf_page_to_cad


class TestCadContours016(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target catalog PDF not accessible in test environment")
        cls.page_num = 667
        # Filter rect around user crop (ox=285.88, oy=439.24)
        cls.crop_box = (299.88, 91.0, 560.0, 425.24)
        cls.out_dxf = Path(r"runtime/cache/cad/test_reconstructed_016.dxf")
        cls.out_dxf.parent.mkdir(parents=True, exist_ok=True)

        cls.res = export_pdf_page_to_cad(
            pdf_path=cls.pdf_path,
            page_number=cls.page_num,
            crop_box=cls.crop_box,
            output_path=cls.out_dxf,
        )
        cls.doc = ezdxf.readfile(str(cls.out_dxf))
        cls.msp = cls.doc.modelspace()

    def test_export_success_and_metadata(self):
        self.assertTrue(self.res["success"])
        self.assertEqual(self.res["page"], 667)
        self.assertEqual(self.res["scaleUnit"], "mm")
        self.assertEqual(self.res["scaleFactor"], 2.0)
        self.assertAlmostEqual(self.res["scale"], 0.705556, places=4)

    def test_dxf_header_units_millimeter(self):
        # INSUNITS 4 = Millimeters
        self.assertEqual(self.doc.header.get("$INSUNITS"), 4)

    def test_blocks_defined_for_components(self):
        block_names = [b.name for b in self.doc.blocks]
        self.assertIn("BLOCK_АЛЮМИНИЙ_НАРУЖНЫЙ", block_names)
        self.assertIn("BLOCK_АЛЮМИНИЙ_ВНУТРЕННИЙ", block_names)
        self.assertIn("BLOCK_ТЕРМОМОСТ", block_names)

        # Assert ModelSpace contains INSERT entities for each block
        inserts = [e for e in self.msp if e.dxftype() == "INSERT"]
        insert_names = {ins.dxf.name for ins in inserts}
        self.assertIn("BLOCK_АЛЮМИНИЙ_НАРУЖНЫЙ", insert_names)
        self.assertIn("BLOCK_АЛЮМИНИЙ_ВНУТРЕННИЙ", insert_names)
        self.assertIn("BLOCK_ТЕРМОМОСТ", insert_names)

    def test_dimension_scale_calibration(self):
        """Dimension 77.5 mm should measure 77.5 +- 0.2 mm in CAD space."""
        dim_lines = [e for e in self.msp if e.dxftype() == "LINE" and e.dxf.layer == "07_РАЗМЕРЫ_ЛИНИИ"]
        lengths = []
        for dl in dim_lines:
            p1, p2 = dl.dxf.start, dl.dxf.end
            lengths.append(math.hypot(p2[0] - p1[0], p2[1] - p1[1]))

        # Look for 77.5 mm and 25.0 mm lines
        has_77_5 = any(abs(l - 77.5) < 0.3 for l in lengths)
        has_25_0 = any(abs(l - 25.0) < 0.3 for l in lengths)
        self.assertTrue(has_77_5, f"Could not find 77.5 mm dimension line. Measured: {lengths}")
        self.assertTrue(has_25_0, f"Could not find 25.0 mm dimension line. Measured: {lengths}")

    def test_text_entities_rotation_and_size(self):
        texts = [e for e in self.msp if e.dxftype() == "TEXT"]
        self.assertGreater(len(texts), 0)

        # Check that no text entity has excessive height (> 6.0 mm)
        for t in texts:
            self.assertLessEqual(t.dxf.height, 6.0, f"Text {t.dxf.text} has blown-up height: {t.dxf.height}")
            self.assertGreaterEqual(t.dxf.height, 1.8, f"Text {t.dxf.text} is too small: {t.dxf.height}")

        # Check vertical profile text rotation (e.g. 408.0326.XX or 080.9124.SY)
        vert_texts = [t for t in texts if t.dxf.text in ("408.0326.XX", "080.9124.SY")]
        for vt in vert_texts:
            self.assertAlmostEqual(vt.dxf.rotation, 90.0, delta=1.0, msg=f"Text {vt.dxf.text} should be vertical (90 deg)")

    def test_layers_structure(self):
        layer_names = [l.dxf.name for l in self.doc.layers]
        self.assertIn("01_АЛЮМИНИЙ_НАРУЖНЫЙ", layer_names)
        self.assertIn("01_АЛЮМИНИЙ_ВНУТРЕННИЙ", layer_names)
        self.assertIn("03_ТЕРМОМОСТ", layer_names)
        self.assertIn("07_РАЗМЕРЫ_ЛИНИИ", layer_names)
        self.assertIn("07_РАЗМЕРЫ_СТРЕЛКИ", layer_names)
        self.assertIn("07_РАЗМЕРЫ_ТЕКСТ", layer_names)
        self.assertIn("09_АННОТАЦИИ_ТЕКСТ", layer_names)


if __name__ == "__main__":
    unittest.main()
