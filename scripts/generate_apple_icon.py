"""
Генерация идеальной иконки FERO Apple Minimalist:
- 1024x1024 Super-Sampled Anti-Aliasing (SSAA) с даунсэмплингом Lanczos
- Благородный глубокий графит (#1C1C1E - #141416)
- Суперэллипс Apple Squircle с hairline-окантовкой
- Монограмма 'F' в пастельном платиново-сером тоне System Gray 5 (#E5E5EA)
- Экспорт во все размеры Windows ICO (16, 24, 32, 48, 64, 128, 256)
- Экспорт в PNG и чистый SVG (без градиентных багов)
"""

import os
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = REPO_ROOT / "app" / "frontend" / "assets"
LOCALAPPDATA_ASSETS = Path(r"C:\Users\a9379\AppData\Local\FEngineering_Launcher\app\frontend\assets")
LOCALAPPDATA_ROOT = Path(r"C:\Users\a9379\AppData\Local\FEngineering_Launcher")
DIST_ASSETS = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\Fero_Launcher_v4\app\frontend\assets")
ARTIFACT_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\brain\cfd227eb-d2c1-48b7-9713-1d1a08c9172b")

def create_apple_icon_1024() -> Image.Image:
    # 1024x1024 RGBA холст
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    
    # 1. Маска суперэллипса Apple Squircle
    mask = Image.new("L", (1024, 1024), 0)
    mask_draw = ImageDraw.Draw(mask)
    # Координаты с отступом 48px
    mask_draw.rounded_rectangle([48, 48, 976, 976], radius=228, fill=255)
    
    # 2. Фоновый вертикальный титаново-графитовый градиент Apple (#262629 вверху -> #141416 внизу)
    bg_gradient = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    for y in range(1024):
        t = y / 1023.0
        r = int(38 * (1 - t) + 20 * t)
        g = int(38 * (1 - t) + 20 * t)
        b = int(42 * (1 - t) + 22 * t)
        line = Image.new("RGBA", (1024, 1), (r, g, b, 255))
        bg_gradient.paste(line, (0, y))
    
    # Накладываем маску
    canvas.paste(bg_gradient, (0, 0), mask)
    draw = ImageDraw.Draw(canvas)
    
    # 3. Деликатная внешняя окантовка (hairline border)
    draw.rounded_rectangle([48, 48, 976, 976], radius=228, outline=(65, 65, 70, 255), width=4)
    # Внутренняя легкая фаска (Apple Chamfer Highlight)
    draw.rounded_rectangle([52, 52, 972, 972], radius=224, outline=(255, 255, 255, 22), width=3)
    
    # 4. Монограмма 'F' в стиле Apple
    # Создаем отдельный слой для буквы F с тенью
    f_layer = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    f_mask = Image.new("L", (1024, 1024), 0)
    f_mask_draw = ImageDraw.Draw(f_mask)
    
    # Геометрия английской F (пропорции Apple SF Pro)
    # Вертикальный ствол (Stem): X: 328 .. 464 (ширина 136), Y: 240 .. 784 (высота 544)
    f_mask_draw.rounded_rectangle([328, 240, 464, 784], radius=18, fill=255)
    # Верхняя перекладина (Top bar): X: 328 .. 712 (ширина 384), Y: 240 .. 368 (высота 128)
    f_mask_draw.rounded_rectangle([328, 240, 712, 368], radius=18, fill=255)
    # Средняя перекладина (Middle bar): X: 328 .. 640 (ширина 312), Y: 456 .. 576 (высота 120)
    f_mask_draw.rounded_rectangle([328, 456, 640, 576], radius=18, fill=255)
    
    # Градиент буквы F (System Gray 5: #F6F6F9 вверху -> #D6D6DC внизу)
    f_gradient = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    for y in range(1024):
        t = y / 1023.0
        r = int(246 * (1 - t) + 214 * t)
        g = int(246 * (1 - t) + 214 * t)
        b = int(250 * (1 - t) + 220 * t)
        line = Image.new("RGBA", (1024, 1), (r, g, b, 255))
        f_gradient.paste(line, (0, y))
    
    f_layer.paste(f_gradient, (0, 0), f_mask)
    
    # Мягкая тень под буквой F
    shadow = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    shadow_mask = f_mask.copy().filter(ImageFilter.GaussianBlur(radius=16))
    shadow_color = Image.new("RGBA", (1024, 1024), (0, 0, 0, 110))
    # Сдвиг тени вниз на 12px
    shadow.paste(shadow_color, (0, 12), shadow_mask)
    
    # Объединяем холст
    canvas.alpha_composite(shadow)
    canvas.alpha_composite(f_layer)
    
    return canvas

def make_svg_content() -> str:
    # Чистый SVG на 512x512 с solid-цветами (без багов рендеринга в старых движках)
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">
  <!-- Apple Squircle Background: Deep Matte Graphite #1D1D20 -->
  <rect x="24" y="24" width="464" height="464" rx="114" fill="#1D1D20" stroke="#3A3A3E" stroke-width="3"/>
  <rect x="26" y="26" width="460" height="460" rx="112" fill="none" stroke="#FFFFFF" stroke-opacity="0.08" stroke-width="2"/>
  
  <!-- Architectural Apple 'F' Monogram in System Gray 5 #E5E5EA -->
  <g fill="#E5E5EA">
    <!-- Vertical Stem -->
    <rect x="164" y="120" width="68" height="272" rx="9"/>
    <!-- Top Horizontal Bar -->
    <rect x="164" y="120" width="192" height="64" rx="9"/>
    <!-- Middle Horizontal Bar -->
    <rect x="164" y="228" width="156" height="60" rx="9"/>
  </g>
</svg>"""

def main():
    print("[*] Генерация суперсэмплированного мастер-изображения 1024x1024...")
    master_1024 = create_apple_icon_1024()
    
    # Генерируем мастер PNG 512x512
    img_512 = master_1024.resize((512, 512), Image.Resampling.LANCZOS)
    img_256 = master_1024.resize((256, 256), Image.Resampling.LANCZOS)
    
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Сохраняем PNG
    png_256_path = ASSETS_DIR / "flauncher.png"
    img_256.save(str(png_256_path), format="PNG")
    img_512.save(str(ASSETS_DIR / "flauncher_512.png"), format="PNG")
    
    # 2. Сохраняем чистый SVG
    svg_path = ASSETS_DIR / "flauncher.svg"
    svg_path.write_text(make_svg_content(), encoding="utf-8")
    
    # 3. Сохраняем мульти-слойный Windows ICO
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    ico_path = ASSETS_DIR / "flauncher.ico"
    fero_ico_path = ASSETS_DIR / "fero.ico"
    master_1024.save(str(ico_path), format="ICO", sizes=ico_sizes)
    master_1024.save(str(fero_ico_path), format="ICO", sizes=ico_sizes)
    
    print(f"[+] Сгенерирован flauncher.ico: {ico_path.stat().st_size} байт")
    print(f"[+] Сгенерирован fero.ico: {fero_ico_path.stat().st_size} байт")
    print(f"[+] Сгенерирован flauncher.png (256x256)")
    print(f"[+] Сгенерирован flauncher.svg")
    
    # 4. Копируем в рабочую папку AppData
    for f in [ico_path, fero_ico_path, png_256_path, svg_path]:
        shutil.copy2(f, LOCALAPPDATA_ASSETS / f.name)
    shutil.copy2(fero_ico_path, LOCALAPPDATA_ROOT / "fero.ico")
    shutil.copy2(ico_path, LOCALAPPDATA_ROOT / "flauncher.ico")
    print(f"[+] Скопировано в локальный рабочий профиль: {LOCALAPPDATA_ASSETS}")
    
    # 5. Копируем в dist_colleague
    for f in [ico_path, fero_ico_path, png_256_path, svg_path]:
        shutil.copy2(f, DIST_ASSETS / f.name)
    print(f"[+] Скопировано в дистрибутив: {DIST_ASSETS}")
    
    # 6. Копируем превью в артефакты
    img_256.save(str(ARTIFACT_DIR / "fero_apple_icon_preview.png"), format="PNG")
    print(f"[+] Артефакт превью сохранён")

if __name__ == "__main__":
    main()
