#define MyAppName "Motoboys WebApp"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Motoboys"
#define MyAppExeName "MotoboysWebApp.exe"

[Setup]
AppId={{F1D5A4D2-2A62-48F9-9E31-A5D0C1D42E73}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Motoboys WebApp
DefaultGroupName={#MyAppName}
OutputDir=..\dist
OutputBaseFilename=MotoboysWebApp-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:";

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: nowait postinstall skipifsilent
