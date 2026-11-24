; F-Engineering Launcher v4.4.1 — Автономный однофайловый дистрибутив (Self-Extracting Single EXE)
; Инженерное бюро ООО «ФЕРО»
; Кодировка: UTF-8 with BOM

[Setup]
AppName=F-Engineering Launcher
AppVersion=4.4.1
VersionInfoVersion=4.4.1.0
VersionInfoCompany=ООО "ФЕРО"
VersionInfoDescription=F-Engineering Launcher v4.4.1 Setup
VersionInfoProductName=F-Engineering Launcher
AppPublisher=ООО "ФЕРО"
AppPublisherURL=https://ferospb.info
DefaultDirName={localappdata}\FEngineering_Launcher
DefaultGroupName=F-Engineering Launcher
OutputBaseFilename=F-Engineering_Launcher
OutputDir=..\dist_release
SetupIconFile=..\app\frontend\assets\flauncher.ico
UninstallDisplayIcon={app}\FEngineeringLauncher.exe
Compression=lzma2/max
SolidCompression=yes

; КРИТИЧНО: установка без прав администратора в профиль пользователя (%LOCALAPPDATA%)
PrivilegesRequired=lowest
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableFinishedPage=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Files]
; Полное содержимое дистрибутива со всеми зависимостями (Python, PyMuPDF, xlrd, ezdxf, Poppler)
Source: "C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\FEngineering_Launcher_v4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\runtime\cache"
Name: "{app}\runtime\logs"
Name: "{app}\runtime\manifests"
Name: "{app}\runtime\db"

[Icons]
Name: "{group}\F-Engineering Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; IconFilename: "{app}\app\frontend\assets\flauncher.ico"
Name: "{group}\Удалить F-Engineering Launcher"; Filename: "{uninstallexe}"
Name: "{autodesktop}\F-Engineering Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; IconFilename: "{app}\app\frontend\assets\flauncher.ico"

[Run]
Filename: "{app}\FEngineeringLauncher.exe"; Flags: nowait

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM FEngineeringLauncher.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpWelcome then
    WizardForm.NextButton.OnClick(WizardForm.NextButton);
end;
