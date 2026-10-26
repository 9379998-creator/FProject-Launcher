import json
import os
import subprocess
import unittest
from pathlib import Path
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestRegression013EscapeAndLoad(unittest.TestCase):
    def test_escape_logic_in_app_js(self):
        """Verify handleGlobalEscape() in app.js calls exitWindow3() when in Window 3 and not swallowed."""
        app_js_path = REPO_ROOT / "app" / "frontend" / "app.js"
        self.assertTrue(app_js_path.exists(), "app.js must exist")
        content = app_js_path.read_text(encoding="utf-8")

        # Must call exitWindow3() in inWindow3() block
        self.assertIn("exitWindow3()", content)
        self.assertIn("function handleGlobalEscape()", content)

        # Check the exact block inside handleGlobalEscape
        escape_block_start = content.find("function handleGlobalEscape()")
        self.assertNotEqual(escape_block_start, -1)
        escape_block = content[escape_block_start:escape_block_start + 1200]
        self.assertIn("if (inWindow3())", escape_block)
        self.assertIn("exitWindow3();", escape_block)
        # Must NOT contain the old silent return
        self.assertNotIn("Escape не выбрасывает случайно из документа", escape_block)

    def test_escape_forwarding_in_launcher_translate_js(self):
        """Verify launcher-translate.js posts launcher-escape to parent when no local transient elements remain."""
        lt_js_path = REPO_ROOT / "app" / "frontend" / "lib" / "pdfjs" / "web" / "launcher-translate.js"
        self.assertTrue(lt_js_path.exists(), "launcher-translate.js must exist")
        content = lt_js_path.read_text(encoding="utf-8")

        self.assertIn("window.parent.postMessage({ type: \"launcher-escape\" }, \"*\")", content)
        self.assertIn("handlePdfJsEscape()", content)

    def test_load_button_contract_compliance(self):
        """Verify server.py /api/choose-folder checks returncode and logs errors."""
        server_py = REPO_ROOT / "app" / "backend" / "server.py"
        self.assertTrue(server_py.exists(), "server.py must exist")
        content = server_py.read_text(encoding="utf-8")

        self.assertIn('if parsed.path == "/api/choose-folder":', content)
        self.assertIn("proc.returncode != 0", content)
        self.assertIn('logger.error("PowerShell FolderBrowserDialog failed with exit code %s: %s"', content)

    def test_real_object_import_api(self):
        """Verify POST /api/objects/import on a real object folder returns valid manifest and updates /api/objects."""
        # Use existing verified folder on Desktop or scratch
        test_folder = REPO_ROOT / "runtime" / "manifests"
        self.assertTrue(test_folder.exists(), "manifests dir must exist")

        url = "http://127.0.0.1:8780/api/objects/import"
        req_data = json.dumps({"path": str(test_folder.resolve())}).encode("utf-8")
        req = urllib.request.Request(url, data=req_data, headers={"Content-Type": "application/json"})

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("id", data)
                self.assertEqual(data.get("name"), "manifests")
                self.assertIn("statistics", data)
        except urllib.error.URLError as err:
            self.skipTest(f"Backend on 8780 not reachable: {err}")

        # Check /api/objects has it
        with urllib.request.urlopen("http://127.0.0.1:8780/api/objects", timeout=10) as resp:
            self.assertEqual(resp.status, 200)
            objects_data = json.loads(resp.read().decode("utf-8"))
            items = objects_data.get("items", [])
            found = any(item.get("id") == data.get("id") for item in items)
            self.assertTrue(found, "Newly imported object must appear in /api/objects")


if __name__ == "__main__":
    unittest.main()
