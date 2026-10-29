"""Automated end-to-end tests for the progressive DWG -> PDF -> PNG pipeline."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from app.backend.dwg_engine import (
    _find_accoreconsole,
    _is_pdf_complete,
    _parse_layouts_txt,
    check_image_is_empty_sheet,
    is_accore_job_active,
    render_dwg_model_progressive,
    render_dwg_page_progressive,
)


class TestDwgToPdfPipeline(unittest.TestCase):
    """Tests progressive headless DWG -> PDF -> PNG conversion across DWG archetypes."""

    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp(prefix="fero_dwg_pdf_test_"))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_parse_layouts_txt_cp1251_and_utf8(self) -> None:
        layouts_file = self.temp_dir / "layouts.txt"
        layouts_file.write_bytes("1|00_Тит\r\n2|_01_ВЧ\r\n3|Лист 3\r\n".encode("cp1251"))
        parsed = _parse_layouts_txt(layouts_file)
        self.assertEqual(len(parsed), 3)
        self.assertEqual(parsed[0]["name"], "00_Тит")
        self.assertEqual(parsed[0]["tabOrder"], 1)
        self.assertEqual(parsed[1]["name"], "_01_ВЧ")
        self.assertEqual(parsed[1]["tabOrder"], 2)
        self.assertEqual(parsed[2]["name"], "Лист 3")
        self.assertEqual(parsed[2]["tabOrder"], 3)

    def test_02_model_space_dwg_export(self) -> None:
        accore = _find_accoreconsole()
        if not accore:
            self.skipTest("accoreconsole.exe not installed")

        candidates = [
            Path(r"C:\Users\a9379\Desktop\1\Узел по низу окна.dwg"),
            Path(__file__).resolve().parents[1] / "output_cad" / "task_032" / "case_b_schueco_e2_2.dwg",
        ]
        dwg_path = next((p for p in candidates if p.is_file()), None)
        if not dwg_path:
            self.skipTest("Model-space DWG fixture not found")

        cache_dir = self.temp_dir / "model_case"
        res = render_dwg_model_progressive(
            dwg_path,
            cache_dir,
            cache_key="model_case",
            dpi=150,
            wait_first_sheet_seconds=12.0,
            force=True,
        )
        deadline = time.time() + 45.0
        while is_accore_job_active(dwg_path) and time.time() < deadline:
            time.sleep(0.25)

        final_res = render_dwg_model_progressive(
            dwg_path,
            cache_dir,
            cache_key="model_case",
            dpi=150,
            force=False,
        )
        self.assertEqual(final_res["status"], "ok")
        self.assertEqual(final_res["pages"], 1)
        self.assertTrue(final_res["isComplete"])
        self.assertTrue(_is_pdf_complete(cache_dir / "page_0001.pdf"))
        self.assertTrue((cache_dir / "page-1.png").is_file())
        self.assertFalse(check_image_is_empty_sheet(cache_dir / "page-1.png"))

    def test_03_multi_sheet_paper_space_dwg_export(self) -> None:
        accore = _find_accoreconsole()
        if not accore:
            self.skipTest("accoreconsole.exe not installed")

        dwg_path = Path(r"C:\Users\a9379\Desktop\1\Новая папка\dwg\Исп.схема утеплитель НВФ.dwg")
        if not dwg_path.is_file():
            self.skipTest("Multi-sheet DWG fixture not found")

        cache_dir = self.temp_dir / "multi_case"
        render_dwg_model_progressive(
            dwg_path,
            cache_dir,
            cache_key="multi_case",
            dpi=150,
            wait_first_sheet_seconds=8.0,
            force=True,
        )
        deadline = time.time() + 60.0
        while is_accore_job_active(dwg_path) and time.time() < deadline:
            time.sleep(0.25)

        final_res = render_dwg_model_progressive(
            dwg_path,
            cache_dir,
            cache_key="multi_case",
            dpi=150,
            force=False,
        )
        self.assertEqual(final_res["pages"], 4)
        self.assertTrue(final_res["isComplete"])
        self.assertEqual(len(final_res["items"]), 4)
        for tab in range(1, 5):
            self.assertTrue(_is_pdf_complete(cache_dir / f"page_{tab:04d}.pdf"))
            png_p = cache_dir / f"page-{tab}.png"
            self.assertTrue(png_p.is_file() and png_p.stat().st_size > 10000)
            self.assertFalse(check_image_is_empty_sheet(png_p))

        # Verify on-demand 300 DPI page slice
        hd_res = render_dwg_page_progressive(dwg_path, cache_dir, "multi_case", page=2, dpi=300)
        self.assertTrue((cache_dir / "page-2@300.png").is_file())
        self.assertGreater(hd_res["bytes"], 20000)


if __name__ == "__main__":
    unittest.main()
