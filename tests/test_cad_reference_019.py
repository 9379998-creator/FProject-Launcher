import unittest
import math
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadReference019(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_019.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_019.dxf"

        # Execute extraction with Task 019 continuous chaining and dimlfac=1.0
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

    def test_dimensions_exact_measurement_and_not_scaled_100x(self):
        """Contract 4: Dimensions must display exact values (87, 76, 3), NOT 100x multiplier (8702, 7599)."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertEqual(len(dims), 3, "Must have exactly 3 dimensions")

        # Check rendered text in dimension geometry blocks
        rendered_texts = []
        for d in dims:
            self.assertEqual(d.dxf.dimstyle, "FERO_MM", "Must use FERO_MM dimstyle with dimlfac=1.0")
            geom_name = getattr(d.dxf, "geometry", None)
            if geom_name and geom_name in self.doc.blocks:
                b = self.doc.blocks[geom_name]
                for e in b.query("MTEXT TEXT"):
                    txt = getattr(e.dxf, "text", "") if hasattr(e.dxf, "text") else getattr(e, "text", "")
                    rendered_texts.append(txt)

        self.assertIn("87", rendered_texts, f"Expected '87' in rendered dimension texts, found {rendered_texts}")
        self.assertIn("76", rendered_texts, f"Expected '76' in rendered dimension texts, found {rendered_texts}")
        self.assertIn("3", rendered_texts, f"Expected '3' in rendered dimension texts, found {rendered_texts}")

        # Ensure NO 100x multiplied texts exist
        for t in rendered_texts:
            self.assertNotIn("8702", t, "Dimension must not be multiplied by 100")
            self.assertNotIn("7599", t, "Dimension must not be multiplied by 100")

    def test_zero_wipeout_mask_boxes_over_text(self):
        """Contract 3: Pure white wipeout mask rectangles crossing out text must be eliminated."""
        # Polylines on text layer or insulation layer should not contain text bounding box wipeouts
        insulation_polys = list(self.msp.query('*[layer=="06_ШТРИХОВКА_УТЕПЛИТЕЛЬ"]'))
        for p in insulation_polys:
            pts = list(p.vertices())
            # Wipeout boxes were small 4-5 vertex rectangles with width 50-100 and height 5-15 right around text
            dx = max(pt[0] for pt in pts) - min(pt[0] for pt in pts)
            dy = max(pt[1] for pt in pts) - min(pt[1] for pt in pts)
            # If it has aspect ratio ~10:1 and 4 vertices around text, it was a wipeout
            if len(pts) <= 5 and 40 < dx < 120 and 4 < dy < 15:
                # Should not be in insulation
                self.fail(f"Found residual wipeout mask rectangle {dx:.1f}x{dy:.1f} on insulation layer")

    def test_segment_continuity_at_radiuses(self):
        """Contract 1: Segments and curves must be chained into continuous smooth polylines."""
        profile_polys = list(self.msp.query('*[layer=="01_ПРОФИЛИ_ОКНА"]'))
        self.assertGreater(len(profile_polys), 0, "Must have profile polylines")
        # Ensure profiles are unified chains with native bulges, not isolated 2-point segments
        avg_pts = sum(len(list(p.vertices())) for p in profile_polys) / len(profile_polys)
        self.assertGreater(avg_pts, 2.5, f"Profiles must be chained smooth polylines (avg {avg_pts} pts/poly)")

    def test_cyrillic_font_style(self):
        """Contract 3: Text annotations must use Arial TrueType font for clean Russian Cyrillic display."""
        self.assertIn("Standard", self.doc.styles)
        style = self.doc.styles.get("Standard")
        self.assertEqual(style.dxf.font.lower(), "arial.ttf", "Standard style must use arial.ttf")

        texts = [t.dxf.text for t in self.msp.query("TEXT")]
        full_text = " ".join(texts)
        self.assertIn("Подоконный профиль", full_text)
        self.assertIn("Створка окна", full_text)
        self.assertIn("Рама окна", full_text)
        self.assertIn("Низ рамы окна", full_text)

    def test_dwg_binary_compilation_019(self):
        """Contract 5: Valid AutoCAD binary DWG must be generated via accoreconsole."""
        self.assertTrue(self.out_dwg.exists(), "Compiled DWG file must exist")
        self.assertGreater(self.out_dwg.stat().st_size, 100_000, "Compiled DWG must be > 100KB")
        with open(self.out_dwg, "rb") as f:
            header = f.read(6)
        self.assertTrue(header.startswith(b"AC"), f"DWG must have AutoCAD header. Got: {header}")


if __name__ == "__main__":
    unittest.main()
