[Setup]
AppName=JD Capital
AppVersion=2.1.0
AppPublisher=JD Capital
DefaultDirName={localappdata}\Programs\JD Capital
DefaultGroupName=JD Capital
OutputDir=installer
OutputBaseFilename=JD_Capital_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\JD-Capital.exe

[Files]
Source: "dist\JD-Capital\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\JD Capital"; Filename: "{app}\JD-Capital.exe"
Name: "{autodesktop}\JD Capital"; Filename: "{app}\JD-Capital.exe"

[Run]
Filename: "{app}\JD-Capital.exe"; Description: "Abrir JD Capital"; Flags: nowait postinstall skipifsilent
