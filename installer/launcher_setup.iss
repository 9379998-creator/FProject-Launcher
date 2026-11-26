; Fero-Launcher v4.5.0 — Скрипт инсталлятора (Inno Setup 6).
; Лейбл FERO / Fero Engineering
; Кодировка: UTF-8 with BOM

[Setup]
AppName=Fero-Launcher
AppVersion=4.5.0
AppPublisher=ООО "ФЕРО"
AppPublisherURL=https://ferospb.info
DefaultDirName={localappdata}\Fero_Launcher
DefaultGroupName=Fero-Launcher
OutputBaseFilename=Fero_Launcher_v4.5.0_Setup
OutputDir=..\dist_setup
SetupIconFile=..\app\frontend\assets\flauncher.ico
UninstallDisplayIcon={app}\FEngineeringLauncher.exe
Compression=lzma2/normal
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
Source: "C:\Users\a9379\.gemini\antigravity\scratch\dist_colleague\Fero_Launcher_v4\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\runtime\cache"
Name: "{app}\runtime\logs"
Name: "{app}\runtime\manifests"
Name: "{app}\runtime\db"

[Icons]
Name: "{group}\Fero-Launcher"; Filename: "{app}\FEngineeringLauncher.exe"
Name: "{group}\Удалить Fero-Launcher"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Fero Launcher"; Filename: "{app}\FEngineeringLauncher.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FEngineeringLauncher.exe"; Description: "{cm:LaunchProgram,Fero-Launcher}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  ErrorCode: Integer;
begin
  Exec('taskkill.exe', '/F /IM FEngineeringLauncher.exe', '', SW_HIDE, ewWaitUntilTerminated, ErrorCode);
  Result := True;
end;

procedure MigrateLegacyRuntime();
var
  OldRuntimeDir, NewRuntimeDir: String;
  OldManifestsDir, NewManifestsDir: String;
  OldDbDir, NewDbDir: String;
  FindRec: TFindRec;
  SrcFile, DstFile: String;
begin
  OldRuntimeDir := ExpandConstant('{localappdata}\FEngineering_Launcher\runtime');
  NewRuntimeDir := ExpandConstant('{app}\runtime');

  if not DirExists(OldRuntimeDir) then
    Exit;

  // 1. Манифесты ранее загруженных объектов (Data Continuity)
  OldManifestsDir := OldRuntimeDir + '\manifests';
  NewManifestsDir := NewRuntimeDir + '\manifests';
  if DirExists(OldManifestsDir) then
  begin
    ForceDirectories(NewManifestsDir);
    if FindFirst(OldManifestsDir + '\*.json', FindRec) then
    begin
      try
        repeat
          SrcFile := OldManifestsDir + '\' + FindRec.Name;
          DstFile := NewManifestsDir + '\' + FindRec.Name;
          if not FileExists(DstFile) then
            FileCopy(SrcFile, DstFile, False);
        until not FindNext(FindRec);
      finally
        FindClose(FindRec);
      end;
    end;
  end;

  // 2. Пользовательские настройки привязки программ
  if FileExists(OldRuntimeDir + '\native_apps.json') and (not FileExists(NewRuntimeDir + '\native_apps.json')) then
  begin
    FileCopy(OldRuntimeDir + '\native_apps.json', NewRuntimeDir + '\native_apps.json', False);
  end;

  // 3. База данных launcher.sqlite
  OldDbDir := OldRuntimeDir + '\db';
  NewDbDir := NewRuntimeDir + '\db';
  if FileExists(OldDbDir + '\launcher.sqlite') and (not FileExists(NewDbDir + '\launcher.sqlite')) then
  begin
    ForceDirectories(NewDbDir);
    FileCopy(OldDbDir + '\launcher.sqlite', NewDbDir + '\launcher.sqlite', False);
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    try
      MigrateLegacyRuntime();
    except
      // Исключения миграции не должны прерывать завершение установки
    end;
  end;
end;
