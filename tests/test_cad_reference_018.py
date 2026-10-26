import unittest
import math
import hashlib
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadReference018(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        # Verify SHA-256 against manifest
        with open(cls.pdf_path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        cls.expected_sha = "9ba7662ffbccd82eb20a81d14df5e333c11dde78e50c042db005e668873e240d"
        assert actual_sha == cls.expected_sha, f"SHA mismatch: {actual_sha} vs {cls.expected_sha}"

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_018.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_018.dxf"

        # Execute extraction in Task 018 Reference Mode
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

    def test_fixture_integrity(self):
        """Verify the specimen PDF is exactly the reference pair fixture."""
        with open(self.pdf_path, "rb") as f:
            actual_sha = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(actual_sha, self.expected_sha)

    def test_dynamic_scale_calibration(self):
        """Contract 1: Dynamic scale detection must calibrate to ~3.52 with millimeter units."""
        self.assertAlmostEqual(self.res["scaleFactor"], 3.52, delta=0.08)
        self.assertEqual(self.doc.header.get("$INSUNITS"), 4)  # Millimeters

    def test_native_dimension_entities(self):
        """Contract 4: Dimensions 87, 76, 3 must be native AutoCAD DIMENSION entities."""
        dims = [e for e in self.msp if e.dxftype() == "DIMENSION"]
        self.assertEqual(len(dims), 3, "Must have exactly 3 native DIMENSION entities")

        calculated_dists = []
        for d in dims:
            p2 = d.dxf.defpoint2
            p3 = d.dxf.defpoint3
            dist = math.hypot(p3[0] - p2[0], p3[1] - p2[1])
            calculated_dists.append(dist)

        has_87 = any(abs(d - 87.0) < 0.2 for d in calculated_dists)
        has_76 = any(abs(d - 76.0) < 0.2 for d in calculated_dists)
        has_3 = any(abs(d - 3.0) < 0.2 for d in calculated_dists)

        self.assertTrue(has_87, f"Missing 87.0 mm dimension. Found: {calculated_dists}")
        self.assertTrue(has_76, f"Missing 76.0 mm dimension. Found: {calculated_dists}")
        self.assertTrue(has_3, f"Missing 3.0 mm dimension. Found: {calculated_dists}")

    def test_hatches_preserved_and_segregated(self):
        """Contract 3: Hatches must be preserved on dedicated layers (unlike 017 zero-hatch)."""
        layers = self.res["layers"]
        self.assertIn("06_ШТРИХОВКА_СТЕНЫ", layers)
        insul_count = layers.get("06_ШТРИХОВКА_УТЕПЛИТЕЛЬ", 0) + layers.get("06_УТЕПЛИТЕЛЬ_ВОЛНА", 0)
        self.assertGreater(layers["06_ШТРИХОВКА_СТЕНЫ"], 100, "Wall masonry hatch must be preserved")
        self.assertGreater(insul_count, 100, "Insulation hatch must be preserved")

    def test_editable_closed_contours(self):
        """Contract 2: Profile boundaries and cavities must be closed polylines."""
        closed_polys = [p for p in self.msp if p.dxftype() == "LWPOLYLINE" and p.closed]
        self.assertGreater(len(closed_polys), 100, "Must have editable closed polylines")
        layers = self.res["layers"]
        self.assertIn("01_ПРОФИЛИ_ОКНА", layers)
        self.assertIn("02_ОТЛИВ_МЕТАЛЛ", layers)

    def test_cyrillic_text_annotations(self):
        """Cyrillic annotations and leaders must be present in readable positions."""
        texts = [t.dxf.text for t in self.msp if t.dxftype() == "TEXT"]
        full_text = " ".join(texts)
        self.assertIn("Подоконный профиль", full_text)
        self.assertIn("Створка окна", full_text)
        self.assertIn("Рама окна", full_text)
        self.assertIn("Низ рамы окна", full_text)
        self.assertIn("Пена монтажная", full_text)
        self.assertIn("Отлив", full_text)

        # Leader lines
        leaders = [p for p in self.msp if p.dxftype() == "LWPOLYLINE" and p.dxf.layer == "08_ВЫНОСКИ"]
        self.assertGreater(len(leaders), 10, "Must have leader lines and shelves")

    def test_dwg_binary_compilation(self):
        """Contract 5: Valid AutoCAD binary DWG must be generated via accoreconsole."""
        self.assertTrue(self.out_dwg.exists(), "Compiled DWG file must exist")
        self.assertGreater(self.out_dwg.stat().st_size, 100_000, "Compiled DWG must be > 100KB")
        with open(self.out_dwg, "rb") as f:
            header = f.read(6)
        self.assertTrue(header.startswith(b"AC"), f"DWG must have AutoCAD header. Got: {header}")


if __name__ == "__main__":
    unittest.main()
