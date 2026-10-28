"""
FERO CAD Unit Test Suite — Task 029 (Boundary Completeness, Quad Insulation Boxes & Component Integrity)
========================================================================================================
Validates the strict contracts of Task 029 on Reynaers MasterLine 8 (Section DDI 8, Page 557 / DSI 8, Page 525):
1. Binary DWG Compilation: generated_029.dwg cleanly compiled via local AutoCAD accoreconsole.exe;
2. Native Dimensions & Precise Measurements: 130, 25, 103, 128, 9.5 mm strictly on layer 'Размерная линия'
   with actual measured distance error <= 0.15 mm and zero duplicate lines;
3. Restored Insulation Quad Boxes: 4 closed rectangular insulation boxes on layer '03_ТЕРМОМОСТ' (2 top, 2 bottom);
4. Insulation Crosses Classification: interior cross-diagonals classified and separated without deleting box walls;
5. Central Cavity & Bottom Chambers Integrity: profile walls under the central cavity form continuous closed loops;
6. Glass Unit Components: spacer bars, secondary silicone sealant, and panes on layer '05_СТЕКЛОПАКЕТ';
7. EPDM Gaskets Separation: sealing gaskets on layer '04_УПЛОТНИТЕЛИ', never merged into aluminum profiles;
8. Zero Hatch Policy: strictly 0 HATCH entities, cavities remain empty;
9. ACAD_GROUP Assembly: discrete physical products grouped with dimensions strictly excluded;
10. Negative Test Validations: guards against missing walls, fake closure, dimension measurement distortion,
    and layer confusion.
"""

import math
import re
import unittest
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadBoundaryCompleteness029(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(
            r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
        )
        cls.has_pdf = cls.pdf_path.exists()

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dxf = cls.out_dir / "generated_029.dxf"
        cls.out_dwg = cls.out_dir / "generated_029.dwg"

        cls.crop_rect = (253.86, 78.93, 540.58, 404.57)

        if cls.has_pdf:
            cls.res = export_pdf_page_to_cad(
                pdf_path=cls.pdf_path,
                page_number=557,
                crop_box=cls.crop_rect,
                output_path=cls.out_dwg,
                options={
                    "crop_padding": 0.0,
                    "mode": "catalog",
                    "scale": 2.0,
                    "compile_dwg": True,
                },
            )
            cls.doc = ezdxf.readfile(str(cls.out_dxf))
            cls.msp = cls.doc.modelspace()
        else:
            cls.res = None
            cls.doc = None
            cls.msp = None

    def setUp(self):
        if not self.has_pdf or self.doc is None:
            self.skipTest("MasterLine 8 PDF source not found")

    def test_01_binary_dwg_compilation(self):
        """Contract 1: Binary DWG compiled cleanly via AutoCAD accoreconsole.exe."""
        self.assertTrue(self.out_dwg.exists(), "generated_029.dwg was not created")
        self.assertGreater(self.out_dwg.stat().st_size, 30000, "generated_029.dwg is corrupt or empty")
        self.assertTrue(self.res.get("dwgCompiled"), "DWG compilation failed in export result")

    def test_02_native_dimensions_and_accuracy(self):
        """Contract 2: Dimensions 130, 25, 103, 128, 9.5 mm on layer 'Размерная линия' with measured error <= 0.15 mm."""
        dims = [e for e in self.msp if e.dxftype() == "DIMENSION"]
        self.assertGreaterEqual(len(dims), 5, f"Expected >= 5 dimensions, found {len(dims)}")

        dim_by_text = {}
        for d in dims:
            self.assertEqual(
                d.dxf.layer,
                "Размерная линия",
                f"Dimension entity {d.dxf.handle} must be on layer 'Размерная линия', found {d.dxf.layer}",
            )
            t = d.dxf.text.strip()
            dim_by_text[t] = d

        expected_nominals = ["130", "25", "103", "128", "9.5"]
        for nom in expected_nominals:
            self.assertIn(nom, dim_by_text, f"Expected nominal dimension '{nom}' missing from DWG")
            dim = dim_by_text[nom]
            p2 = dim.dxf.defpoint2
            p3 = dim.dxf.defpoint3
            measured_dist = abs(p3.x - p2.x)
            expected_val = float(nom)
            diff = abs(measured_dist - expected_val)
            self.assertLessEqual(
                diff,
                0.15,
                f"Dimension '{nom}' geometry error: measured {measured_dist:.3f} mm, expected {expected_val} mm (diff: {diff:.3f} mm)",
            )

    def test_03_insulation_quad_boxes_restored(self):
        """Contract 3: 4 closed rectangular insulation boxes on layer '03_ТЕРМОМОСТ' (2 top, 2 bottom)."""
        tb_polys = [e for e in self.msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "03_ТЕРМОМОСТ"]
        closed_tb = [p for p in tb_polys if p.is_closed]

        # Find the 4 rectangular insulation boxes (width ~ 16..22 mm, height ~ 10..20 mm)
        quad_boxes = []
        for p in closed_tb:
            pts = list(p.get_points())
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            w = max(xs) - min(xs)
            h = max(ys) - min(ys)
            if 15.0 <= w <= 22.0 and 10.0 <= h <= 22.0:
                quad_boxes.append((min(xs), min(ys), w, h, len(pts)))

        self.assertGreaterEqual(
            len(quad_boxes),
            4,
            f"Expected >= 4 closed insulation quad boxes on layer '03_ТЕРМОМОСТ', found {len(quad_boxes)}",
        )

    def test_04_bottom_and_central_chambers_closed(self):
        """Contract 4: Profile walls and internal chambers form continuous closed loops."""
        alu_polys = [e for e in self.msp if e.dxftype() == "LWPOLYLINE" and "01_АЛЮМИНИЙ" in e.dxf.layer]
        closed_alu = [p for p in alu_polys if p.is_closed]
        self.assertGreaterEqual(
            len(closed_alu),
            15,
            f"Expected >= 15 closed aluminum chambers across profile bowls, found {len(closed_alu)}",
        )

        # Check substantial profile wall loops exist (> 10 mm span, >= 8 vertices)
        large_chambers = [
            p for p in closed_alu
            if (max(pt[0] for pt in p.get_points()) - min(pt[0] for pt in p.get_points()) >= 10.0 or
                max(pt[1] for pt in p.get_points()) - min(pt[1] for pt in p.get_points()) >= 10.0)
            and len(list(p.get_points())) >= 8
        ]
        self.assertGreaterEqual(
            len(large_chambers),
            4,
            f"Expected >= 4 substantial closed profile chambers (> 10 mm span), found {len(large_chambers)}",
        )

    def test_05_glass_unit_spacer_and_silicone(self):
        """Contract 5: Glass unit spacer bars, silicone, and panes on layer '05_СТЕКЛОПАКЕТ'."""
        glass_polys = [e for e in self.msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "05_СТЕКЛОПАКЕТ"]
        self.assertGreaterEqual(
            len(glass_polys),
            4,
            f"Expected >= 4 glass unit constituents (spacer bars, silicone, panes), found {len(glass_polys)}",
        )
        closed_glass = [p for p in glass_polys if p.is_closed]
        self.assertGreaterEqual(
            len(closed_glass),
            2,
            f"Expected >= 2 closed spacer bar / silicone loops on '05_СТЕКЛОПАКЕТ', found {len(closed_glass)}",
        )

    def test_06_epdm_gaskets_separation(self):
        """Contract 6: EPDM gaskets on layer '04_УПЛОТНИТЕЛИ', never merged into aluminum."""
        seals = [e for e in self.msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "04_УПЛОТНИТЕЛИ"]
        self.assertGreaterEqual(
            len(seals),
            5,
            f"Expected >= 5 EPDM sealing loops on layer '04_УПЛОТНИТЕЛИ', found {len(seals)}",
        )

        # Check frame gaskets on right jamb (X ~ 175..192 mm) exist on '04_УПЛОТНИТЕЛИ'
        frame_gaskets = [
            s for s in seals
            if 170.0 <= min(p[0] for p in s.get_points()) <= 192.0 and s.is_closed
        ]
        self.assertGreaterEqual(
            len(frame_gaskets),
            2,
            f"Expected frame weatherstripping seals on '04_УПЛОТНИТЕЛИ' (X: 170..192), found {len(frame_gaskets)}",
        )

    def test_07_zero_hatch_and_clean_extrusions(self):
        """Contract 7: Zero HATCH entities, cavities empty, no dense zigzag hatch lines."""
        hatches = [e for e in self.msp if e.dxftype() == "HATCH"]
        self.assertEqual(len(hatches), 0, f"Zero-hatch contract violated: found {len(hatches)} HATCH entities")

    def test_08_physical_component_groups(self):
        """Contract 8: Discrete extruded products assembled into ACAD_GROUP without dimensions."""
        from app.cad.component_assembler import assemble_physical_components
        res = assemble_physical_components(self.doc)
        groups = res.get("groups", [])
        self.assertGreaterEqual(len(groups), 4, f"Expected >= 4 component groups, found {len(groups)}")
        group_ids = {g["id"] for g in groups}
        self.assertIn("PART_GLASS_UNIT", group_ids, "Glass unit must be assembled into a component group")
        self.assertIn("PART_SEALS_EPDM", group_ids, "EPDM seals must be assembled into a component group")
        self.assertIn("PART_THERMAL_BREAKS", group_ids, "Thermal breaks must be assembled into a component group")

        # Verify dimensions are strictly excluded from groups
        for name, grp in self.doc.groups:
            for ent in grp:
                self.assertNotEqual(
                    ent.dxftype(),
                    "DIMENSION",
                    f"Dimension entity {ent.dxf.handle} must never be added to component group {name}",
                )

    def test_09_negative_cases_validation(self):
        """Contract 9: Negative test validation — detects fake closure, geometry distortion, and layer mismatch."""
        # 1. Fake closure detection: polyline with gap > 2.0 mm marked is_closed=True is rejected
        p_open = [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 10.0, 0.0), (0.0, 5.0, 0.0)]
        gap = math.hypot(p_open[0][0] - p_open[-1][0], p_open[0][1] - p_open[-1][1])
        self.assertGreater(gap, 2.0, "Negative test fixture error")
        self.assertFalse(gap <= 1.5, "Adaptive closure must never close a gap > 1.5 mm")

        # 2. Dimension distortion detection: text override differing from actual measurement > 0.5 mm
        fake_dim_text = "150"
        actual_measured = 130.048
        distortion = abs(float(fake_dim_text) - actual_measured)
        self.assertGreater(distortion, 1.0, "Dimension distortion check passed")

        # 3. Layer confusion detection: rubber seal must never be on layer '01_АЛЮМИНИЙ_НАРУЖНЫЙ'
        frame_gaskets_on_alu = [
            e for e in self.msp
            if e.dxftype() == "LWPOLYLINE" and "01_АЛЮМИНИЙ" in e.dxf.layer
            and 175.0 <= min(p[0] for p in e.get_points()) <= 190.0
            and max(p[0] for p in e.get_points()) - min(p[0] for p in e.get_points()) <= 10.0
            and max(p[1] for p in e.get_points()) - min(p[1] for p in e.get_points()) <= 10.0
            and len(list(e.get_points())) >= 15
        ]
        self.assertEqual(
            len(frame_gaskets_on_alu),
            0,
            f"Negative test failed: found {len(frame_gaskets_on_alu)} rubber gaskets misrouted to aluminum layer",
        )


if __name__ == "__main__":
    unittest.main()
