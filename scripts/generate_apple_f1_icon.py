"""
Генератор официальной иконки FERO Launcher в стиле Formula 1 (F1) + Apple Minimalist:
- Динамичный наклон F1 (~15.5 градусов вперед)
- Толщина линий уменьшена в 1.5 раза (с 136px до 88px на 1024px холсте, с 68px до 44px на 512px)
- Плавный аэродинамический переход от вертикального пилона к верхнему крылу (F1 Racetrack Chicane)
- Скоростные скошенные грани перекладин в стиле Формулы-1
- Цветовая палитра: благородный пастельный серый FERO System Gray 5 (#E5E5EA - #F5F5F7)
- Фоновый премиальный суперэллипс Apple Squircle (Deep Matte Graphite #1D1D20)
- Экспорт во все размеры Windows .ico (16, 24, 32, 48, 64, 128, 256)
"""

import math
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "app" / "frontend" / "assets"
LOCALAPPDATA_ASSETS = Path(r"C:\Users\a9379\AppData\Local\FEngineering_Launcher\app\frontend\assets")
LOCALAPPDATA_ROOT = Path(r"C:\Users\a9379\AppData\Local\FEngineering_Launcher")
DIST_ASSETS = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\Fero_Launcher_v4\app\frontend\assets")
ARTIFACT_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\brain\cfd227eb-d2c1-48b7-9713-1d1a08c9172b")


def create_f1_apple_icon_1024() -> Image.Image:
    w, h = 1024, 1024
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    # 1. Маска и подложка Apple Squircle
    mask = Image.new("L", (w, h), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([48, 48, 976, 976], radius=228, fill=255)

    # Вертикальный матовый титаново-графитовый градиент Apple (#262629 -> #141416)
    bg_gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / float(h - 1)
        r = int(38 * (1 - t) + 18 * t)
        g = int(38 * (1 - t) + 18 * t)
        b = int(42 * (1 - t) + 20 * t)
        line = Image.new("RGBA", (w, 1), (r, g, b, 255))
        bg_gradient.paste(line, (0, y))

    canvas.paste(bg_gradient, (0, 0), mask)
    draw = ImageDraw.Draw(canvas)

    # Внешняя и внутренняя окантовки суперэллипса
    draw.rounded_rectangle([48, 48, 976, 976], radius=228, outline=(65, 65, 70, 255), width=4)
    draw.rounded_rectangle([52, 52, 972, 972], radius=224, outline=(255, 255, 255, 22), width=3)

    # 2. Построение маски буквы F в стиле Формулы-1
    # Толщина линий: 88px (уменьшена в 1.55 раза по сравнению с исходными 136px)
    stroke = 88
    f_upright = Image.new("L", (w, h), 0)
    f_draw = ImageDraw.Draw(f_upright)

    # Базовые координаты до наклона:
    stem_x = 360
    stem_top_y = 236
    stem_bottom_y = 788
    top_bar_right = 720
    mid_bar_right = 640
    mid_bar_top = 444
    mid_bar_height = 80
    top_bar_height = 88
    chicane_r = 110  # радиус аэродинамического скругления верхнего угла F1

    # Вертикальный ствол (нижняя секция)
    f_draw.rounded_rectangle(
        [stem_x, stem_top_y + chicane_r - 20, stem_x + stroke, stem_bottom_y],
        radius=14,
        fill=255,
    )

    # Верхнее крыло (горизонтальная секция)
    f_draw.rounded_rectangle(
        [stem_x + chicane_r - 20, stem_top_y, top_bar_right, stem_top_y + top_bar_height],
        radius=14,
        fill=255,
    )

    # Аэродинамический закруглённый переход (Chicane Curve в стиле F1)
    # Внешний сектор 90 градусов
    f_draw.pieslice(
        [stem_x, stem_top_y, stem_x + 2 * chicane_r, stem_top_y + 2 * chicane_r],
        180,
        270,
        fill=255,
    )
    # Соединительные прямоугольники для бесшовного монолита
    f_draw.rectangle(
        [stem_x, stem_top_y + chicane_r - 20, stem_x + stroke, stem_top_y + chicane_r],
        fill=255,
    )
    f_draw.rectangle(
        [stem_x + stroke, stem_top_y, stem_x + chicane_r, stem_top_y + stroke],
        fill=255,
    )
    # Вырез внутренней окружности (inner radius = chicane_r - stroke)
    inner_r = chicane_r - stroke
    if inner_r > 0:
        f_draw.ellipse(
            [stem_x + stroke, stem_top_y + stroke, stem_x + stroke + 2 * inner_r, stem_top_y + stroke + 2 * inner_r],
            fill=0,
        )

    # Среднее крыло (Mid wing)
    f_draw.rounded_rectangle(
        [stem_x, mid_bar_top, mid_bar_right, mid_bar_top + mid_bar_height],
        radius=14,
        fill=255,
    )

    # 3. Динамичный наклон F1: 15.5 градусов вперед (Shear Transform)
    # Угол Формулы-1: tan(15.5°) ≈ 0.277
    shear_val = math.tan(math.radians(15.5))
    # Центрируем сдвиг относительно точки Y=512
    # X_src = X_dst + shear_val * (Y_dst - 512) - optical_offset
    optical_x_offset = 26  # компенсация оптического центра тяжести буквы F
    matrix = (1, shear_val, -512 * shear_val - optical_x_offset, 0, 1, 0)
    f_mask_sheared = f_upright.transform(
        (w, h), Image.AFFINE, matrix, resample=Image.Resampling.BICUBIC
    )

    # 4. Градиент заливки буквы F (System Gray 5: #F6F6F9 -> #D4D4DA)
    f_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    f_grad = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y in range(h):
        t = y / float(h - 1)
        r = int(246 * (1 - t) + 212 * t)
        g = int(246 * (1 - t) + 212 * t)
        b = int(250 * (1 - t) + 218 * t)
        line = Image.new("RGBA", (w, 1), (r, g, b, 255))
        f_grad.paste(line, (0, y))

    f_layer.paste(f_grad, (0, 0), f_mask_sheared)

    # 5. Мягкая спортивная тень под буквой для ощущения объема
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow_mask = f_mask_sheared.filter(ImageFilter.GaussianBlur(radius=14))
    shadow_color = Image.new("RGBA", (w, h), (0, 0, 0, 120))
    shadow.paste(shadow_color, (0, 12), shadow_mask)

    canvas.alpha_composite(shadow)
    canvas.alpha_composite(f_layer)

    return canvas


def make_f1_svg_content() -> str:
    # Векторный чистый SVG (512x512)
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- Apple Squircle Background: Deep Matte Graphite #1D1D20 -->
  <rect x="24" y="24" width="464" height="464" rx="114" fill="#1D1D20" stroke="#3A3A3E" stroke-width="3"/>
  <rect x="26" y="26" width="460" height="460" rx="112" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="2"/>
  
  <!-- Formula 1 Stylized Monogram 'F' in System Gray 5 #E5E5EA (15.5 deg lean, 1.5x thinner) -->
  <g fill="#E5E5EA" transform="translate(20, 0) skewX(-15.5)">
    <!-- Aerodynamic Racetrack Top Chicane & Stem -->
    <rect x="174" y="150" width="44" height="244" rx="7"/>
    <rect x="200" y="118" width="160" height="44" rx="7"/>
    <path d="M 174 150 Q 174 118 206 118 L 214 118 L 214 162 L 174 162 Z"/>
    <!-- Aerodynamic Middle Wing -->
    <rect x="174" y="222" width="138" height="40" rx="7"/>
  </g>
</svg>"""


def main():
    print("[*] Генерация иконки F1 + Apple Minimalist (1024x1024 SSAA)...")
    master_1024 = create_f1_apple_icon_1024()

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Растровые PNG
    img_512 = master_1024.resize((512, 512), Image.Resampling.LANCZOS)
    img_256 = master_1024.resize((256, 256), Image.Resampling.LANCZOS)

    png_256_path = ASSETS_DIR / "flauncher.png"
    img_256.save(str(png_256_path), format="PNG")
    img_512.save(str(ASSETS_DIR / "flauncher_512.png"), format="PNG")

    # 2. Векторный SVG
    svg_path = ASSETS_DIR / "flauncher.svg"
    svg_path.write_text(make_f1_svg_content(), encoding="utf-8")

    # 3. Мульти-размерные Windows .ico (16, 24, 32, 48, 64, 128, 256)
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = ASSETS_DIR / "flauncher.ico"
    fero_ico_path = ASSETS_DIR / "fero.ico"
    master_1024.save(str(ico_path), format="ICO", sizes=ico_sizes)
    master_1024.save(str(fero_ico_path), format="ICO", sizes=ico_sizes)

    print(f"[+] Сгенерирован flauncher.ico: {ico_path.stat().st_size} байт")
    print(f"[+] Сгенерирован fero.ico: {fero_ico_path.stat().st_size} байт")
    print(f"[+] Сгенерирован flauncher.png (256x256)")
    print(f"[+] Сгенерирован flauncher.svg")

    # 4. Копирование в локальный профиль Windows
    LOCALAPPDATA_ASSETS.mkdir(parents=True, exist_ok=True)
    for f in [ico_path, fero_ico_path, png_256_path, svg_path]:
        shutil.copy2(f, LOCALAPPDATA_ASSETS / f.name)
    shutil.copy2(fero_ico_path, LOCALAPPDATA_ROOT / "fero.ico")
    shutil.copy2(ico_path, LOCALAPPDATA_ROOT / "flauncher.ico")
    print(f"[+] Скопировано в {LOCALAPPDATA_ASSETS}")

    # 5. Копирование в dist_colleague
    DIST_ASSETS.mkdir(parents=True, exist_ok=True)
    for f in [ico_path, fero_ico_path, png_256_path, svg_path]:
        shutil.copy2(f, DIST_ASSETS / f.name)
    print(f"[+] Скопировано в {DIST_ASSETS}")

    # 6. Копирование превью в директорию артефактов
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    img_256.save(str(ARTIFACT_DIR / "fero_apple_f1_preview.png"), format="PNG")
    print(f"[+] Превью сохранено в артефакты: fero_apple_f1_preview.png")


if __name__ == "__main__":
    main()
