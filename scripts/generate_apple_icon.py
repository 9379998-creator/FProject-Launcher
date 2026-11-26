"""
Скрипт генерации официальной иконки FERO в стиле Apple Minimalist:
- Благородный глубокий матовый графит (Deep Matte Graphite #1D1D1F / #161618)
- Премиальный суперэллипс Apple (Squircle) с hairline-окантовкой
- Монограмма 'F' в пастельном платиново-сером тоне System Gray 5 (#E5E5EA / #F5F5F7)
- Генерация многослойного Windows .ico (16x16, 24x24, 32x32, 48x48, 64x64, 128x128, 256x256)
- Генерация мастер-PNG и SVG
"""

import io
import os
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "app" / "frontend" / "assets"

SVG_CONTENT = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <defs>
    <!-- Премиальный фоновый градиент Apple Dark Titanium / Deep Graphite -->
    <linearGradient id="appleBg" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#242427" />
      <stop offset="100%" stop-color="#151517" />
    </linearGradient>

    <!-- Благородный пастельный тон System Gray 5 / Platinum для буквы F -->
    <linearGradient id="appleF" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="#F7F7FA" />
      <stop offset="100%" stop-color="#DCDCE2" />
    </linearGradient>

    <!-- Деликатная тень под буквой для ощущения глубины -->
    <filter id="softDepth" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="6" stdDeviation="10" flood-color="#000000" flood-opacity="0.45" />
    </filter>
  </defs>

  <!-- Внешний контур: Apple Squircle (суперэллипс) -->
  <rect x="28" y="28" width="456" height="456" rx="112" ry="112" fill="url(#appleBg)" stroke="#38383C" stroke-width="3" />
  
  <!-- Внутренняя ультратонкая hairline фаска (Apple Chamfer Highlight) -->
  <rect x="30" y="30" width="452" height="452" rx="110" ry="110" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="2" />

  <!-- Архитектурная английская монограмма 'F' в сером цвете FERO -->
  <g filter="url(#softDepth)" fill="url(#appleF)">
    <!-- Вертикальный пилон (ствол) -->
    <rect x="166" y="124" width="64" height="264" rx="8" />
    <!-- Верхняя полка -->
    <rect x="166" y="124" width="188" height="60" rx="8" />
    <!-- Средняя полка -->
    <rect x="166" y="228" width="152" height="56" rx="8" />
  </g>
</svg>"""

def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    svg_path = ASSETS_DIR / "flauncher.svg"
    png_path = ASSETS_DIR / "flauncher.png"
    ico_path = ASSETS_DIR / "flauncher.ico"

    print(f"[*] Запись SVG: {svg_path}")
    svg_path.write_text(SVG_CONTENT, encoding="utf-8")

    # Рендеринг в высоком разрешении через PyMuPDF
    print("[*] Рендеринг master PNG 512x512 через PyMuPDF...")
    doc = fitz.open(stream=SVG_CONTENT.encode("utf-8"), filetype="svg")
    # 512x512 при 72 DPI базового размера SVG
    pix = doc[0].get_pixmap(dpi=144)  # 512x512
    master_png = ASSETS_DIR / "flauncher_512.png"
    pix.save(str(master_png))

    img = Image.open(str(master_png))
    # Сохраняем стандартный flauncher.png (256x256)
    img_256 = img.resize((256, 256), Image.Resampling.LANCZOS)
    img_256.save(str(png_path), format="PNG")
    print(f"[+] Сохранен PNG: {png_path}")

    # Создание многослойного Windows .ico со всеми стандартными размерами
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    print(f"[*] Сборка мульти-размерного Windows .ico: {ico_sizes}...")
    img.save(str(ico_path), format="ICO", sizes=ico_sizes)
    print(f"[+] Успешно сгенерирован .ico: {ico_path} (Размер: {ico_path.stat().st_size} байт)")

if __name__ == "__main__":
    main()
