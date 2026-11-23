"""Комплексный стресс-тест практического рендеринга реальных файлов F-Engineering Launcher.

Тестирует 15 реальных файлов (DWG, PDF, XLSX, XLS, DOCX, HTML, JPG, PNG, TXT, CSV, ZIP)
из боевых проектов (13_Попова_38_Стройтрест и Desktop/1) на работающем сервере Launcher (127.0.0.1:8780).

Метрики:
1. Корректность диспетчеризации (Engine & Type)
2. Время первого холодного рендеринга (Cold TTR, ms)
3. Время теплого повторного рендеринга (Warm TTR, ms)
4. Коэффициент ускорения кэша (Speedup Factor S)
5. Целостность сгенерированного контента (Размер байт, MIME-type, DPI)
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from typing import Any

BASE_URL = "http://127.0.0.1:8780"

TEST_FILES = [
    {
        "category": "CAD (DWG с парой)",
        "label": "U2601-002 ОПР (Проект АР, 4.3 МБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\U2601-002 ОПР_2026-04-14.dwg",
        "pair_path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\U2601-002 ОПР_2026-04-14.pdf",
        "expected_type": "dwg",
        "check_300dpi": True,
    },
    {
        "category": "CAD (DWG локальный)",
        "label": "Узел по низу окна (Узел СПК, 1.6 МБ)",
        "path": r"C:\Users\a9379\Desktop\1\Узел по низу окна.dwg",
        "pair_path": r"C:\Users\a9379\Desktop\1\Узел по низу окна.pdf",
        "expected_type": "dwg",
        "check_300dpi": True,
    },
    {
        "category": "CAD (DWG без пары)",
        "label": "Фасад в осях 17-3 (DWG без PDF, 601 КБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\2026-04-21_АР выше 0.000\АР3 - 3 - Фасад в осях 17-3.dwg",
        "pair_path": None,
        "expected_type": "dwg",
        "check_300dpi": False,
    },
    {
        "category": "PDF (Проектный альбом)",
        "label": "U2601-002 ОПР (Векторный АР, 7.3 МБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\U2601-002 ОПР_2026-04-14.pdf",
        "pair_path": None,
        "expected_type": "pdf",
        "check_300dpi": True,
    },
    {
        "category": "PDF (Спецификация СПК)",
        "label": "Larta Glass Спич (Спецификация стекла, 441 КБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\2024_03_26_Larta_Санкт_Петербург_Офис_Спич_В2.pdf",
        "pair_path": None,
        "expected_type": "pdf",
        "check_300dpi": True,
    },
    {
        "category": "Таблица XLSX (Смета ВОР)",
        "label": "ВОР_БЦ_Попова_38_без_цен.xlsx (Ведомость объемов, 31 КБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\ИИ\ВОР_БЦ_Попова_38_без_цен.xlsx",
        "pair_path": None,
        "expected_type": "workbook",
        "check_sheet_html": True,
    },
    {
        "category": "Таблица XLSX (Расчет фасадов)",
        "label": "Расчет стоимости Фасады к. 7.2 СРП_ЛОТ7 (833 КБ)",
        "path": r"C:\Users\a9379\Desktop\1\Новая папка\xls\Приложение №1 Расчет стоимости Фасады к. 7.2 СРП_ЛОТ7 ФИНАЛ (Антигравити).xlsx",
        "pair_path": None,
        "expected_type": "workbook",
        "check_sheet_html": True,
    },
    {
        "category": "Таблица XLS (Бинарный формат)",
        "label": "ОтчетТМЦ.xls (Legacy Excel 97-2003, 1.4 МБ)",
        "path": r"C:\Users\a9379\Desktop\1\ОтчетТМЦ.xls",
        "pair_path": None,
        "expected_type": "workbook",
        "check_sheet_html": True,
    },
    {
        "category": "Документ DOCX (Договор)",
        "label": "Договор выше 0_МСК_БЕЗ СУБПОДРЯД (155 КБ, многостраничный)",
        "path": r"C:\Users\a9379\Desktop\1\Новая папка\doc\Договор выше 0_МСК_БЕЗ СУБПОДРЯД_ИЗМ 28.07.2026.docx",
        "pair_path": None,
        "expected_type": "word_html",
    },
    {
        "category": "Веб-документ HTML (КП)",
        "label": "commercial_proposal_popova_38.html (Инженерное КП, 37 КБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\commercial_proposal_popova_38.html",
        "pair_path": None,
        "expected_type": "html",
    },
    {
        "category": "Графика JPG (Фотофиксация)",
        "label": "DSC_0221.JPG (Фото фасада с камеры, 6.6 МБ)",
        "path": r"C:\Users\a9379\Desktop\1\Новая папка\Архив\DSC_0221.JPG",
        "pair_path": None,
        "expected_type": "photo",
    },
    {
        "category": "Графика PNG (Растр 300 DPI)",
        "label": "compare_300dpi.png (Чертежный растр, 4.5 МБ)",
        "path": r"C:\Users\a9379\Desktop\1\Новая папка\pdf\compare_300dpi.png",
        "pair_path": None,
        "expected_type": "photo",
    },
    {
        "category": "Текст TXT (Инструкция)",
        "label": "Правила работы КО с ИИ.txt (Текстовый регламент, 12 КБ)",
        "path": r"C:\Users\a9379\Desktop\1\Правила работы КО с ИИ.txt",
        "pair_path": None,
        "expected_type": "text",
    },
    {
        "category": "Данные CSV (Таблица бенчмарка)",
        "label": "metrics.csv (Инженерные данные, 6 КБ)",
        "path": r"C:\Users\a9379\Desktop\1\_dwg_png_benchmark\trueview\metrics.csv",
        "pair_path": None,
        "expected_type": "workbook",  # CSV теперь нативно рендерится как таблица через ensure_csv_rendered
        "check_sheet_html": True,
    },
    {
        "category": "Архив ZIP (Нативный формат)",
        "label": "2026-04-21_АР выше 0.000.zip (Архив чертежей, 8.2 МБ)",
        "path": r"G:\Общие диски\007_Коммерческий отдел\ОБЪЕКТЫ 2026\13_Попова_38_Стройтрест\Попова АР\2026-04-21_АР выше 0.000.zip",
        "pair_path": None,
        "expected_type": "native_app",
    },
]


@dataclass
class TestResult:
    category: str
    label: str
    file_size_kb: float
    expected_type: str
    actual_type: str
    cold_ms: float
    warm_ms: float
    speedup: float
    details: str
    status: str  # PASS / WARN / FAIL


def http_post_json(url: str, payload: dict) -> tuple[int, dict, float]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw), elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        err_msg = e.read().decode("utf-8", errors="replace")
        return e.code, {"error": err_msg}, elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return 500, {"error": str(e)}, elapsed_ms


def http_get(url: str) -> tuple[int, bytes, str, float]:
    req = urllib.request.Request(url)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            content = resp.read()
            content_type = resp.headers.get("Content-Type", "")
            return resp.status, content, content_type, elapsed_ms
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return e.code, e.read(), e.headers.get("Content-Type", ""), elapsed_ms
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return 500, str(e).encode(), "", elapsed_ms


def run_benchmark() -> list[TestResult]:
    print("=" * 80)
    print("   КОМПЛЕКСНЫЙ ПРАКТИЧЕСКИЙ БЕНЧМАРК РЕНДЕРИНГА F-ENGINEERING LAUNCHER")
    print("=" * 80)
    print(f"Целевой сервер: {BASE_URL}")
    print(f"Количество реальных файлов: {len(TEST_FILES)}\n")

    results: list[TestResult] = []

    for idx, item in enumerate(TEST_FILES, 1):
        path = item["path"]
        label = item["label"]
        cat = item["category"]
        expected_type = item["expected_type"]

        if not os.path.exists(path):
            print(f"[{idx:02d}/{len(TEST_FILES):02d}] ❌ {label}: файл отсутствует на диске!")
            results.append(
                TestResult(
                    category=cat,
                    label=label,
                    file_size_kb=0,
                    expected_type=expected_type,
                    actual_type="NOT_FOUND",
                    cold_ms=0,
                    warm_ms=0,
                    speedup=0,
                    details="Файл не найден на диске",
                    status="FAIL",
                )
            )
            continue

        file_sz_kb = round(os.path.getsize(path) / 1024.0, 1)

        # 1. Холодный вызов /api/preview
        payload = {"file": path}
        if item.get("pair_path"):
            payload["pdf_path"] = item["pair_path"]

        status_code, res_cold, cold_ms = http_post_json(f"{BASE_URL}/api/preview", payload)

        # 2. Теплый повторный вызов /api/preview
        _, res_warm, warm_ms = http_post_json(f"{BASE_URL}/api/preview", payload)

        speedup = round(cold_ms / max(warm_ms, 0.01), 1)

        actual_type = res_cold.get("type", "UNKNOWN")
        is_type_ok = (
            (actual_type == expected_type)
            or (expected_type == "dwg" and actual_type in ("dwg", "pdf"))
            or (expected_type == "native_app" and actual_type in ("native_app", "unsupported"))
        )

        details_list = []

        # 3. Специальные проверки для типов
        # А) Проверка PDF / DWG пары (150 DPI thumbnail и 300 DPI high-res)
        if item.get("check_300dpi"):
            target_pdf = item["pair_path"] if item.get("pair_path") else path

            # Проверка 150 DPI через POST /api/pdf/page
            st_150, res_150, t_150 = http_post_json(
                f"{BASE_URL}/api/pdf/page",
                {"file": target_pdf, "page": 1, "dpi": 150},
            )

            # Проверка 300 DPI через POST /api/pdf/page
            st_300, res_300, t_300 = http_post_json(
                f"{BASE_URL}/api/pdf/page",
                {"file": target_pdf, "page": 1, "dpi": 300},
            )

            bytes_150 = res_150.get("item", {}).get("bytes", 0)
            bytes_300 = res_300.get("item", {}).get("bytes", 0)

            if st_150 == 200 and st_300 == 200:
                details_list.append(
                    f"150 DPI: {bytes_150//1024} KB ({t_150:.0f} ms) | 300 DPI: {bytes_300//1024} KB ({t_300:.0f} ms)"
                )
            else:
                details_list.append(f"Ошибка DPI рендера: st150={st_150}, st300={st_300}")

        # Б) Проверка XLSX/XLS - извлечение листов и HTML
        if item.get("check_sheet_html") and actual_type == "workbook":
            sheets = res_cold.get("sheets", [])
            sheet_count = len(sheets)
            engine = res_cold.get("engine", "openpyxl")
            # Запрос HTML листа 0 через POST /api/excel/sheet
            st_sh, res_sh, t_sh = http_post_json(
                f"{BASE_URL}/api/excel/sheet",
                {"file": path, "sheetIndex": 0},
            )
            sh_rows = res_sh.get("rows", 0)
            sh_cols = res_sh.get("columns", 0)
            details_list.append(
                f"Вкладок: {sheet_count} ({engine}) | Лист 0: {sh_rows} строк x {sh_cols} колонок ({t_sh:.0f} ms)"
            )

        # В) Проверка DOCX - word_html
        if actual_type == "word_html":
            p_count = res_cold.get("paragraphs", "?")
            t_count = res_cold.get("tables", "?")
            html_url = res_cold.get("url")
            details_list.append(f"Параграфов: {p_count}, Таблиц: {t_count}")

        # Г) Проверка HTML
        if actual_type == "html":
            enc_p = urllib.parse.quote(path)
            url_raw = f"{BASE_URL}/api/file/raw?path={enc_p}"
            st_h, bytes_h, ct_h, t_h = http_get(url_raw)
            details_list.append(f"HTML Payload: {len(bytes_h)//1024} KB, Content-Type: {ct_h}")

        # Д) Проверка Photo
        if actual_type == "photo":
            w = res_cold.get("width", "?")
            h = res_cold.get("height", "?")
            details_list.append(f"Разрешение: {w}x{h} px")

        # Е) Проверка Text
        if actual_type == "text":
            enc = res_cold.get("encoding", "utf-8")
            lines = res_cold.get("lines", "?")
            details_list.append(f"Кодировка: {enc}, Строк: {lines}")

        # Ж) Проверка Native app
        if actual_type == "native_app":
            act = res_cold.get("openAction")
            details_list.append(f"Нативное открытие: {act}")

        status = "PASS" if is_type_ok and status_code == 200 else "FAIL"
        details_str = " | ".join(details_list) if details_list else f"Status: {status_code}"

        result_item = TestResult(
            category=cat,
            label=label,
            file_size_kb=file_sz_kb,
            expected_type=expected_type,
            actual_type=actual_type,
            cold_ms=round(cold_ms, 1),
            warm_ms=round(warm_ms, 1),
            speedup=speedup,
            details=details_str,
            status=status,
        )
        results.append(result_item)

        icon = "✅" if status == "PASS" else "❌"
        print(
            f"[{idx:02d}/{len(TEST_FILES):02d}] {icon} {cat:<24} | {label[:30]:<30} | Cold: {cold_ms:6.1f} ms | Warm: {warm_ms:5.1f} ms | {speedup:4.1f}x | {details_str}"
        )

    print("\n" + "=" * 80)
    total_count = len(results)
    pass_count = sum(1 for r in results if r.status == "PASS")
    avg_cold = sum(r.cold_ms for r in results if r.status == "PASS") / max(pass_count, 1)
    avg_warm = sum(r.warm_ms for r in results if r.status == "PASS") / max(pass_count, 1)

    print(f"ИТОГИ ТЕСТИРОВАНИЯ:")
    print(f"  Успешно пройдено: {pass_count} из {total_count} ({pass_count/total_count*100:.1f}%)")
    print(f"  Среднее время холодного рендеринга (Cold TTR): {avg_cold:.1f} ms")
    print(f"  Среднее время повторного рендеринга (Warm TTR): {avg_warm:.1f} ms")
    print(f"  Средний фактор ускорения кэша: {avg_cold/max(avg_warm, 0.01):.1f}x")
    print("=" * 80)

    # Сохраняем в JSON
    report_path = os.path.join(os.path.dirname(__file__), "..", "runtime", "logs", "practical_test_report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print(f"Полный JSON-отчет сохранен: {os.path.abspath(report_path)}")

    return results


if __name__ == "__main__":
    run_benchmark()
