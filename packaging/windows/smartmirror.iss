; Inno Setup script for SmartMirror RAID (Windows installer).
;
; Build steps (run from the repository root in a Windows shell):
;   1. python -m venv .venv && .venv\Scripts\activate
;   2. pip install -r requirements-dev.txt
;   3. python packaging\generate_icons.py
;   4. pyinstaller packaging\smartmirror.spec
;   5. "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\windows\smartmirror.iss
;
; The result is dist\installer\SmartMirrorRAID-Setup-<version>.exe

#define AppName "SmartMirror RAID"
#define AppVersion "1.0.0"
#define AppPublisher "Yags"
#define AppURL "https://www.yags.in"
#define AppExeName "SmartMirrorRAID.exe"

[Setup]
AppId={{9F3A1C5E-7B2D-4E6A-9C4F-SMARTMIRRORRAID}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\SmartMirrorRAID
DefaultGroupName=SmartMirror RAID
DisableProgramGroupPage=yes
OutputDir=..\..\dist\installer
OutputBaseFilename=SmartMirrorRAID-Setup-{#AppVersion}
SetupIconFile=..\icons\icon.ico
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; SmartMirror RAID is a per-user mirroring tool; no admin rights required.
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Start SmartMirror RAID automatically on login"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
; The single-file PyInstaller executable.
Source: "..\..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "..\..\INSTALL.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\SmartMirror RAID"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,SmartMirror RAID}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\SmartMirror RAID"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
; Launch minimised to tray on login when the user opts in.
Name: "{userstartup}\SmartMirror RAID"; Filename: "{app}\{#AppExeName}"; Parameters: "tray"; Tasks: startupicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,SmartMirror RAID}"; Flags: nowait postinstall skipifsilent
