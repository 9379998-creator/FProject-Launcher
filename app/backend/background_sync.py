import threading
import time
import hashlib
from pathlib import Path
from app.backend.db import get_connection

def hash_file(path: Path) -> str:
    try:
        stat = path.stat()
        # Для очень больших файлов (>50 МБ) в фоне используем быстрый хэш метаданных, чтобы не вешать диск
        if stat.st_size > 50 * 1024 * 1024:
            raw = f"{path.name}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
            return hashlib.blake2b(raw).hexdigest()
        hasher = hashlib.blake2b()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except OSError:
        return ""

def background_hashing_worker():
    conn = get_connection()
    
    # On startup, recover any tasks stuck in 'running'
    conn.execute("UPDATE documents SET hash_state = 'pending' WHERE hash_state = 'running'")
    conn.commit()

    while True:
        try:
            cursor = conn.cursor()
            
            # Fetch pending docs (небольшими порциями)
            cursor.execute("""
                SELECT d.id, d.rel_path, r.path as root_path, d.observed_revision, d.verified_content_hash
                FROM documents d
                JOIN roots r ON d.root_id = r.id
                WHERE d.hash_state = 'pending'
                LIMIT 5
            """)
            docs = cursor.fetchall()
            
            if not docs:
                time.sleep(5.0)
                continue
                
            time.sleep(0.2) # Щадящая задержка между пачками для экономии диска
                
            for doc in docs:
                doc_id = doc["id"]
                full_path = Path(doc["root_path"]) / doc["rel_path"]
                observed_revision = doc["observed_revision"]
                old_hash = doc["verified_content_hash"]
                
                # Mark as running
                cursor.execute("UPDATE documents SET hash_state = 'running' WHERE id = ? AND observed_revision = ?", (doc_id, observed_revision))
                conn.commit()
                
                if cursor.rowcount == 0:
                    continue # Revision changed before we even started!
                    
                # Compute hash OUTSIDE of write transaction
                new_hash = hash_file(full_path)
                
                if not new_hash:
                    # Error reading file
                    cursor.execute("UPDATE documents SET hash_state = 'error' WHERE id = ? AND observed_revision = ?", (doc_id, observed_revision))
                    conn.commit()
                    continue
                    
                # Commit new hash ONLY if revision is still the same!
                # Short transaction to update state and artifacts
                cursor.execute("BEGIN IMMEDIATE")
                
                cursor.execute("SELECT observed_revision FROM documents WHERE id = ?", (doc_id,))
                row = cursor.fetchone()
                if not row or row["observed_revision"] != observed_revision:
                    # Revision changed while we were hashing! Discard result.
                    conn.commit()
                    continue
                
                if new_hash == old_hash:
                    # Content didn't change! Just mark ready.
                    cursor.execute("UPDATE documents SET hash_state = 'ready' WHERE id = ?", (doc_id,))
                else:
                    # Content changed! Mark old artifacts as stale
                    cursor.execute("UPDATE artifacts SET status = 'stale' WHERE document_id = ?", (doc_id,))
                    # Save new hash
                    cursor.execute("UPDATE documents SET hash_state = 'ready', verified_content_hash = ? WHERE id = ?", (new_hash, doc_id))
                    
                conn.commit()
                
        except Exception as e:
            print(f"Background hashing error: {e}")
            conn.rollback()
            time.sleep(5)
            
def start_background_sync():
    thread = threading.Thread(target=background_hashing_worker, daemon=True)
    thread.start()
