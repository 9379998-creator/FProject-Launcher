; F-Engineering Launcher v4.4 — Скрипт инсталлятора (Inno Setup 6).
; Инженерное бюро ООО «ФЕРО»
; Кодировка: UTF-8 with BOM

[Setup]
AppName=F-Engineering Launcher
AppVersion=4.4.0
AppPublisher=ООО "ФЕРО"
AppPublisherURL=https://ferospb.info
DefaultDirName={localappdata}\FEngineering_Launcher
DefaultGroupName=F-Engineering Launcher
OutputBaseFilename=FEngineering_Launcher_v4_Setup
OutputDir=..\dist_setup
SetupIconFile=..\app\frontend\assets\flauncher.ico
UninstallDisplayIcon={app}\FEngineeringLauncher.exe
Compression=lzma2/ultra64
SolidCompression=yes

; КРИТИЧНО: без прав администратора! Установка в профиль пользователя исключает ошибки «Отказано в доступе».
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; Полное содержимое автономного дистрибутива
Source: "C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\FEngineering_Launcher_v4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\runtime\cache"
Name: "{app}\runtime\logs"
Name: "{app}\runtime\manifests"
Name: "{app}\runtime\db"

[Icons]
Name: "{group}\F-Engineering Launcher"; Filename: "{app}\FEngineeringLauncher.exe"
Name: "{group}\Удалить F-Engineering Launcher"; Filename: "{uninstallexe}"
Name: "{autodesktop}\F-Engineering Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FEngineeringLauncher.exe"; Description: "{cm:LaunchProgram,F-Engineering Launcher}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM FEngineeringLauncher.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;
