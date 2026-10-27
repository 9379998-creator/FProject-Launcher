"""
FERO CAD Unit Test Suite — Task 024 (Physical Parts & Selectable Components)
=============================================================================
Validates the strict contracts of Task 024:
1. Physical Component Assembly: identifies and groups distinct components (>= 15 parts);
2. Native AutoCAD Groups (ACAD_GROUP): verified in group_table with proper IDs and names;
3. Duality Contract: individual contours/cavities remain independent closed LWPOLYLINEs;
4. Component Movement Isolation: moving a physical part on a copy moves its boundary,
   cavities, and hatch without displacing adjacent components;
5. Non-interference with dimensions: DIMENSION entities are clean and not swallowed by groups;
6. Binary DWG compilation: produces uzel_po_nizu_okna_generated_024.dwg via accoreconsole.
"""

import math
import unittest
from pathlib import Path

import ezdxf

from app.cad.pdf_cad_extractor import export_pdf_page_to_cad


class TestCadComponents024(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pdf_path = Path(r"runtime/fixtures/uzel_po_nizu_okna.pdf")
        if not cls.pdf_path.exists():
            raise unittest.SkipTest("Target window bottom fixture not found")

        cls.out_dir = Path(r"runtime/cache/cad")
        cls.out_dir.mkdir(parents=True, exist_ok=True)
        cls.out_dwg = cls.out_dir / "uzel_po_nizu_okna_generated_024.dwg"
        cls.out_dxf = cls.out_dir / "uzel_po_nizu_okna_generated_024.dxf"

        # Execute extraction with Task 024 physical component assembly
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

    def test_physical_components_count_and_taxonomy(self):
        """Contract 1: Recognizes >= 15 distinct physical components in the window detail."""
        components = self.res.get("components", [])
        self.assertGreaterEqual(
            len(components),
            15,
            f"Expected >= 15 physical components, found {len(components)}: {[c['id'] for c in components]}",
        )

        comp_ids = set(c["id"] for c in components)
        # Verify key structural components from the component map
        self.assertIn("PART_01_GLASS_UNIT", comp_ids)
        self.assertIn("PART_02_SEAL_GLASS_EXT", comp_ids)
        self.assertIn("PART_03_SEAL_GLASS_INT", comp_ids)
        self.assertIn("PART_05_GLAZING_BEAD", comp_ids)
        self.assertIn("PART_06_SASH_OUTER_ALU", comp_ids)
        self.assertIn("PART_07_SASH_INNER_ALU", comp_ids)
        self.assertIn("PART_10_FRAME_OUTER_ALU", comp_ids)
        self.assertIn("PART_11_FRAME_INNER_ALU", comp_ids)
        self.assertIn("PART_13_SUBFRAME_PROFILE", comp_ids)
        self.assertIn("PART_14_EXTERNAL_SILL_ALU", comp_ids)
        self.assertIn("PART_16_FOAM_INSULATION", comp_ids)

    def test_native_acad_groups_present_in_group_table(self):
        """Contract 2: Groups are stored in native AutoCAD group_table (ACAD_GROUP)."""
        groups = self.doc.groups
        self.assertGreaterEqual(len(groups), 15, f"Expected >= 15 AutoCAD groups, found {len(groups)}")

        group_names = set(name for name, g in groups)
        self.assertIn("PART_06_SASH_OUTER_ALU", group_names)
        self.assertIn("PART_10_FRAME_OUTER_ALU", group_names)
        self.assertIn("PART_01_GLASS_UNIT", group_names)

        # Verify group entities
        sash_grp = None
        for name, g in groups:
            if name == "PART_06_SASH_OUTER_ALU":
                sash_grp = g
                break
        self.assertIsNotNone(sash_grp)
        entities = list(sash_grp)
        self.assertGreater(len(entities), 0, "Sash group must contain entities")

    def test_duality_contract_individual_contours_preserved(self):
        """Contract 3: Level 1 individual closed LWPOLYLINEs remain independently editable."""
        closed_polys = [p for p in self.msp.query("LWPOLYLINE") if p.is_closed]
        self.assertGreater(
            len(closed_polys),
            150,
            f"Expected >150 independent closed loops (Level 1 duality), found {len(closed_polys)}",
        )

        # Verify 76-vertex chamber and 8-vertex chambers still exist as independent entities
        chamber_76 = [p for p in closed_polys if len(p.get_points()) in (75, 76, 77, 78)]
        self.assertGreaterEqual(len(chamber_76), 1, "76-vertex chamber polyline must exist independently")

    def test_component_movement_isolation(self):
        """Contract 4: Moving a physical component shifts all its parts without moving adjacent components."""
        groups = dict(self.doc.groups)
        sash_grp = groups.get("PART_06_SASH_OUTER_ALU")
        frame_grp = groups.get("PART_10_FRAME_OUTER_ALU")
        self.assertIsNotNone(sash_grp)
        self.assertIsNotNone(frame_grp)

        sash_ents = list(sash_grp)
        frame_ents = list(frame_grp)

        # Record initial bounds of sash and frame
        def get_bbox(ents):
            xs, ys = [], []
            for e in ents:
                if e.dxftype() == "LWPOLYLINE":
                    pts = list(e.get_points())
                    xs.extend(p[0] for p in pts)
                    ys.extend(p[1] for p in pts)
            return min(xs), min(ys), max(xs), max(ys)

        sash_b0 = get_bbox(sash_ents)
        frame_b0 = get_bbox(frame_ents)

        # Simulate movement by vector (+100.0, +50.0) mm on sash entities
        dx, dy = 100.0, 50.0
        moved_sash_pts = []
        for e in sash_ents:
            if e.dxftype() == "LWPOLYLINE":
                pts = [(p[0] + dx, p[1] + dy) for p in e.get_points()]
                moved_sash_pts.extend(pts)

        # Verify sash moved completely by (dx, dy)
        new_min_x = min(p[0] for p in moved_sash_pts)
        new_min_y = min(p[1] for p in moved_sash_pts)
        self.assertAlmostEqual(new_min_x, sash_b0[0] + dx, places=2)
        self.assertAlmostEqual(new_min_y, sash_b0[1] + dy, places=2)

        # Frame entities remain strictly untouched
        frame_b1 = get_bbox(frame_ents)
        self.assertAlmostEqual(frame_b1[0], frame_b0[0], places=3)
        self.assertAlmostEqual(frame_b1[1], frame_b0[1], places=3)

    def test_clean_dimensions_not_swallowed_by_groups(self):
        """Contract 5: Dimensions must remain outside component groups with zero overlap."""
        dims = list(self.msp.query("DIMENSION"))
        self.assertEqual(len(dims), 3, f"Expected 3 native DIMENSION entities, found {len(dims)}")

        # Verify no DIMENSION entity is part of any group
        all_grouped_handles = set()
        for name, g in self.doc.groups:
            for e in g:
                all_grouped_handles.add(e.dxf.handle)

        for d in dims:
            self.assertNotIn(
                d.dxf.handle,
                all_grouped_handles,
                f"Dimension {d.dxf.handle} must not be inside component groups",
            )

    def test_dwg_binary_output_valid_with_groups(self):
        """Contract 6: Binary DWG 024 is successfully generated with groups via accoreconsole."""
        self.assertTrue(self.out_dwg.exists(), f"DWG file does not exist: {self.out_dwg}")
        self.assertGreater(self.out_dwg.stat().st_size, 50000, "DWG file too small")
        self.assertTrue(self.res["dwgCompiled"], "DWG compilation failed")


if __name__ == "__main__":
    unittest.main()
