; Tezis-Setup.iss — Inno Setup 6
; Локальная сборка:
;   ISCC.exe /DAppVersion=2.5.2 scripts\installer\Tezis-Setup.iss
; Вывод: dist\Tezis-Setup.exe
;
; ВАЖНО: AppId — замороженный GUID. Не менять. Он связывает upgrade и uninstall.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#define AppName       "Тезис"
#define AppExeName    "Tezis.exe"
#define AppId         "{{14059DE7-BFA1-4897-A1ED-4F6D2FF5CE95}}"

[Setup]
AppId={#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=tutormvetrov
AppPublisherURL=https://github.com/tutormvetrov/ticket-exam-trainer
AppSupportURL=https://github.com/tutormvetrov/ticket-exam-trainer/issues
AppUpdatesURL=https://github.com/tutormvetrov/ticket-exam-trainer/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=Tezis-Setup
SetupIconFile=..\..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
CloseApplications=force
RestartApplications=no
MinVersion=10.0.17763
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoCompany=tutormvetrov

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительно:"; Flags: checkedonce
Name: "installollama"; Description: "Установить Ollama для ИИ-рецензирования (опционально, ~3 ГБ)"; GroupDescription: "Дополнительные компоненты:"; Flags: unchecked

[Files]
Source: "..\..\dist\Tezis.exe";                       DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\scripts\install_ollama_wizard.ps1";    DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\..\scripts\setup_ollama_windows.ps1";     DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\..\scripts\check_ollama.ps1";             DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "..\..\assets\icon.ico";                      DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README_classmates.md";                  DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";                           Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}";     Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";                     Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\install_ollama_wizard.ps1"""; WorkingDir: "{app}"; StatusMsg: "Запуск мастера Ollama..."; Flags: postinstall nowait; Tasks: installollama

Filename: "{app}\{#AppExeName}"; Description: "Запустить Тезис"; Flags: nowait postinstall skipifsilent unchecked

; Note: Inno Setup automatically removes all [Files] entries on uninstall.
; User data at %LOCALAPPDATA%\Tezis\app_data\ is NOT touched — it lives outside {app}.
; No [UninstallDelete] section needed.
