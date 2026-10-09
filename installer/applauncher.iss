; Inno Setup script for AppLauncher.
; Build the exe first (from the repo root): pyinstaller main.spec
; Then compile this script (from this folder or via the Inno Setup IDE):
;   ISCC.exe applauncher.iss
; The installer is written to installer\Output\.

#define MyAppName "AppLauncher"
#define MyAppVersion "2.2"
#define MyAppPublisher "Slipfaith"
#define MyAppURL "https://github.com/Slipfaith/applauncher"
#define MyAppExeName "applauncher.exe"

[Setup]
; Do not change this GUID once released - it identifies the app across
; versions so the installer can detect and upgrade a previous install.
AppId={{2F458762-6C9D-444C-9FEC-7AE240F113E4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Output
OutputBaseFilename=AppLauncher-Setup-{#MyAppVersion}
SetupIconFile=..\sliplaun.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=force
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
russian.AutostartTask=Запускать %1 при входе в Windows
english.AutostartTask=Launch %1 when Windows starts

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart"; Description: "{cm:AutostartTask,{#MyAppName}}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\applauncher.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
