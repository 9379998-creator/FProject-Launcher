import os
import ctypes
import win32com.client

def set_shortcuts():
    sh = win32com.client.Dispatch("WScript.Shell")
    desktop = os.path.expanduser(r"~\Desktop")
    programs = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu\Programs")
    start_menu = os.path.expanduser(r"~\AppData\Roaming\Microsoft\Windows\Start Menu")
    
    repo_root = r"C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4"
    target_vbs = os.path.join(repo_root, "run_launcher.vbs")
    target_ico = os.path.join(repo_root, "app", "frontend", "assets", "flauncher.ico")
    
    assert os.path.exists(target_vbs), f"VBS missing: {target_vbs}"
    assert os.path.exists(target_ico), f"ICO missing: {target_ico}"
    
    wscript_exe = r"C:\Windows\System32\wscript.exe"
    if not os.path.exists(wscript_exe):
        wscript_exe = "wscript.exe"
        
    for folder in [desktop, programs, start_menu]:
        if not os.path.exists(folder):
            continue
        lnk_path = os.path.join(folder, "F-Engineering Launcher.lnk")
        sc = sh.CreateShortcut(lnk_path)
        sc.TargetPath = wscript_exe
        sc.Arguments = f'"{target_vbs}"'
        sc.WorkingDirectory = repo_root
        sc.Description = "F-Engineering Launcher v4"
        sc.IconLocation = f"{target_ico},0"
        sc.Save()
        
        # Verify readback
        sc_check = sh.CreateShortcut(lnk_path)
        print(f"Configured: {lnk_path}")
        print(f"  TargetPath:       {sc_check.TargetPath}")
        print(f"  Arguments:        {sc_check.Arguments}")
        print(f"  WorkingDirectory: {sc_check.WorkingDirectory}")
        print(f"  IconLocation:     {sc_check.IconLocation}")
        print(f"  File exists:      {os.path.exists(sc_check.Arguments.strip('\"'))}")

    # Notify explorer
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        print("Notified Windows shell (SHChangeNotify).")
    except Exception as e:
        print(f"Shell notify error: {e}")

if __name__ == "__main__":
    set_shortcuts()
