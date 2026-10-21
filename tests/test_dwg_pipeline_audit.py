import os
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

import app.backend.server as server


class TestDwgPipelineContracts(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = Path(self.temp_dir) / "source_dwg"
        self.source_dir.mkdir(parents=True)
        self.fake_dwg = self.source_dir / "test_drawing.dwg"
        self.fake_dwg.write_bytes(b"AC1032" + b"\x00" * 2000)

        self.cache_dir = Path(self.temp_dir) / "runtime_cache" / "dwg"
        self.cache_dir.mkdir(parents=True)

        self._orig_dwg_cache = server.DWG_CACHE_DIR
        server.DWG_CACHE_DIR = self.cache_dir

    def tearDown(self):
        server.DWG_CACHE_DIR = self._orig_dwg_cache
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_dwg_to_model_pdf_strictly_isolated_never_touches_source_dir(self):
        """DWG conversion must NEVER write anything into the source directory alongside the DWG."""
        def mock_convert_process(**kwargs):
            # Simulate conversion script output strictly into fallback_pdf/paired_pdf (which points to cache)
            out_pdf = kwargs.get("paired_pdf") or kwargs.get("fallback_pdf")
            out_pdf.write_bytes(b"%PDF-1.4 Fake PDF Content for Test" + b" " * 1024)
            # Write a complete manifest in the cache folder
            manifest_file = out_pdf.parent / "manifest.json"
            manifest_file.write_text(
                json.dumps({
                    "sourcePath": str(kwargs["path"]),
                    "sourceName": kwargs["path"].name,
                    "pdfPath": str(out_pdf),
                    "pageCount": 4,
                    "isComplete": True,
                    "sourceMtimeNs": kwargs["path"].stat().st_mtime_ns,
                    "sourceSize": kwargs["path"].stat().st_size,
                }),
                encoding="utf-8"
            )
            return MagicMock(returncode=0, stdout='{"ok": true}', stderr="")

        with patch("app.backend.server.dwg_convert_process", side_effect=mock_convert_process):
            pdf_path, is_cached = server.dwg_to_model_pdf(self.fake_dwg)

            # 1. Assert result is inside DWG_CACHE_DIR
            self.assertTrue(str(pdf_path).startswith(str(self.cache_dir)))
            self.assertTrue(pdf_path.exists())

            # 2. Assert source directory has ONLY the original .dwg file
            files_in_source = list(self.source_dir.iterdir())
            self.assertEqual(len(files_in_source), 1)
            self.assertEqual(files_in_source[0], self.fake_dwg)
            self.assertFalse((self.source_dir / "test_drawing.pdf").exists())

    def test_dwg_cache_hit_requires_is_complete_true(self):
        """A cache hit is only valid if manifest exists and isComplete is True."""
        key = server.file_cache_key(self.fake_dwg, "dwg-smart-cad-v3")
        target_dir = self.cache_dir / key
        target_dir.mkdir(parents=True)
        cached_pdf = target_dir / f"{self.fake_dwg.stem}.pdf"
        cached_pdf.write_bytes(b"%PDF-1.4 Fake Cached Content" + b" " * 1024)
        manifest_path = target_dir / "manifest.json"

        # Manifest with isComplete: False should NOT be a cache hit
        manifest_path.write_text(
            json.dumps({
                "sourcePath": str(self.fake_dwg),
                "isComplete": False,
                "sourceMtimeNs": self.fake_dwg.stat().st_mtime_ns,
                "sourceSize": self.fake_dwg.stat().st_size,
            }),
            encoding="utf-8"
        )

        with patch("app.backend.server.dwg_convert_process") as mock_convert:
            mock_convert.return_value = MagicMock(returncode=0, stdout='{"ok": true}', stderr="")
            # Because isComplete is False, it should invoke conversion process, not return cached immediately
            server.dwg_to_model_pdf(self.fake_dwg)
            self.assertTrue(mock_convert.called)


if __name__ == "__main__":
    unittest.main()
