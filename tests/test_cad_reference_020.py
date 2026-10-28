import unittest
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadReference020(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_020.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_020.dxf"

        # Execute extraction with Task 020 native bulges, full styling, and natural drawing-order chaining
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

    def test_native_circular_arc_bulges(self):
        """Task 020 Contract 1: Curves must be represented by native mathematical bulges, not facetted chords."""
        bulge_count = 0
        bulge_values = []
        for e in self.msp.query("LWPOLYLINE"):
            for p in e.get_points(format="xyb"):
                if abs(p[2]) > 1e-4:
                    bulge_count += 1
                    bulge_values.append(p[2])

        self.assertGreater(
            bulge_count, 500,
            f"Expected >500 native circular arc bulges in LWPOLYLINEs, found {bulge_count}"
        )
        # Verify typical standard fillet bulges exist
        has_fillet_bulge = any(abs(abs(b) - 0.184) < 0.01 for b in bulge_values)
        self.assertTrue(has_fillet_bulge, "Expected standard 41-45 deg fillet bulges (~0.184) in profiles")

    def test_dimensions_exact_measurement_and_green_styling(self):
        """Task 020 Contract 4: Dimensions must display exact 87, 76, 3 and be styled in Green (ACI 3)."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertEqual(len(dims), 3, "Must have exactly 3 dimensions")

        rendered_texts = []
        for d in dims:
            self.assertEqual(d.dxf.dimstyle, "FERO_MM", "Must use FERO_MM dimstyle with dimlfac=1.0")
            self.assertIn(d.dxf.layer, ("07_РАЗМЕРЫ", "Размерная линия"), "Must be on dimension layer")
            self.assertEqual(d.dxf.color, 3, "Dimension entities must be Green (color 3)")
            geom_name = getattr(d.dxf, "geometry", None)
            if geom_name and geom_name in self.doc.blocks:
                b = self.doc.blocks[geom_name]
                for e in b.query("MTEXT TEXT"):
                    txt = getattr(e.dxf, "text", "") if hasattr(e.dxf, "text") else getattr(e, "text", "")
                    rendered_texts.append(txt)

        self.assertIn("87", rendered_texts)
        self.assertIn("76", rendered_texts)
        self.assertIn("3", rendered_texts)
        for t in rendered_texts:
            self.assertNotIn("8702", t)
            self.assertNotIn("7599", t)

    def test_complete_text_annotations_and_colors(self):
        """Task 020 Contract 3: All annotations present, Cyrillic readable, yellow leader text, cyan notes."""
        texts = list(self.msp.query("TEXT"))
        self.assertGreaterEqual(len(texts), 18, f"Expected at least 18 text annotations, found {len(texts)}")

        text_map = {t.dxf.text: t for t in texts}

        # Check key leader texts in Yellow (color 2)
        key_yellow = ["Подоконный профиль", "Створка окна", "Рама окна", "Низ рамы окна"]
        for k in key_yellow:
            self.assertIn(k, text_map, f"Missing leader text: {k}")
            self.assertEqual(text_map[k].dxf.color, 2, f"Text '{k}' must be Yellow (color 2)")

        # Check key notes in Cyan (color 4)
        self.assertIn("внутренняя отделка**", text_map, "Must include 'внутренняя отделка**'")
        self.assertEqual(text_map["внутренняя отделка**"].dxf.color, 4, "'внутренняя отделка**' must be Cyan (color 4)")
        self.assertEqual(text_map["внутренняя отделка**"].dxf.layer, "09_АННОТАЦИИ_ПРИМЕЧАНИЯ")
        self.assertGreater(text_map["внутренняя отделка**"].dxf.insert.x, 650.0, "Position must be above concrete slab (>650 mm)")

        self.assertIn("граница НВФ**", text_map)
        self.assertEqual(text_map["граница НВФ**"].dxf.color, 4)

        self.assertIn("Отлив**", text_map)
        self.assertEqual(text_map["Отлив**"].dxf.color, 4)

    def test_batt_insulation_and_breakline(self):
        """Task 020 Contract 2: Batt insulation S-curves and green breakline preserved."""
        insul = list(self.msp.query('*[layer=="06_УТЕПЛИТЕЛЬ_ВОЛНА"]'))
        self.assertGreater(len(insul), 50, f"Expected >50 batt insulation elements, found {len(insul)}")
        total_pts = sum(len(list(p.vertices())) for p in insul)
        self.assertGreater(total_pts, 150, f"Insulation must have >150 vertices, found {total_pts}")

        breakline = list(self.msp.query('*[layer=="02_ЛИНИЯ_ОБРЫВА"]'))
        self.assertGreater(len(breakline), 0, "Green breakline at bottom must exist")
        self.assertEqual(breakline[0].dxf.color, 3, "Breakline must be Green (color 3)")

    def test_glass_seal_arcs_present(self):
        """Task 020 Contract 1: Two glass seal arcs reconnected in glass unit."""
        seals = list(self.msp.query('*[layer=="04_УПЛОТНИТЕЛИ_ГЕРМЕТИКИ"]'))
        self.assertGreaterEqual(len(seals), 2, "Must contain at least 2 glass unit seal arcs")

    def test_dwg_binary_compilation_020(self):
        """Task 020 Contract 5: Native compiled DWG binary exists and has valid AC1032 header."""
        self.assertTrue(self.out_dwg.exists(), "Compiled DWG file must exist")
        self.assertGreater(self.out_dwg.stat().st_size, 150_000, "Compiled DWG must be > 150KB")
        with open(self.out_dwg, "rb") as f:
            header = f.read(6).decode("ascii", errors="ignore")
        self.assertTrue(
            header.startswith("AC10"),
            f"Expected valid AutoCAD header starting with AC10, found {header}"
        )


if __name__ == "__main__":
    unittest.main()
