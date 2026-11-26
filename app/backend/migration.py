"""
Модуль бесшовной миграции данных предыдущих версий (Data Continuity & Migration).
Обеспечивает преемственность пользовательских данных при обновлении или переносе лаунчера:
- Манифесты ранее загруженных объектов (runtime/manifests/*.json)
- Настройки привязки приложений (runtime/native_apps.json)
- База данных метаданных и кэша документов (runtime/db/launcher.sqlite)
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger("flauncher.migration")

# Имена папок предыдущих версий лаунчера в %LOCALAPPDATA% и %APPDATA%
LEGACY_DIR_NAMES = [
    "FEngineering_Launcher",
    "F-Engineering Launcher",
    "FEngineeringLauncher",
    "FEngineering_Platform",
    "FEngineeringPlatform",
    "Fero_Launcher",
]


def get_candidate_legacy_runtime_dirs(current_runtime_dir: Path | None = None) -> list[Path]:
    """Возвращает список существующих директорий runtime от предыдущих установок лаунчера.

    Исключает текущую рабочую директорию runtime, чтобы предотвратить циклическое копирование.
    """
    resolved_current = current_runtime_dir.resolve() if current_runtime_dir else None
    candidates: list[Path] = []
    seen: set[str] = set()

    def _add_candidate(runtime_path: Path):
        try:
            res = runtime_path.resolve()
            res_str = str(res).lower()
            if res.is_dir() and res_str not in seen:
                if resolved_current and res == resolved_current:
                    return
                seen.add(res_str)
                candidates.append(res)
        except Exception:
            pass

    # 1. Проверяем переменные окружения профиля Windows
    env_vars = ["LOCALAPPDATA", "APPDATA", "USERPROFILE"]
    for var in env_vars:
        base_str = os.environ.get(var)
        if not base_str:
            continue
        base_path = Path(base_str)
        for name in LEGACY_DIR_NAMES:
            # Вариант 1: <base>/<name>/runtime
            _add_candidate(base_path / name / "runtime")
            # Вариант 2: <base>/<name> (если сам корень использовался как runtime)
            manifests_check = base_path / name / "manifests"
            if manifests_check.is_dir():
                _add_candidate(base_path / name)

    # 2. Проверяем известные пути рабочих копий репозитория в документах пользователя
    user_home = Path.home()
    dev_paths = [
        user_home / "Documents" / "Codex" / "FEngineering_Launcher_v3_CURRENT_COPY" / "runtime",
        user_home / "Documents" / "Codex" / "F.E.R.O.-Launcher" / "runtime",
        user_home / "Documents" / "Codex" / "f-engineering-launcher" / "runtime",
        Path(r"G:\Общие диски\021_F-Engineering_Knowledge_Library\04_FERO_Launcher\runtime"),
        Path(r"G:\Общие диски\022_F-Engineering\01_FERO-Launcher\runtime"),
    ]
    for dev_p in dev_paths:
        _add_candidate(dev_p)

    return candidates


def migrate_manifests(candidates: list[Path], target_manifests_dir: Path) -> list[str]:
    """Копирует отсутствующие манифесты объектов из устаревших директорий в целевую.

    Не перезаписывает существующие манифесты в target_manifests_dir (Zero Breakage).
    """
    target_manifests_dir.mkdir(parents=True, exist_ok=True)
    migrated_names: list[str] = []

    for cand in candidates:
        cand_manifests = cand / "manifests" if (cand / "manifests").is_dir() else cand
        if not cand_manifests.is_dir():
            continue

        for src_file in cand_manifests.glob("*.json"):
            dst_file = target_manifests_dir / src_file.name
            if dst_file.exists():
                continue

            try:
                # Валидируем, что это действительно корректный манифест проекта
                raw = src_file.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict) and ("id" in data or "rootPath" in data or "tree" in data):
                    shutil.copy2(src_file, dst_file)
                    migrated_names.append(src_file.name)
                    logger.info("Migrated manifest: %s from %s", src_file.name, cand)
            except Exception as err:
                logger.warning("Could not migrate manifest %s: %s", src_file, err)

    return migrated_names


def migrate_native_apps_config(candidates: list[Path], target_apps_file: Path) -> bool:
    """Копирует настройки привязки программ, если в целевом runtime они отсутствуют."""
    if target_apps_file.exists() and target_apps_file.stat().st_size > 10:
        return False

    for cand in candidates:
        cand_apps = cand / "native_apps.json"
        if cand_apps.is_file() and cand_apps.stat().st_size > 10:
            try:
                target_apps_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand_apps, target_apps_file)
                logger.info("Migrated native_apps.json from %s", cand)
                return True
            except Exception as err:
                logger.warning("Could not migrate native_apps.json: %s", err)
    return False


def migrate_database(candidates: list[Path], target_db_file: Path) -> bool:
    """Копирует базу данных launcher.sqlite, если в целевом runtime она отсутствует."""
    if target_db_file.exists() and target_db_file.stat().st_size > 0:
        return False

    for cand in candidates:
        cand_db = cand / "db" / "launcher.sqlite"
        if cand_db.is_file() and cand_db.stat().st_size > 0:
            try:
                target_db_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand_db, target_db_file)
                # Копируем также файлы журнала WAL и SHM при наличии
                for ext in ["-wal", "-shm"]:
                    extra_src = cand / "db" / f"launcher.sqlite{ext}"
                    extra_dst = target_db_file.parent / f"launcher.sqlite{ext}"
                    if extra_src.is_file():
                        shutil.copy2(extra_src, extra_dst)
                logger.info("Migrated launcher.sqlite database from %s", cand)
                return True
            except Exception as err:
                logger.warning("Could not migrate database: %s", err)
    return False


def migrate_legacy_data(target_runtime_dir: Path | None = None) -> dict[str, Any]:
    """Выполняет полную автоматическую миграцию пользовательских данных.

    Возвращает отчет об объемах перенесенных данных.
    """
    if target_runtime_dir is None:
        from app.backend.server import RUNTIME_DIR
        target_runtime_dir = RUNTIME_DIR

    target_runtime_dir = Path(target_runtime_dir)
    target_manifests = target_runtime_dir / "manifests"
    target_apps = target_runtime_dir / "native_apps.json"
    target_db = target_runtime_dir / "db" / "launcher.sqlite"

    candidates = get_candidate_legacy_runtime_dirs(target_runtime_dir)
    if not candidates:
        return {
            "success": True,
            "candidates_found": 0,
            "manifests_count": 0,
            "native_apps_migrated": False,
            "db_migrated": False,
        }

    migrated_manifests = migrate_manifests(candidates, target_manifests)
    migrated_apps = migrate_native_apps_config(candidates, target_apps)
    migrated_db = migrate_database(candidates, target_db)

    return {
        "success": True,
        "candidates_found": len(candidates),
        "candidates": [str(c) for c in candidates],
        "manifests_count": len(migrated_manifests),
        "migrated_manifests": migrated_manifests,
        "native_apps_migrated": migrated_apps,
        "db_migrated": migrated_db,
    }
