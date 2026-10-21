import os
import sys
import shutil
import ctypes
from PIL import Image

SOURCE_IMG = r"C:\Users\a9379\.gemini\antigravity\brain\3acc4eb7-0c1e-4118-8b72-ab9dd5251e93\.user_uploaded\media_1792129555096_35854596.png"
REPO_ROOT = r"C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4"
ASSETS_DIR = os.path.join(REPO_ROOT, "app", "frontend", "assets")
FRONTEND_DIR = os.path.join(REPO_ROOT, "app", "frontend")
DESKTOP_DIR = os.path.expanduser(r"~\Desktop")

def process_icon():
    print(f"Loading source image: {SOURCE_IMG}")
    img = Image.open(SOURCE_IMG).convert("RGBA")
    w, h = img.size
    print(f"Source size: {w}x{h}")

    # Process transparency
    pixdata = img.load()
    
    # Outer and inner white areas:
    for y in range(h):
        for x in range(w):
            r, g, b, a = pixdata[x, y]
            # Pure white background removal
            if r >= 245 and g >= 245 and b >= 245:
                pixdata[x, y] = (255, 255, 255, 0)
            elif r > 215 and g > 215 and b > 215:
                # Anti-aliasing fringe against white
                whiteness = (r + g + b) / (3.0 * 255.0)
                alpha = max(0, min(255, int((1.0 - whiteness) * 2.5 * 255)))
                pixdata[x, y] = (18, 18, 17, alpha)

    # Crop to bounding box of non-zero alpha
    bbox = img.getbbox()
    print(f"Glyph bounding box: {bbox}")
    cropped = img.crop(bbox)
    cw, ch = cropped.size
    print(f"Cropped glyph dimensions: {cw}x{ch}")

    # Create square canvas 256x256 with margin
    target_canvas_size = 256
    margin = 12
    max_glyph_size = target_canvas_size - (margin * 2) # 232
    
    scale = min(max_glyph_size / cw, max_glyph_size / ch)
    new_cw = int(cw * scale)
    new_ch = int(ch * scale)
    resized_glyph = cropped.resize((new_cw, new_ch), Image.Resampling.LANCZOS)

    # Paste centered on 256x256 transparent canvas
    master_256 = Image.new("RGBA", (target_canvas_size, target_canvas_size), (0, 0, 0, 0))
    paste_x = (target_canvas_size - new_cw) // 2
    paste_y = (target_canvas_size - new_ch) // 2
    master_256.paste(resized_glyph, (paste_x, paste_y), resized_glyph)

    os.makedirs(ASSETS_DIR, exist_ok=True)
    os.makedirs(FRONTEND_DIR, exist_ok=True)

    # Save target assets
    target_ico = os.path.join(ASSETS_DIR, "flauncher.ico")
    target_png = os.path.join(ASSETS_DIR, "flauncher.png")
    target_favicon = os.path.join(FRONTEND_DIR, "favicon.ico")

    # Multi-resolution ICO: 16, 24, 32, 48, 64, 128, 256
    ico_sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    master_256.save(target_ico, format="ICO", sizes=ico_sizes)
    print(f"Saved: {target_ico} ({os.path.getsize(target_ico)} bytes)")

    # PNG 256x256
    master_256.save(target_png, format="PNG")
    print(f"Saved: {target_png} ({os.path.getsize(target_png)} bytes)")

    # Favicon ICO
    fav_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
    master_256.save(target_favicon, format="ICO", sizes=fav_sizes)
    print(f"Saved: {target_favicon} ({os.path.getsize(target_favicon)} bytes)")

    # Delete legacy icon if exists
    legacy_ico = os.path.join(ASSETS_DIR, "flauncher_legacy_260416.ico")
    if os.path.exists(legacy_ico):
        try:
            os.remove(legacy_ico)
            print(f"Removed legacy icon: {legacy_ico}")
        except Exception as e:
            print(f"Error removing {legacy_ico}: {e}")

    update_shortcuts(target_ico)
    refresh_icon_cache()

def update_shortcuts(ico_path):
    print("Updating desktop and start menu shortcuts...")
    import subprocess
    ps_cmd = f'''
    $sh = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $programs = [Environment]::GetFolderPath('Programs')
    $startMenu = [Environment]::GetFolderPath('StartMenu')
    
    $vbs = Join-Path '{REPO_ROOT}' 'Запуск_Нового_Лаунчера.vbs'
    $targetPath = 'wscript.exe'
    $targetArgs = '\"' + $vbs + '\"'
    
    $folders = @($desktop, $programs, $startMenu)
    foreach ($dir in $folders) {{
        if ($dir -and (Test-Path $dir)) {{
            $links = Get-ChildItem -Path $dir -Filter "*.lnk" -ErrorAction SilentlyContinue
            foreach ($lnk in $links) {{
                if ($lnk.Name -like "*F-Engineering*" -or $lnk.Name -like "*FERO*" -or $lnk.Name -like "*launcher*" -or $lnk.Name -like "*лаунчер*") {{
                    Write-Host "Updating shortcut: $($lnk.FullName)"
                    $sc = $sh.CreateShortcut($lnk.FullName)
                    $sc.TargetPath = $targetPath
                    $sc.Arguments = $targetArgs
                    $sc.WorkingDirectory = '{REPO_ROOT}'
                    $sc.IconLocation = "{ico_path},0"
                    $sc.Save()
                    Write-Host "  New Icon: $($sc.IconLocation)"
                }}
            }}
            
            # Ensure primary desktop shortcut exists
            if ($dir -eq $desktop) {{
                $deskLnk = Join-Path $desktop "F-Engineering Launcher.lnk"
                $sc = $sh.CreateShortcut($deskLnk)
                $sc.TargetPath = $targetPath
                $sc.Arguments = $targetArgs
                $sc.WorkingDirectory = '{REPO_ROOT}'
                $sc.Description = "F.E.R.O. Launcher v4"
                $sc.IconLocation = "{ico_path},0"
                $sc.Save()
                Write-Host "Created/Updated primary desktop shortcut: $deskLnk"
            }}
        }}
    }}
    '''
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True)
    print("PowerShell shortcut update stdout:\n", res.stdout)
    if res.stderr:
        print("PowerShell shortcut update stderr:\n", res.stderr)

def refresh_icon_cache():
    print("Notifying Windows Explorer of icon change...")
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        print("SHChangeNotify called successfully.")
    except Exception as e:
        print(f"Error notifying shell: {e}")

if __name__ == "__main__":
    process_icon()
