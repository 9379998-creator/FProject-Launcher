import os
import ctypes
import subprocess

def fix_shortcuts():
    repo_root = r"C:\Users\a9379\.gemini\antigravity\scratch\fero-launcher-v4"
    vbs_path = os.path.join(repo_root, "Запуск_Лаунчера.vbs")
    ico_path = os.path.join(repo_root, "app", "frontend", "assets", "flauncher.ico")
    
    ps_cmd = f'''
    $sh = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath('Desktop')
    $programs = [Environment]::GetFolderPath('Programs')
    $startMenu = [Environment]::GetFolderPath('StartMenu')
    
    $targetPath = 'wscript.exe'
    $targetArgs = '"{vbs_path}"'
    
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
                    $sc.WorkingDirectory = '{repo_root}'
                    $sc.Description = "F.E.R.O. Launcher v4"
                    $sc.IconLocation = "{ico_path},0"
                    $sc.Save()
                    Write-Host "  New Target: $($sc.TargetPath) $($sc.Arguments)"
                    Write-Host "  New Icon:   $($sc.IconLocation)"
                }}
            }}
            
            if ($dir -eq $desktop) {{
                $deskLnk = Join-Path $desktop "F-Engineering Launcher.lnk"
                $sc = $sh.CreateShortcut($deskLnk)
                $sc.TargetPath = $targetPath
                $sc.Arguments = $targetArgs
                $sc.WorkingDirectory = '{repo_root}'
                $sc.Description = "F.E.R.O. Launcher v4"
                $sc.IconLocation = "{ico_path},0"
                $sc.Save()
                Write-Host "Ensured primary desktop shortcut: $deskLnk"
            }}
        }}
    }}
    '''
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(res.stdout)
    if res.stderr:
        print("STDERR:", res.stderr)
        
    try:
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        print("Notified Windows shell of icon update.")
    except Exception as e:
        print(f"Error notifying shell: {e}")

if __name__ == "__main__":
    fix_shortcuts()
