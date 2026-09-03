; Draftex Screen Recorder – Inno Setup 6.3+ skript
; Build:  build.bat  (alebo: ISCC.exe installer.iss po pyinstaller + skopírovaní ffmpeg.exe do dist\)

#define MyAppName      "Draftex Screen Recorder"
#define MyAppVersion   "1.0.1"
#define MyAppPublisher "Draftex s.r.o."
#define MyAppURL       "https://draftex.sk"
#define MyAppExeName   "DraftexScreenRecorder.exe"
#define MyAppSource    "dist\DraftexScreenRecorder"

[Setup]
AppId={{7E3C9A41-5B2D-4F86-9D1A-C4E7F0B2A9D3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}
DefaultDirName={autopf}\Draftex\Screen Recorder
DefaultGroupName=Draftex
DisableProgramGroupPage=yes
; bežný používateľ bez admin práv (inštaluje do %LocalAppData%\Programs); dialóg ponúkne aj inštaláciu pre všetkých
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=installer
OutputBaseFilename=DraftexScreenRecorder-Setup-{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
; výber jazyka vždy; zvolený jazyk sa zapíše do registra a aplikácia ho prevezme
ShowLanguageDialog=yes
; Podpis inštalátora (Tools > Configure Sign Tools v Inno Setup, názov "draftex"):
;SignTool=draftex $f
;SignedUninstaller=yes

[Languages]
; názvy "sk" / "en" = hodnoty, ktoré aplikácia číta z registra (language)
Name: "sk"; MessagesFile: "compiler:Languages\Slovak.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
sk.Autostart=Spúšťať pri prihlásení do Windows (na pozadí, ikona v lište)
en.Autostart=Start with Windows (in background, tray icon)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "autostart";   Description: "{cm:Autostart}"; Flags: unchecked

[Files]
Source: "{#MyAppSource}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}";  Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; autoštart do lišty
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "DraftexScreenRecorder"; ValueData: """{app}\{#MyAppExeName}"" --tray"; Flags: uninsdeletevalue; Tasks: autostart
; nastavenia aplikácie (QSettings) – jazyk zvolený v inštalátore; celý kľúč sa zmaže pri odinštalovaní
Root: HKCU; Subkey: "Software\Draftex\ScreenRecorder"; ValueType: string; ValueName: "language"; ValueData: "{language}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
