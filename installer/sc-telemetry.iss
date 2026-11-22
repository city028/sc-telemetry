; The installer around PyInstaller's dist\sc-telemetry folder. Build with
; build.ps1, which passes the version from app\updater.py.
; Per-user: no admin prompt, and an update can run without one too.
; Same layout as SC Locator's installer.

#ifndef AppVersion
  #error Build with build.ps1, which sets AppVersion
#endif

#define AppName "SC Telemetry"
#define AppExe "sc-telemetry.exe"
#define AppMutexName "Local\sc-telemetry"

[Setup]
; Never change AppId: it is what makes a new version an upgrade of the old one.
AppId={{8DF1A568-6CF6-457C-A91D-1387810A4525}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Citygamer
AppPublisherURL=https://github.com/city028/sc-telemetry
DefaultDirName={localappdata}\Programs\SC Telemetry
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
AppMutex={#AppMutexName}
CloseApplications=no
OutputDir=..\dist
OutputBaseFilename=sc-telemetry-setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[InstallDelete]
; Files a previous version shipped and this one does not. Settings are not
; here: they are in %LocalAppData%\SC Telemetry, which nothing in this file touches.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\sc-telemetry\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
; Without skipifsilent, so an update starts the new version again too.
Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; Description: "Start {#AppName}"; Flags: nowait postinstall

[Code]
// An update is started by the running program, which then closes.
// Give it time to go, or AppMutex would find it still running and give up.
function InitializeSetup(): Boolean;
var
  Waited: Integer;
begin
  Waited := 0;
  if WizardSilent then
    while CheckForMutexes('{#AppMutexName}') and (Waited < 30000) do
    begin
      Sleep(250);
      Waited := Waited + 250;
    end;
  Result := True;
end;
