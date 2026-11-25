import os
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\FProject-Launcher")
SRC_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\Fero_Launcher_v4")
OUTPUT_DIR = Path(r"C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague")
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"
SFX_MODULE = r"C:\Program Files\7-Zip\7z.sfx"
GDRIVE_DIR = Path(r"G:\Общие диски\022_F-Engineering\01_FERO-Launcher")

print(f"[*] Packaging Fero-Launcher v4.5.0 into single self-extracting EXE...")
print(f"    Source: {SRC_DIR}")

if not SRC_DIR.exists():
    print(f"[-] Source directory {SRC_DIR} not found!")
    exit(1)

# Step 1: Create 7z archive with maximum compression
archive_7z = OUTPUT_DIR / "launcher_payload.7z"
if archive_7z.exists():
    archive_7z.unlink()

print("[*] Creating compressed 7z payload...")
cmd_7z = [
    SEVEN_ZIP,
    "a",
    str(archive_7z),
    f"{SRC_DIR}\\*",
    "-mx=5", # fast/solid compression
    "-mmt=on"
]
res = subprocess.run(cmd_7z, capture_output=True, text=True)
if res.returncode != 0:
    print(f"[-] 7z compression failed: {res.stderr}")
    exit(1)

print(f"[+] 7z payload created: {archive_7z.stat().st_size / (1024*1024):.2f} MB")

# Step 2: Prepare SFX config
# 7-Zip standard SFX config
config_path = OUTPUT_DIR / "sfx_config.txt"
config_content = (
    ";!@Install@!UTF-8!\r\n"
    "Title=\"Fero-Launcher v4.5.0\"\r\n"
    "BeginPrompt=\"Запустить Fero-Launcher? Файлы будут автоматически распакованы и программа откроется.\"\r\n"
    "RunProgram=\"FEngineeringLauncher.exe\"\r\n"
    ";!@InstallEnd@!\r\n"
)
config_path.write_bytes(config_content.encode("utf-8"))

# Step 3: Combine 7z.sfx + config + 7z into final single executable
final_exe = OUTPUT_DIR / "Fero_Launcher_v4.5.0.exe"

with open(final_exe, "wb") as f_out:
    with open(SFX_MODULE, "rb") as f_sfx:
        shutil.copyfileobj(f_sfx, f_out)
    with open(config_path, "rb") as f_cfg:
        shutil.copyfileobj(f_cfg, f_out)
    with open(archive_7z, "rb") as f_payload:
        shutil.copyfileobj(f_payload, f_out)

print(f"[+] SUCCESS! Single-file installer created: {final_exe}")
print(f"    Final Size: {final_exe.stat().st_size / (1024*1024):.2f} MB")

# Also copy unversioned pointer and deploy to Google Drive
unversioned_exe = OUTPUT_DIR / "Fero_Launcher.exe"
shutil.copy2(final_exe, unversioned_exe)

if GDRIVE_DIR.exists():
    print(f"[*] Deploying to Google Drive: {GDRIVE_DIR}...")
    shutil.copy2(final_exe, GDRIVE_DIR / "Fero_Launcher_v4.5.0.exe")
    shutil.copy2(final_exe, GDRIVE_DIR / "Fero_Launcher.exe")
    print(f"[+] Successfully deployed to Google Drive!")
