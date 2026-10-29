import sqlite3
import sys
from pathlib import Path
from typing import Optional, List, Dict
import time

if getattr(sys, "frozen", False):
    _REPO_ROOT = Path(sys.executable).resolve().parent
else:
    _p_db = Path(__file__).resolve()
    _REPO_ROOT = Path(*_p_db.parts[: _p_db.parts.index("_internal")]) if "_internal" in _p_db.parts else _p_db.parents[2]

RUNTIME_DIR = _REPO_ROOT / "runtime" 
DB_DIR = RUNTIME_DIR / "db"
DB_PATH = DB_DIR / "launcher.sqlite"

def get_connection() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        return conn
    except sqlite3.OperationalError as e:
        if "disk I/O error" in str(e):
            shm = DB_DIR / "launcher.sqlite-shm"
            if shm.exists():
                try:
                    shm.unlink()
                except Exception:
                    pass
            conn = sqlite3.connect(DB_PATH, timeout=5.0)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            conn.execute("PRAGMA busy_timeout=5000;")
            return conn
        raise

def init_db():
    conn = get_connection()
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS roots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            root_id INTEGER NOT NULL,
            rel_path TEXT NOT NULL,
            name TEXT NOT NULL,
            ext TEXT NOT NULL,
            size INTEGER NOT NULL,
            mtime_ns INTEGER NOT NULL,
            observed_revision INTEGER NOT NULL DEFAULT 1,
            hash_state TEXT NOT NULL DEFAULT 'pending',
            verified_content_hash TEXT,
            FOREIGN KEY (root_id) REFERENCES roots(id) ON DELETE CASCADE,
            UNIQUE (root_id, rel_path)
        );

        CREATE TABLE IF NOT EXISTS artifacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            data TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            UNIQUE (document_id, type)
        );

        -- STEP 3: Analytics and Commercial Proposals
        
        CREATE TABLE IF NOT EXISTS parsed_elements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            source_hash TEXT NOT NULL, 
            page_number INTEGER,
            element_type TEXT NOT NULL,
            area_m2 REAL,
            perimeter_m REAL,
            count INTEGER,
            metadata TEXT,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS unit_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            work_category TEXT NOT NULL,
            material_name TEXT NOT NULL,
            unit_type TEXT NOT NULL,
            price_per_unit REAL NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS specifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS specification_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            specification_id INTEGER NOT NULL,
            parsed_element_id INTEGER NOT NULL,
            unit_rate_id INTEGER NOT NULL,
            FOREIGN KEY (specification_id) REFERENCES specifications(id) ON DELETE CASCADE,
            FOREIGN KEY (parsed_element_id) REFERENCES parsed_elements(id),
            FOREIGN KEY (unit_rate_id) REFERENCES unit_rates(id)
        );

        CREATE TABLE IF NOT EXISTS estimates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            total_price REAL NOT NULL DEFAULT 0.0,
            status TEXT NOT NULL DEFAULT 'draft',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS estimate_rows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            estimate_id INTEGER NOT NULL,
            specification_item_id INTEGER NOT NULL,
            snapshot_price_per_unit REAL NOT NULL,
            snapshot_quantity REAL NOT NULL,
            computed_cost REAL NOT NULL,
            FOREIGN KEY (estimate_id) REFERENCES estimates(id) ON DELETE CASCADE,
            FOREIGN KEY (specification_item_id) REFERENCES specification_items(id)
        );
        """)
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized at", DB_PATH.absolute())

import os

def sync_root_to_db(root: Path):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        
        # Ensure root exists
        cursor.execute("INSERT OR IGNORE INTO roots (path, is_active) VALUES (?, 1)", (str(root.resolve()),))
        cursor.execute("SELECT id FROM roots WHERE path = ?", (str(root.resolve()),))
        root_id = cursor.fetchone()[0]

        # Scan disk and collect existing files
        disk_files = {}
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden/system directories
            dirnames[:] = [d for d in dirnames if d not in {".git", ".svn", "__pycache__", "node_modules", "runtime"}]
            rel_dir = Path(dirpath).relative_to(root)
            
            for file in filenames:
                if file.startswith("~$") or file.startswith(".~"):
                    continue
                file_path = Path(dirpath) / file
                rel_path = str(rel_dir / file).replace("\\", "/")
                if rel_path.startswith("./"):
                    rel_path = rel_path[2:]
                
                try:
                    stat = file_path.stat()
                    disk_files[rel_path] = {
                        "name": file,
                        "ext": file_path.suffix.lstrip(".").upper(),
                        "size": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns
                    }
                except OSError:
                    disk_files[rel_path] = {"name": file, "ext": file_path.suffix.lstrip(".").upper(), "size": 0, "mtime_ns": 0}
        
        # Fetch existing DB files
        cursor.execute("SELECT id, rel_path, size, mtime_ns FROM documents WHERE root_id = ?", (root_id,))
        db_files = {row["rel_path"]: row for row in cursor.fetchall()}
        
        # Determine inserts, updates, deletes
        to_insert = []
        to_update = []
        to_delete_ids = []
        
        for rel_path, disk_stat in disk_files.items():
            if rel_path not in db_files:
                to_insert.append((root_id, rel_path, disk_stat["name"], disk_stat["ext"], disk_stat["size"], disk_stat["mtime_ns"]))
            else:
                db_stat = db_files[rel_path]
                if db_stat["size"] != disk_stat["size"] or db_stat["mtime_ns"] != disk_stat["mtime_ns"]:
                    to_update.append((disk_stat["size"], disk_stat["mtime_ns"], root_id, rel_path))
                    
        for rel_path, db_stat in db_files.items():
            if rel_path not in disk_files:
                to_delete_ids.append((db_stat["id"],))
                
        if to_insert:
            cursor.executemany("INSERT INTO documents (root_id, rel_path, name, ext, size, mtime_ns) VALUES (?, ?, ?, ?, ?, ?)", to_insert)
        if to_update:
            # We increment observed_revision, set hash_state to pending, and RETAIN verified_content_hash.
            cursor.executemany("UPDATE documents SET size = ?, mtime_ns = ?, observed_revision = observed_revision + 1, hash_state = 'pending' WHERE root_id = ? AND rel_path = ?", to_update)
        if to_delete_ids:
            cursor.executemany("DELETE FROM documents WHERE id = ?", to_delete_ids)
            
        conn.commit()
        return root_id
    finally:
        conn.close()

def build_tree_from_db(root: Path, root_id: int):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT rel_path, name, ext, size FROM documents WHERE root_id = ?", (root_id,))
        rows = cursor.fetchall()
        
        root_node = {
            "type": "folder",
            "name": root.name,
            "path": str(root.resolve()),
            "children": {}
        }
        
        file_count = 0
        ext_counts = {}
        
        for row in rows:
            rel_path = row["rel_path"]
            parts = rel_path.split("/")
            
            current_dict = root_node["children"]
            current_abs_path = Path(root)
            
            # Build directory structure
            for i, part in enumerate(parts[:-1]):
                current_abs_path = current_abs_path / part
                if part not in current_dict:
                    current_dict[part] = {
                        "type": "folder",
                        "name": part,
                        "path": str(current_abs_path),
                        "children": {}
                    }
                current_dict = current_dict[part]["children"]
            
            # Insert file
            filename = parts[-1]
            ext = row["ext"]
            file_abs_path = current_abs_path / filename
            current_dict[filename] = {
                "type": "file",
                "name": row["name"],
                "path": str(file_abs_path),
                "extension": ext,
                "size": row["size"]
            }
            
            file_count += 1
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
            
        # Convert children dicts to lists recursively
        def dict_to_list(node):
            if node["type"] == "folder":
                children_list = list(node["children"].values())
                # Sort: folders first, then files alphabetically
                children_list.sort(key=lambda x: (x["type"] == "file", x["name"].lower()))
                node["children"] = children_list
                for child in children_list:
                    dict_to_list(child)
            return node
            
        tree = dict_to_list(root_node)
        
        # Count folders
        folder_count = 0
        stack = [tree]
        while stack:
            n = stack.pop()
            if n["type"] == "folder":
                folder_count += 1
                stack.extend(n["children"])
                
        return tree, ext_counts, folder_count - 1, file_count
    finally:
        conn.close()
