; ==============================================================================
; AudioGuard — Inno Setup Script
; Generates a 1-click standalone Windows installer for AudioGuard (x64 / x86)
; ==============================================================================

#ifndef AppArch
#define AppArch "x64"
#endif

[Setup]
AppName=AudioGuard
AppVersion=1.6.2
AppPublisher=MAHDI DIGITAL LLC
AppPublisherURL=https://github.com/midimahdi/audioguard
AppSupportURL=https://github.com/midimahdi/audioguard
DefaultDirName={localappdata}\Programs\AudioGuard
DefaultGroupName=AudioGuard
OutputDir=..\dist-installer
OutputBaseFilename=AudioGuard-Setup-{#AppArch}
Compression=lzma2/max
SolidCompression=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
DisableDirPage=no
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\AudioGuard.exe
WizardStyle=modern

#if AppArch == "x64"
ArchitecturesInstallIn64BitMode=x64
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupicon"; Description: "Launch AudioGuard automatically on Windows startup (in background)"; GroupDescription: "Startup Options:"; Flags: unchecked

[Files]
; Dist folder contents produced by PyInstaller --onedir
Source: "..\dist\AudioGuard\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\AudioGuard"; Filename: "{app}\AudioGuard.exe"; Comment: "Bulletproof Lossless Audio Backup System"
Name: "{autodesktop}\AudioGuard"; Filename: "{app}\AudioGuard.exe"; Tasks: desktopicon; Comment: "Bulletproof Lossless Audio Backup System"
Name: "{userstartup}\AudioGuard"; Filename: "{app}\AudioGuard.exe"; Parameters: "--minimized"; Tasks: startupicon; Comment: "AudioGuard Background Backup Monitor"

[Run]
Filename: "{app}\AudioGuard.exe"; Description: "{cm:LaunchProgram,AudioGuard}"; Flags: nowait postinstall skipifsilent
