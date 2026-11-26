"""
Unit tests for legacy data migration (Data Continuity & Backward Compatibility).
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from app.backend.migration import (
    get_candidate_legacy_runtime_dirs,
    migrate_database,
    migrate_legacy_data,
    migrate_manifests,
    migrate_native_apps_config,
)


class TestLegacyMigration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_migration_")
        self.root = Path(self.temp_dir)
        self.old_runtime = self.root / "old_runtime"
        self.new_runtime = self.root / "new_runtime"
        self.old_runtime.mkdir(parents=True)
        self.new_runtime.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_migrate_manifests_preserves_existing_and_copies_new(self):
        old_manifests = self.old_runtime / "manifests"
        old_manifests.mkdir(parents=True)
        new_manifests = self.new_runtime / "manifests"
        new_manifests.mkdir(parents=True)

        # Create 2 manifests in old runtime
        m1 = {"id": "obj_1", "name": "Project 1", "rootPath": "C:\\P1", "tree": {"name": "P1"}}
        m2 = {"id": "obj_2", "name": "Project 2", "rootPath": "C:\\P2", "tree": {"name": "P2"}}
        (old_manifests / "obj_1.json").write_text(json.dumps(m1), encoding="utf-8")
        (old_manifests / "obj_2.json").write_text(json.dumps(m2), encoding="utf-8")

        # Create obj_1 in new runtime with different name to test NO-OVERWRITE rule
        m1_new = {"id": "obj_1", "name": "Project 1 Newer", "rootPath": "C:\\P1_new"}
        (new_manifests / "obj_1.json").write_text(json.dumps(m1_new), encoding="utf-8")

        migrated = migrate_manifests([self.old_runtime], new_manifests)

        # Only obj_2 should be copied; obj_1 must NOT be overwritten
        self.assertEqual(migrated, ["obj_2.json"])
        self.assertTrue((new_manifests / "obj_2.json").exists())

        # Verify obj_1 was preserved intact
        content_1 = json.loads((new_manifests / "obj_1.json").read_text(encoding="utf-8"))
        self.assertEqual(content_1["name"], "Project 1 Newer")

        content_2 = json.loads((new_manifests / "obj_2.json").read_text(encoding="utf-8"))
        self.assertEqual(content_2["name"], "Project 2")

    def test_migrate_native_apps_config(self):
        old_apps = self.old_runtime / "native_apps.json"
        cfg_data = {"pdf": {"configuredPath": "C:\\Acrobat.exe"}}
        old_apps.write_text(json.dumps(cfg_data), encoding="utf-8")

        new_apps = self.new_runtime / "native_apps.json"

        # Should copy when new does not exist
        res = migrate_native_apps_config([self.old_runtime], new_apps)
        self.assertTrue(res)
        self.assertTrue(new_apps.exists())
        self.assertEqual(json.loads(new_apps.read_text(encoding="utf-8")), cfg_data)

        # Should not copy when new already exists with valid data
        res2 = migrate_native_apps_config([self.old_runtime], new_apps)
        self.assertFalse(res2)

    def test_migrate_database(self):
        old_db_dir = self.old_runtime / "db"
        old_db_dir.mkdir(parents=True)
        old_db = old_db_dir / "launcher.sqlite"
        old_db.write_bytes(b"SQLITE_TEST_DUMMY_DATA_1234567890")

        new_db = self.new_runtime / "db" / "launcher.sqlite"

        # Should copy when new does not exist
        res = migrate_database([self.old_runtime], new_db)
        self.assertTrue(res)
        self.assertTrue(new_db.exists())
        self.assertEqual(new_db.read_bytes(), b"SQLITE_TEST_DUMMY_DATA_1234567890")

        # Should not copy when new exists
        res2 = migrate_database([self.old_runtime], new_db)
        self.assertFalse(res2)

    def test_migrate_legacy_data_full_flow(self):
        # Set up old runtime with manifests, db, native_apps
        old_m_dir = self.old_runtime / "manifests"
        old_m_dir.mkdir(parents=True)
        (old_m_dir / "item_a.json").write_text(json.dumps({"id": "a", "name": "Item A"}), encoding="utf-8")

        old_apps = self.old_runtime / "native_apps.json"
        old_apps.write_text(json.dumps({"dwg": "acad.exe"}), encoding="utf-8")

        old_db_dir = self.old_runtime / "db"
        old_db_dir.mkdir(parents=True)
        (old_db_dir / "launcher.sqlite").write_bytes(b"DUMMY_DB")

        # Mock candidates function or pass mock
        import app.backend.migration as mig_mod
        orig_get_candidates = mig_mod.get_candidate_legacy_runtime_dirs
        mig_mod.get_candidate_legacy_runtime_dirs = lambda current: [self.old_runtime]

        try:
            report = migrate_legacy_data(self.new_runtime)
            self.assertTrue(report["success"])
            self.assertEqual(report["manifests_count"], 1)
            self.assertTrue(report["native_apps_migrated"])
            self.assertTrue(report["db_migrated"])

            self.assertTrue((self.new_runtime / "manifests" / "item_a.json").exists())
            self.assertTrue((self.new_runtime / "native_apps.json").exists())
            self.assertTrue((self.new_runtime / "db" / "launcher.sqlite").exists())
        finally:
            mig_mod.get_candidate_legacy_runtime_dirs = orig_get_candidates


    def test_real_localappdata_discovery_if_present(self):
        # Verify that candidate detection finds existing user profile if it exists on disk
        candidates = get_candidate_legacy_runtime_dirs(self.new_runtime)
        # If running on this machine where FEngineering_Launcher exists, candidates should not be empty
        localappdata = os.environ.get("LOCALAPPDATA")
        if localappdata and (Path(localappdata) / "FEngineering_Launcher" / "runtime").is_dir():
            self.assertTrue(len(candidates) >= 1)
            report = migrate_legacy_data(self.new_runtime)
            self.assertTrue(report["success"])
            self.assertGreaterEqual(report["manifests_count"], 1)
            self.assertTrue((self.new_runtime / "manifests").is_dir())
            self.assertTrue((self.new_runtime / "db" / "launcher.sqlite").exists())
            self.assertTrue((self.new_runtime / "native_apps.json").exists())


    def test_list_object_summaries_self_healing(self):
        # Test self-healing in server.py list_object_summaries()
        import app.backend.server as srv
        orig_runtime = srv.RUNTIME_DIR
        orig_manifests = srv.MANIFESTS_DIR
        try:
            srv.RUNTIME_DIR = self.new_runtime
            srv.MANIFESTS_DIR = self.new_runtime / "manifests"
            # Ensure manifests dir is initially empty
            shutil.rmtree(srv.MANIFESTS_DIR, ignore_errors=True)
            srv.MANIFESTS_DIR.mkdir(parents=True)

            # Call list_object_summaries() - it should self-heal and pull real manifests
            localappdata = os.environ.get("LOCALAPPDATA")
            if localappdata and (Path(localappdata) / "FEngineering_Launcher" / "runtime").is_dir():
                summaries = srv.list_object_summaries()
                self.assertGreaterEqual(len(summaries), 1)
                first = summaries[0]
                self.assertIn("id", first)
                self.assertIn("name", first)
        finally:
            srv.RUNTIME_DIR = orig_runtime
            srv.MANIFESTS_DIR = orig_manifests


if __name__ == "__main__":
    unittest.main()
