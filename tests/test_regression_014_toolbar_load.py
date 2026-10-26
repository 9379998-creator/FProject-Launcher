import json
import os
import subprocess
import time
import unittest
from pathlib import Path
import urllib.request
import urllib.error

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestRegression014ToolbarAndLoad(unittest.TestCase):
    def test_in_window3_logic_in_app_js(self):
        """Verify inWindow3() strictly checks full-view and does NOT hide toolbar in Window 2."""
        app_js_path = REPO_ROOT / "app" / "frontend" / "app.js"
        self.assertTrue(app_js_path.exists(), "app.js must exist")
        content = app_js_path.read_text(encoding="utf-8")

        self.assertIn("function inWindow3()", content)
        in_win3_start = content.find("function inWindow3()")
        self.assertNotEqual(in_win3_start, -1)
        in_win3_block = content[in_win3_start:in_win3_start + 300]

        # Must check state.viewMode === "full" or full-view
        self.assertIn('state.viewMode === "full"', in_win3_block)
        # Must NOT treat pdfDocViewer being visible as Window 3
        self.assertNotIn("pdfDocViewer && !els.pdfDocViewer.hidden", in_win3_block)
        # Must NOT treat stage-active unconditionally as Window 3
        self.assertNotIn('classList.contains("stage-active")', in_win3_block)

    def test_no_local_subprocess_shadowing_in_server_py(self):
        """Verify server.py does NOT shadow module-level subprocess inside do_POST."""
        server_py = REPO_ROOT / "app" / "backend" / "server.py"
        self.assertTrue(server_py.exists(), "server.py must exist")
        content = server_py.read_text(encoding="utf-8")

        # Find do_POST method
        do_post_start = content.find("def do_POST(")
        self.assertNotEqual(do_post_start, -1)
        do_post_end = content.find("class SingleInstanceHTTPServer", do_post_start)
        self.assertNotEqual(do_post_end, -1)
        do_post_body = content[do_post_start:do_post_end]

        # Must NOT contain 'import subprocess' inside do_POST
        self.assertNotIn("import subprocess", do_post_body)

    def test_choose_folder_handler_without_unbound_local_error(self):
        """Verify /api/choose-folder code path can be called on a test server without UnboundLocalError."""
        # Start a temporary server.py on port 8789
        test_port = 8789
        env = os.environ.copy()
        proc = subprocess.Popen(
            [r"C:\Python314\python.exe", str(REPO_ROOT / "app" / "backend" / "server.py"), "--port", str(test_port)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            # Wait for server ready
            ready = False
            for _ in range(30):
                time.sleep(0.2)
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/health", timeout=1) as res:
                        if res.status == 200:
                            ready = True
                            break
                except Exception:
                    pass
            self.assertTrue(ready, "Test server on port 8789 must become ready")

            # Call /api/choose-folder in a separate thread, but cancel dialog by closing window or timeout
            # In automated test without user clicking, we verify the endpoint starts powershell and returns valid JSON on cancellation
            import ctypes
            u32 = ctypes.windll.user32
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
            found_hwnds = []

            def _find_dialog(hwnd, _):
                if u32.IsWindowVisible(hwnd):
                    cls = ctypes.create_unicode_buffer(256)
                    u32.GetClassNameW(hwnd, cls, 256)
                    if cls.value == "#32770":
                        found_hwnds.append(hwnd)
                return True

            import threading
            api_result = {}

            def _call():
                try:
                    req = urllib.request.Request(
                        f"http://127.0.0.1:{test_port}/api/choose-folder",
                        data=b"{}",
                        headers={"Content-Type": "application/json", "Accept": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        api_result["status"] = resp.status
                        api_result["body"] = json.loads(resp.read().decode("utf-8"))
                except Exception as ex:
                    api_result["error"] = str(ex)

            th = threading.Thread(target=_call)
            th.start()

            # Wait for dialog and close it
            t0 = time.time()
            dlg_found = False
            while time.time() - t0 < 6:
                del found_hwnds[:]
                u32.EnumWindows(EnumWindowsProc(_find_dialog), 0)
                if found_hwnds:
                    dlg_found = True
                    # Send WM_CLOSE to simulate user canceling the dialog
                    u32.PostMessageW(found_hwnds[0], 0x0010, 0, 0)
                    break
                time.sleep(0.2)

            th.join(timeout=10)

            # Check that the server did NOT crash with UnboundLocalError
            self.assertEqual(api_result.get("status"), 200)
            body = api_result.get("body", {})
            self.assertIn("path", body)
            # Empty path because user cancelled
            self.assertEqual(body.get("path"), "")
            self.assertTrue(dlg_found, "System FolderBrowserDialog must have appeared on screen")

        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=3)
            except Exception:
                proc.kill()

    def test_object_import_flow(self):
        """Verify POST /api/objects/import on an object directory succeeds and registers object."""
        test_folder = REPO_ROOT / "runtime" / "manifests"
        self.assertTrue(test_folder.exists())

        test_port = 8789
        proc = subprocess.Popen(
            [r"C:\Python314\python.exe", str(REPO_ROOT / "app" / "backend" / "server.py"), "--port", str(test_port)],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            ready = False
            for _ in range(30):
                time.sleep(0.2)
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/health", timeout=1) as res:
                        if res.status == 200:
                            ready = True
                            break
                except Exception:
                    pass
            self.assertTrue(ready)

            # Import
            req_data = json.dumps({"path": str(test_folder.resolve())}).encode("utf-8")
            req = urllib.request.Request(
                f"http://127.0.0.1:{test_port}/api/objects/import",
                data=req_data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                data = json.loads(resp.read().decode("utf-8"))
                self.assertIn("id", data)
                self.assertEqual(data.get("name"), "manifests")

            # Check /api/objects
            with urllib.request.urlopen(f"http://127.0.0.1:{test_port}/api/objects", timeout=10) as resp:
                self.assertEqual(resp.status, 200)
                objs = json.loads(resp.read().decode("utf-8")).get("items", [])
                self.assertTrue(any(o.get("id") == data["id"] for o in objs))
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=3)
            except Exception:
                proc.kill()


if __name__ == "__main__":
    unittest.main()
