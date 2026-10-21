import subprocess

script = """
$sh = New-Object -ComObject WScript.Shell
$d = [Environment]::GetFolderPath('Desktop')
Get-ChildItem $d -Filter '*.lnk' | ForEach-Object {
    $sc = $sh.CreateShortcut($_.FullName)
    Write-Host "FILE: $($_.Name)"
    Write-Host "  TARGET: $($sc.TargetPath)"
    Write-Host "  ARGS:   $($sc.Arguments)"
    Write-Host "  DIR:    $($sc.WorkingDirectory)"
    Write-Host "  ICON:   $($sc.IconLocation)"
}
"""
p = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(p.stdout)
if p.stderr:
    print("STDERR:", p.stderr)
