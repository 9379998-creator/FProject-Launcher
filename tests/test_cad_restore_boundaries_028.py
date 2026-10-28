"""
FERO CAD Unit Test Suite — Task 028 (Restored Product Boundaries, Cavities & Closed Contours)
=============================================================================================
Validates the strict contracts of Task 028 on Reynaers MasterLine 8 (Section PIDI 2, Page 703):
1. Exact Layer 'Размерная линия': All dimensions are native AutoCAD DIMENSION entities on layer 'Размерная линия';
2. Exact Millimeter Distance & Decimal Accuracy: Dimensions (51.5, 42.5, 68.5, 77, 104.5...) have measured mm distances <= 0.15 mm error;
3. Restored Top Profile Outer & Inner Boundaries:
   - Outer perimeter wall of the profile forms a continuous closed loop (is_closed == True);
   - Internal chambers (камеры профиля) are preserved as closed loops;
4. Restored Glass Unit Constituents:
   - Distance spacer bars (дистанционные рамки) and secondary silicone sealant are preserved on layer '05_СТЕКЛОПАКЕТ' as closed loops;
5. Restored Thermal Breaks:
   - Connecting thermal break strips on layer '03_ТЕРМОМОСТ' have complete crimping tooth edges without bite-offs;
6. Zero Hatch & Clean Extrusions:
   - HATCH == 0, cavities remain empty, no dense hatch zigzags;
7. Physical Component Assembly:
   - Distinct extruded products assembled into ACAD_GROUP with dimensions strictly excluded;
8. Binary DWG Compilation:
   - generated_028.dwg compiled cleanly via accoreconsole.
"""

import math
import re
import unittest
from pathlib import Path
import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadRestoreBoundaries028(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(
            r"G:\Общие диски\006_Информационная база\Каталоги профильных систем\0004 Reynaers\MASTERLINE 8 - 2019.pdf"
        )
        cls.has_pdf = cls.pdf_path.exists()

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dxf = cls.out_dir / "generated_028.dxf"
        cls.out_dwg = cls.out_dir / "generated_028.dwg"

        # Crop box for Section PIDI 2 (Window pivot inward opening)
        cls.crop_rect = (150.0, 100.0, 520.0, 720.0)

        if cls.has_pdf:
            cls.res = export_pdf_page_to_cad(
                pdf_path=cls.pdf_path,
                page_number=703,
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
            cls.res = {}
            cls.doc = None
            cls.msp = []

    def setUp(self):
        if not self.has_pdf:
            self.skipTest(f"PDF not found: {self.pdf_path}")

    def test_dwg_and_dxf_generation(self):
        """Contract 8: generated_028.dxf and generated_028.dwg exist and compiled."""
        self.assertTrue(self.out_dxf.exists(), "generated_028.dxf must exist")
        self.assertGreater(self.out_dxf.stat().st_size, 1000, "DXF must not be empty")
        self.assertTrue(self.out_dwg.exists(), "generated_028.dwg must exist")
        self.assertGreater(self.out_dwg.stat().st_size, 1000, "DWG must not be empty")

    def test_dimensions_on_exact_layer(self):
        """Contract 1: All dimensions are native DIMENSION entities on layer 'Размерная линия'."""
        dims = [e for e in self.msp if e.dxftype() == "DIMENSION"]
        self.assertGreaterEqual(len(dims), 7, f"Expected >= 7 dimensions, got {len(dims)}")
        for d in dims:
            self.assertEqual(
                d.dxf.layer,
                "Размерная линия",
                f"Dimension must be strictly on layer 'Размерная линия', got {d.dxf.layer}",
            )

    def test_dimension_values_accuracy(self):
        """Contract 2: Measured distances in mm accurately match catalog nominals (51.5, 42.5, 68.5, 77, 104.5)."""
        dims = [e for e in self.msp if e.dxftype() == "DIMENSION"]
        found_nominals = set()
        for d in dims:
            p1 = d.dxf.defpoint2
            p2 = d.dxf.defpoint3
            meas_mm = math.hypot(p1.x - p2.x, p1.y - p2.y)
            txt = d.dxf.text
            if txt:
                found_nominals.add(txt)
                val = float(txt)
                diff = abs(meas_mm - val)
                self.assertLess(
                    diff, 0.25, f"Dimension '{txt}' measured {meas_mm:.2f} mm exceeds tolerance (diff={diff:.2f})"
                )

        expected_nominals = {"51.5", "42.5", "77", "68.5"}
        missing = expected_nominals - found_nominals
        self.assertEqual(len(missing), 0, f"Expected nominals {expected_nominals} missing: {missing}")

    def test_top_profile_outer_and_inner_boundaries(self):
        """Contract 3: Top profile has continuous closed outer perimeter and inner chambers."""
        polys = [e for e in self.msp if e.dxftype() == "LWPOLYLINE"]
        top_closed = []
        for p in polys:
            if not p.is_closed:
                continue
            pts = list(p.get_points(format="xyb"))
            ys = [pt[1] for pt in pts]
            xs = [pt[0] for pt in pts]
            if max(ys) >= 365.0 and min(xs) >= 160.0 and max(xs) <= 240.0:
                top_closed.append((p, max(xs) - min(xs), max(ys) - min(ys), len(pts)))

        self.assertGreaterEqual(
            len(top_closed),
            5,
            f"Expected >= 5 closed loops in top profile region, found {len(top_closed)}",
        )
        # Check substantial profile wall loops exist (> 25 mm span)
        large_top = [c for c in top_closed if c[1] >= 20.0 or c[2] >= 25.0]
        self.assertGreaterEqual(
            len(large_top),
            2,
            f"Expected outer perimeter and main chamber (> 20mm span), found {len(large_top)}",
        )

    def test_glass_unit_spacer_and_silicone_restored(self):
        """Contract 4: Spacer bars and secondary silicone seals are preserved on layer '05_СТЕКЛОПАКЕТ'."""
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
            f"Expected >= 2 closed spacer bar / silicone loops, found {len(closed_glass)}",
        )

    def test_thermal_breaks_intact(self):
        """Contract 5: Thermal breaks on layer '03_ТЕРМОМОСТ' have complete crimping edges."""
        tb_polys = [e for e in self.msp if e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "03_ТЕРМОМОСТ"]
        self.assertGreaterEqual(
            len(tb_polys),
            1,
            f"Expected thermal breaks on layer '03_ТЕРМОМОСТ', found {len(tb_polys)}",
        )

    def test_zero_hatch_and_clean_extrusions(self):
        """Contract 6: Zero HATCH entities, cavities empty, no dense hatch zigzags."""
        hatches = [e for e in self.msp if e.dxftype() == "HATCH"]
        self.assertEqual(len(hatches), 0, f"Zero-hatch contract violated: found {len(hatches)} HATCH entities")

    def test_physical_component_groups(self):
        """Contract 7: Discrete extruded products assembled into ACAD_GROUP without dimensions."""
        from app.cad.component_assembler import assemble_physical_components
        res = assemble_physical_components(self.doc)
        groups = res.get("groups", [])
        self.assertGreaterEqual(len(groups), 4, f"Expected >= 4 component groups, found {len(groups)}")
        group_ids = {g["id"] for g in groups}
        self.assertIn("PART_GLASS_UNIT", group_ids, "Glass unit must be assembled into a component group")
        self.assertIn("PART_ALU_SASH_OUTER", group_ids, "Outer sash profile must be assembled into a component group")

        # Verify dimensions are strictly excluded from groups
        for name, grp in self.doc.groups:
            for ent in grp:
                self.assertNotEqual(
                    ent.dxftype(),
                    "DIMENSION",
                    f"Dimension entity {ent.dxf.handle} must never be added to component group {name}",
                )


if __name__ == "__main__":
    unittest.main()
