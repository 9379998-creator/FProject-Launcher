; Fero-Launcher v4.5.0 — Автономный инсталлятор обновления (In-place Upgrade)
; Инженерное бюро ООО «ФЕРО» (https://ferospb.info)
; Кодировка: UTF-8 with BOM

[Setup]
AppName=Fero Launcher
AppVersion=4.5.0
VersionInfoVersion=4.5.0.0
VersionInfoCompany=ООО "ФЕРО"
VersionInfoDescription=Fero Launcher v4.5.0 Setup
VersionInfoProductName=Fero Launcher
AppPublisher=ООО "ФЕРО"
AppPublisherURL=https://ferospb.info
DefaultDirName={localappdata}\FEngineering_Launcher
DefaultGroupName=Fero Launcher
OutputBaseFilename=Fero_Launcher_v4.5.0
OutputDir=..\dist_colleague
SetupIconFile=..\app\frontend\assets\flauncher.ico
UninstallDisplayIcon={app}\FEngineeringLauncher.exe
Compression=lzma2/normal
SolidCompression=yes

; Установка строго в профиль пользователя без запроса прав администратора
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

[InstallDelete]
; Очистка устаревших ярлыков со старыми названиями
Type: files; Name: "{autodesktop}\F-Engineering Launcher.lnk"
Type: files; Name: "{group}\F-Engineering Launcher.lnk"

[Files]
; Полное содержимое релиза за исключением пользовательских данных
Source: "C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\Fero_Launcher_v4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "runtime\manifests\*,runtime\db\*,runtime\logs\*,runtime\cache\*"

[Dirs]
; Каталоги пользовательских данных — создаются при первой установке, никогда не перезаписываются
Name: "{app}\runtime\cache"
Name: "{app}\runtime\logs"
Name: "{app}\runtime\manifests"
Name: "{app}\runtime\db"

[Icons]
Name: "{group}\Fero Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; IconFilename: "{app}\app\frontend\assets\flauncher.ico"
Name: "{group}\Удалить Fero Launcher"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Fero Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; IconFilename: "{app}\app\frontend\assets\flauncher.ico"

[Run]
Filename: "{sys}\ie4uinit.exe"; Parameters: "-show"; Flags: runhidden
Filename: "{app}\FEngineeringLauncher.exe"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  // Закрываем активные процессы лаунчера и бэкенда для разблокировки файлов
  Exec('taskkill.exe', '/F /IM FEngineeringLauncher.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Sleep(800);
  Result := True;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpWelcome then
    WizardForm.NextButton.OnClick(WizardForm.NextButton);
end;
