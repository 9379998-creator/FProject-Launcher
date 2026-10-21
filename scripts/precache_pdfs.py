#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Утилита пакетного предкэширования PDF-чертежей для F-Engineering Launcher.
Позволяет заранее отрендерить все PDF-файлы любого объекта (включая ЖК МОД на 6,000+ файлов),
чтобы при открытии в Лаунчере всё открывалось мгновенно из дискового кэша.

Использование:
    python scripts/precache_pdfs.py [MANIFEST_ID или путь] [--threads 8] [--dpi 150]
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

try:
    from app.backend.server import (
        MANIFESTS_DIR,
        PDF_CACHE_DIR,
        render_pdf,
    )
except ImportError as err:
    print(f"Ошибка импорта server.py: {err}", file=sys.stderr)
    sys.exit(1)


def format_time(seconds: float) -> str:
    if seconds < 0 or seconds > 86400 * 30:
        return "--:--"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h}ч {m:02d}м {s:02d}с"
    return f"{m}м {s:02d}с"


def extract_pdf_files(node: dict) -> list[str]:
    pdfs = []

    def walk(n: dict):
        if not isinstance(n, dict):
            return
        node_type = n.get("type")
        if node_type == "file":
            ext = str(n.get("extension", "")).upper()
            name = str(n.get("name", ""))
            path = str(n.get("path", ""))
            if ext == "PDF" and not name.startswith("~$") and not name.startswith(".~") and path:
                pdfs.append(path)
        elif node_type == "folder":
            for child in n.get("children", []):
                walk(child)

    walk(node)
    return pdfs


def find_manifest(manifest_arg: str | None) -> Path:
    if manifest_arg:
        arg_path = Path(manifest_arg)
        if arg_path.is_file():
            return arg_path
        candidate = MANIFESTS_DIR / f"{manifest_arg}.json"
        if candidate.is_file():
            return candidate
        candidate2 = MANIFESTS_DIR / manifest_arg
        if candidate2.is_file():
            return candidate2
        print(f"Манифест не найден: {manifest_arg}", file=sys.stderr)
        sys.exit(1)

    mod_manifest = MANIFESTS_DIR / "cc658988e9842904.json"
    if mod_manifest.is_file():
        return mod_manifest

    candidates = sorted(
        [p for p in MANIFESTS_DIR.glob("*.json") if p.name != ".gitkeep"],
        key=lambda p: p.stat().st_size,
        reverse=True,
    )
    if not candidates:
        print("В папке runtime/manifests не найдено ни одного манифеста.", file=sys.stderr)
        sys.exit(1)
    return candidates[0]


def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Пакетный рендеринг и кэширование PDF-чертежей")
    parser.add_argument("manifest", nargs="?", help="ID манифеста или путь к файлу .json")
    parser.add_argument("-t", "--threads", type=int, default=8, help="Количество параллельных потоков (по умолчанию: 8)")
    parser.add_argument("--dpi", type=int, default=150, help="DPI для превью (по умолчанию: 150)")
    parser.add_argument("--all-pages", action="store_true", help="Рендерить все страницы (по умолчанию только первая)")
    parser.add_argument("--limit", type=int, default=0, help="Лимит файлов для обработки (0 = все)")
    args = parser.parse_args()

    manifest_file = find_manifest(args.manifest)
    print(f"Загрузка манифеста: {manifest_file.name} ({manifest_file.stat().st_size / (1024*1024):.1f} МБ)...")
    try:
        data = json.loads(manifest_file.read_text(encoding="utf-8"))
    except Exception as err:
        print(f"Ошибка чтения манифеста: {err}", file=sys.stderr)
        sys.exit(1)

    obj_name = data.get("name") or manifest_file.stem
    tree = data.get("tree", {})
    all_pdfs = extract_pdf_files(tree)

    if args.limit > 0:
        all_pdfs = all_pdfs[:args.limit]

    total = len(all_pdfs)
    mode_str = "все страницы" if args.all_pages else "1-я страница"
    print(f"Объект: {obj_name}")
    print(f"Всего PDF-файлов для обработки: {total}")
    print(f"Потоков: {args.threads} | DPI: {args.dpi} | Режим: {mode_str}")
    print("-" * 75)

    if total == 0:
        print("PDF-файлы не найдены.")
        return

    first_page_only = not args.all_pages
    dpi = args.dpi

    cached_count = 0
    rendered_count = 0
    error_count = 0
    processed = 0

    start_time = time.monotonic()

    def process_file(file_path_str: str) -> tuple[str, bool, int, str | None]:
        p = Path(file_path_str)
        try:
            res = render_pdf(p, dpi=dpi, first_page_only=first_page_only)
            is_hit = bool(res.get("cacheHit"))
            pages = res.get("renderedPages", 1)
            return p.name, is_hit, pages, None
        except Exception as e:
            return p.name, False, 0, str(e)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_file = {executor.submit(process_file, f): f for f in all_pdfs}

        try:
            for future in concurrent.futures.as_completed(future_to_file):
                processed += 1
                name, is_hit, pages, err = future.result()

                if err:
                    error_count += 1
                elif is_hit:
                    cached_count += 1
                else:
                    rendered_count += 1

                elapsed = time.monotonic() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining_sec = (total - processed) / rate if rate > 0 else 0
                pct = (processed / total) * 100

                short_name = name[:25] + ("..." if len(name) > 25 else "")
                status_line = (
                    f"\r[{processed}/{total}] {pct:5.1f}% | "
                    f"Кэш: {cached_count} | Новых: {rendered_count} | Ошибок: {error_count} | "
                    f"Осталось: {format_time(remaining_sec)} | {short_name:<28}"
                )
                sys.stdout.write(status_line[:100])
                sys.stdout.flush()

                if processed % 50 == 0 or processed == total:
                    print(f"\n>>> Прогресс: {processed}/{total} ({pct:.1f}%) | Кэш: {cached_count} | Новых: {rendered_count} | Ошибок: {error_count} | Оставшееся время: {format_time(remaining_sec)}", flush=True)

        except KeyboardInterrupt:
            print("\n\nПрервано пользователем. Все обработанные кэши сохранены на диск.")
            executor.shutdown(wait=False, cancel_futures=True)
            return

    elapsed_total = time.monotonic() - start_time
    print("\n" + "=" * 75)
    print(f"Завершено за {format_time(elapsed_total)}!")
    print(f"Всего обработано: {processed}")
    print(f"Уже было в кэше: {cached_count}")
    print(f"Отрендерено новых: {rendered_count}")
    print(f"Ошибок: {error_count}")
    print(f"Папка кэша: {PDF_CACHE_DIR}")


if __name__ == "__main__":
    main()