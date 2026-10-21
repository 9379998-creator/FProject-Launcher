"""Tests for file counting consistency, directory traversal, and extension mapping.

Verifies:
1. Empty folders, folder-only trees, mixed-extension structures.
2. Case-insensitivity (.pdf, .PDF, .Pdf -> "PDF").
3. Files with identical names in different subdirectories.
4. Folder named 'something.pdf' is not counted as a PDF file.
5. Directory symlink / junction loop does not break or abort the scan (continues properly).
6. Manifest file count, folder count, and extension breakdown match the disk exactly.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.backend.server import build_tree, file_extension


class TestFileCountConsistency(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_file_extension_normalization(self):
        self.assertEqual(file_extension(Path("document.pdf")), "PDF")
        self.assertEqual(file_extension(Path("drawing.DWG")), "DWG")
        self.assertEqual(file_extension(Path("table.Xlsx")), "XLSX")
        self.assertEqual(file_extension(Path("archive.tar.gz")), "GZ")
        self.assertEqual(file_extension(Path("no_extension")), "NO_EXT")

    def test_empty_folder(self):
        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(file_count, 0)
        self.assertEqual(folder_count, 1)
        self.assertEqual(counts, {})
        self.assertEqual(tree["children"], [])

    def test_folders_without_files(self):
        (self.root / "sub1" / "nested").mkdir(parents=True)
        (self.root / "sub2").mkdir()

        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(file_count, 0)
        self.assertEqual(folder_count, 4)  # root, sub1, sub1/nested, sub2
        self.assertEqual(counts, {})

    def test_mixed_extensions_and_casing(self):
        sub_a = self.root / "Section_A"
        sub_b = self.root / "Section_B"
        sub_a.mkdir()
        sub_b.mkdir()

        (sub_a / "sheet1.pdf").write_bytes(b"content")
        (sub_a / "sheet2.PDF").write_bytes(b"content")
        (sub_a / "plan.dwg").write_bytes(b"content")
        (sub_b / "calc.xlsx").write_bytes(b"content")
        (sub_b / "calc2.XLSX").write_bytes(b"content")
        (sub_b / "notes.txt").write_bytes(b"content")

        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(file_count, 6)
        self.assertEqual(folder_count, 3)
        self.assertEqual(counts.get("PDF"), 2)
        self.assertEqual(counts.get("DWG"), 1)
        self.assertEqual(counts.get("XLSX"), 2)
        self.assertEqual(counts.get("TXT"), 1)

    def test_folder_named_like_extension_not_counted_as_file(self):
        # A directory named "project.pdf" must NOT be treated as a PDF file
        fake_pdf_dir = self.root / "project.pdf"
        fake_pdf_dir.mkdir()
        (fake_pdf_dir / "real_file.dwg").write_bytes(b"content")

        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(counts.get("PDF", 0), 0)
        self.assertEqual(counts.get("DWG"), 1)
        self.assertEqual(file_count, 1)
        self.assertEqual(folder_count, 2)

    def test_identical_file_names_in_different_folders(self):
        # Files with identical names in different directories must each be counted
        dir1 = self.root / "Dir1"
        dir2 = self.root / "Dir2"
        dir1.mkdir()
        dir2.mkdir()

        (dir1 / "specification.pdf").write_bytes(b"pdf1")
        (dir2 / "specification.pdf").write_bytes(b"pdf2")

        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(file_count, 2)
        self.assertEqual(counts.get("PDF"), 2)

    def test_symlink_or_junction_cycle_does_not_abort_scan(self):
        # If there is a junction or symlink loop, build_tree must skip the loop and CONTINUE
        # processing other sibling directories without early returning.
        dir1 = self.root / "Regular1"
        dir2 = self.root / "Regular2"
        dir1.mkdir()
        dir2.mkdir()
        (dir1 / "file1.pdf").write_bytes(b"pdf1")
        (dir2 / "file2.pdf").write_bytes(b"pdf2")

        # Create a loop if symlinks are permitted on this OS / environment
        loop_link = dir1 / "loop_back"
        try:
            loop_link.symlink_to(self.root, target_is_directory=True)
            has_symlink = True
        except (OSError, NotImplementedError):
            has_symlink = False

        tree, counts, folder_count, file_count = build_tree(self.root)

        # In all cases, file1 and file2 must be scanned and counts["PDF"] == 2
        self.assertEqual(counts.get("PDF"), 2)
        self.assertEqual(file_count, 2)

    def test_tree_structure_contains_all_files(self):
        # Verify that all leaf file nodes in tree match disk files 1-to-1
        for i in range(10):
            folder = self.root / f"Folder_{i}"
            folder.mkdir()
            for j in range(5):
                (folder / f"doc_{j}.pdf").write_bytes(b"pdf")

        tree, counts, folder_count, file_count = build_tree(self.root)
        self.assertEqual(file_count, 50)
        self.assertEqual(counts.get("PDF"), 50)
        self.assertEqual(folder_count, 11)

        # Collect all file paths from tree
        tree_files = set()
        stack = [tree]
        while stack:
            curr = stack.pop()
            if curr.get("type") == "file":
                tree_files.add(curr["path"])
            for child in curr.get("children", []):
                stack.append(child)

        self.assertEqual(len(tree_files), 50)


if __name__ == "__main__":
    unittest.main()
