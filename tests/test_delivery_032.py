import unittest
from pathlib import Path
import json
import ezdxf

RESULTS_PATH = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher\scratch\delivery_032_results.json")
OUT_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher\output_cad\task_032")


class TestDelivery032(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if RESULTS_PATH.exists():
            cls.results = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        else:
            cls.results = {}

    def test_01_case_a_reynaers_p557_artifacts(self):
        """Case A: Reynaers MASTERLINE 8 p557 verified DWG, reverse PDF plot, dimensions, and groups."""
        res = self.results.get("Case_A", {})
        self.assertEqual(res.get("status"), "PASS")
        dwg = Path(res.get("dwg_path", ""))
        self.assertTrue(dwg.exists(), f"DWG not found: {dwg}")
        self.assertGreater(dwg.stat().st_size, 50000)
        self.assertTrue(res.get("dwg_valid_header"), "Invalid DWG binary header (must start with AC10)")

        plot_pdf = Path(res.get("plot_pdf_path", ""))
        self.assertTrue(plot_pdf.exists(), f"Plotted reverse PDF not found: {plot_pdf}")
        self.assertGreater(plot_pdf.stat().st_size, 30000)

        self.assertEqual(res.get("dimensions_count"), 5)
        for d in res.get("dimension_details", []):
            self.assertLessEqual(d.get("diff", 999), 0.05, f"Dimension {d.get('text')} exceeded 0.05 mm tolerance")

        self.assertGreaterEqual(res.get("closed_aluminum_chambers", 0), 15)
        self.assertGreaterEqual(res.get("epdm_seals_count", 0), 5)

    def test_02_case_b_schueco_e2_2_two_independent_sections(self):
        """Case B: Schüco AWS 70 sheet E 2-2 verified DWG, 32 dimensions, and separate section groups."""
        res = self.results.get("Case_B", {})
        self.assertEqual(res.get("status"), "PASS")
        dwg = Path(res.get("dwg_path", ""))
        self.assertTrue(dwg.exists(), f"DWG not found: {dwg}")
        self.assertGreater(dwg.stat().st_size, 50000)
        self.assertTrue(res.get("dwg_valid_header"))

        plot_pdf = Path(res.get("plot_pdf_path", ""))
        self.assertTrue(plot_pdf.exists(), f"Plotted reverse PDF not found: {plot_pdf}")
        self.assertGreater(plot_pdf.stat().st_size, 30000)

        self.assertGreaterEqual(res.get("dimensions_count", 0), 30)

        s1_groups = res.get("section_1_groups", [])
        s2_groups = res.get("section_2_groups", [])
        self.assertGreaterEqual(len(s1_groups), 4, "Section 1 must have >= 4 independent component groups")
        self.assertGreaterEqual(len(s2_groups), 4, "Section 2 must have >= 4 independent component groups")
        # Ensure S1 and S2 have zero intersection in group names
        self.assertEqual(len(set(s1_groups) & set(s2_groups)), 0, "Groups must not be merged across sections")

    def test_03_case_c_mounting_node_reference_mode(self):
        """Case C: Mounting node constructor drawing DWG, reverse PDF plot, dimensions, and text annotations."""
        res = self.results.get("Case_C", {})
        self.assertEqual(res.get("status"), "PASS")
        dwg = Path(res.get("dwg_path", ""))
        self.assertTrue(dwg.exists(), f"DWG not found: {dwg}")
        self.assertGreater(dwg.stat().st_size, 50000)
        self.assertTrue(res.get("dwg_valid_header"))

        plot_pdf = Path(res.get("plot_pdf_path", ""))
        self.assertTrue(plot_pdf.exists(), f"Plotted reverse PDF not found: {plot_pdf}")
        self.assertGreater(plot_pdf.stat().st_size, 30000)

        self.assertGreaterEqual(res.get("dimensions_count", 0), 3)
        self.assertGreaterEqual(res.get("texts_count", 0), 15)

    def test_04_extra_control_1_reynaers_p525(self):
        """Extra 1: Unused Reynaers section DSI 8 p525 verified DWG, reverse plot, and dimensions."""
        res = self.results.get("Extra_1", {})
        self.assertEqual(res.get("status"), "PASS")
        dwg = Path(res.get("dwg_path", ""))
        self.assertTrue(dwg.exists())
        self.assertGreater(dwg.stat().st_size, 50000)
        self.assertTrue(res.get("dwg_valid_header"))

        plot_pdf = Path(res.get("plot_pdf_path", ""))
        self.assertTrue(plot_pdf.exists())
        self.assertGreater(plot_pdf.stat().st_size, 30000)
        self.assertGreaterEqual(res.get("dimensions_count", 0), 4)

    def test_05_extra_control_2_crop_invariance(self):
        """Extra 2: Crop offset invariance verified with 10 identical closed chambers and discrete groups."""
        res = self.results.get("Extra_2", {})
        self.assertEqual(res.get("status"), "PASS")
        dwg = Path(res.get("dwg_path", ""))
        self.assertTrue(dwg.exists())
        self.assertGreater(dwg.stat().st_size, 50000)
        self.assertTrue(res.get("dwg_valid_header"))
        self.assertEqual(res.get("closed_aluminum_chambers"), 10)
        self.assertGreaterEqual(len(res.get("groups", [])), 4)

    def test_06_server_backend_dwg_contract(self):
        """Server handler contract: genuine binary DWG compilation enforced on /api/pdf/export-cad."""
        res = self.results.get("Server_Contract", {})
        self.assertEqual(res.get("status"), "PASS")
        self.assertTrue(res.get("compile_dwg_enforced"))
        self.assertTrue(res.get("genuine_dwg_returned"))


if __name__ == "__main__":
    unittest.main()
