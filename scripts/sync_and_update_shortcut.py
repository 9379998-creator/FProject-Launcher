import os
import shutil
import win32com.client
import ctypes

src_root = r"c:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher"
dst_root = r"C:\Users\a9379\AppData\Local\FEngineering_Launcher"

print(f"Syncing files from {src_root} to {dst_root}...")

# 1. Sync app directory
for sub in ["app", "docs"]:
    src_sub = os.path.join(src_root, sub)
    dst_sub = os.path.join(dst_root, sub)
    if os.path.exists(src_sub):
        print(f"Copying tree {sub}...")
        shutil.copytree(src_sub, dst_sub, dirs_exist_ok=True)

# 2. Sync root script files
for f in ["Запуск_Лаунчера.cmd", "Создать_ярлык_на_Рабочем_столе.cmd", "Создать_ярлыки_в_Пуск_и_на_Рабочий_стол.cmd", "AGENTS.md"]:
    src_f = os.path.join(src_root, f)
    dst_f = os.path.join(dst_root, f)
    if os.path.exists(src_f):
        shutil.copy2(src_f, dst_f)
        print(f"Copied {f}")

# 3. Rename old 61MB binary so it never gets invoked by mistake
old_exe = os.path.join(dst_root, "FEngineeringLauncher.exe")
bak_exe = os.path.join(dst_root, "FEngineeringLauncher_old_nov25.bak")
if os.path.exists(old_exe):
    try:
        if os.path.exists(bak_exe):
            os.remove(bak_exe)
        os.rename(old_exe, bak_exe)
        print("Renamed old FEngineeringLauncher.exe to .bak")
    except Exception as e:
        print(f"Could not rename old exe: {e}")

# 4. Update Desktop and Start Menu shortcuts
desktop = os.path.expanduser(r"~\Desktop")
programs = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")

wsh = win32com.client.Dispatch("WScript.Shell")

pythonw_exe = r"C:\Python314\pythonw.exe"
flauncher_pyw = os.path.join(dst_root, "app", "flauncher.pyw")
ico_path = os.path.join(dst_root, "app", "frontend", "assets", "flauncher.ico")
if not os.path.exists(ico_path):
    ico_path = os.path.join(dst_root, "flauncher.ico")

print(f"Target pythonw: {pythonw_exe} exists={os.path.exists(pythonw_exe)}")
print(f"Target script: {flauncher_pyw} exists={os.path.exists(flauncher_pyw)}")
print(f"Target icon: {ico_path} exists={os.path.exists(ico_path)}")

for folder in [desktop, programs]:
    if not os.path.exists(folder):
        continue
    # Remove any old naming variants
    for old_name in ["F-Engineering Launcher.lnk", "Fero Launcher.lnk", "FProject Launcher.lnk"]:
        old_p = os.path.join(folder, old_name)
        if os.path.exists(old_p):
            try:
                os.remove(old_p)
                print(f"Removed legacy shortcut: {old_p}")
            except Exception:
                pass

    lnk_path = os.path.join(folder, "Fero Project Shell.lnk")
    sc = wsh.CreateShortcut(lnk_path)
    sc.TargetPath = pythonw_exe
    sc.Arguments = f'"{flauncher_pyw}"'
    sc.WorkingDirectory = dst_root
    sc.Description = "Fero Project Shell (FPS)"
    sc.IconLocation = f"{ico_path},0"
    sc.Save()
    print(f"Created/Updated shortcut: {lnk_path}")

try:
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
    print("Notified Windows shell of shortcut changes.")
except Exception as e:
    print(f"Shell notify: {e}")

print("Sync and shortcut update complete!")
