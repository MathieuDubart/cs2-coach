; Wily's installer (08/10, the user: "une façon beaucoup plus simple d'installer l'app"). A small setup that downloads
; the app's three parts from the site (the release the app's own updates use: Python, the code, the base), checks each
; one's SHA-256 (baked in here by make_beta.py at the release), unpacks them for this Windows user only (no
; administrator rights), writes the player's settings ({"role": "client"}), and makes the shortcuts: Start menu,
; desktop, start with Windows (Wily then opens Live by itself when CS2 starts). The uninstaller stops Wily and asks
; whether to keep the player's matches. Built by make_beta.py from this template (@...@ are filled there).

#define AppVersion "@VERSION@"
#define AppVerNum "@VERNUM@"
#define Build "@BUILD@"
#define BaseUrl "@BASEURL@"
#define RtFile "@RT_FILE@"
#define RtSha "@RT_SHA@"
#define CodeFile "@CODE_FILE@"
#define CodeSha "@CODE_SHA@"
#define BaseFile "@BASE_FILE@"
#define BaseSha "@BASE_SHA@"
#define TotalMB "@TOTAL_MB@"

[Setup]
AppId={{6E9A3B51-4C2D-4F0E-9B7A-2D8C5A1F7E30}
AppName=Wily
AppVersion={#AppVersion}
AppVerName=Wily {#AppVersion}
VersionInfoVersion={#AppVerNum}
VersionInfoDescription=Wily, your CS2 coach (setup)
AppPublisher=Valentin Gassend
AppPublisherURL=https://wily.valentingassend.com
AppSupportURL=https://wily.valentingassend.com
DefaultDirName={autopf}\Wily
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=@OUTDIR@
OutputBaseFilename=WilySetup
SetupIconFile=@ICON@
UninstallDisplayIcon={app}\wily.ico
UninstallDisplayName=Wily
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
; the parts are downloaded then unpacked: about 2 GB on the drive while installing, 1.5 GB after
ExtraDiskSpaceRequired=2200000000
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; tar.exe (the unpacking) comes with Windows 10 1803 and later
MinVersion=10.0.17134
ShowLanguageDialog=auto
CloseApplications=no
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
Name: "fr"; MessagesFile: "compiler:Languages\French.isl"

[CustomMessages]
en.StartWithWindows=Start Wily with Windows (it opens Live by itself when CS2 starts)
fr.StartWithWindows=Démarrer Wily avec Windows (il ouvre Live tout seul quand CS2 démarre)
en.Downloading=Downloading Wily
fr.Downloading=Téléchargement de Wily
en.DownloadingDesc=About {#TotalMB} MB from wily.valentingassend.com, each part checked.
fr.DownloadingDesc=Environ {#TotalMB} Mo depuis wily.valentingassend.com, chaque partie vérifiée.
en.DownloadFailed=The download failed: %1%n%nCheck your connection, then click Install again.
fr.DownloadFailed=Le téléchargement a échoué : %1%n%nVérifie ta connexion, puis clique de nouveau sur Installer.
en.UnpackPython=Unpacking Python (about a minute)...
fr.UnpackPython=Décompression de Python (environ une minute)...
en.UnpackApp=Unpacking the app...
fr.UnpackApp=Décompression de l'application...
en.UnpackBase=Unpacking the base of matches...
fr.UnpackBase=Décompression de la base de matchs...
en.UnpackFailed=Unpacking %1 failed (code %2). Make sure the drive has 2 GB free, then click Install again.
fr.UnpackFailed=La décompression de %1 a échoué (code %2). Vérifie qu'il reste 2 Go libres sur le disque, puis clique de nouveau sur Installer.
en.KeepData=Keep your matches, your profile and your settings (the "out" folder) for a later reinstall?
fr.KeepData=Garder tes matchs, ton profil et tes réglages (le dossier « out ») pour une prochaine installation ?

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startup"; Description: "{cm:StartWithWindows}"

[Files]
Source: "@ICON@"; DestDir: "{app}"; DestName: "wily.ico"

[Icons]
Name: "{autoprograms}\Wily"; Filename: "{app}\python\pythonw.exe"; Parameters: "-s serve.py"; WorkingDir: "{app}"; IconFilename: "{app}\wily.ico"; Comment: "Wily, your CS2 coach"
Name: "{autodesktop}\Wily"; Filename: "{app}\python\pythonw.exe"; Parameters: "-s serve.py"; WorkingDir: "{app}"; IconFilename: "{app}\wily.ico"; Comment: "Wily, your CS2 coach"; Tasks: desktopicon
Name: "{userstartup}\Wily"; Filename: "{app}\python\pythonw.exe"; Parameters: "-s serve.py --no-browser"; WorkingDir: "{app}"; IconFilename: "{app}\wily.ico"; Tasks: startup

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-s serve.py"; WorkingDir: "{app}"; Description: "{cm:LaunchProgram,Wily}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('Downloading'), CustomMessage('DownloadingDesc'), @OnDownloadProgress);
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

// Wily running from this folder (a reinstall, the uninstall): stopped, never another Python of the PC
procedure StopWily();
var
  Locator, Service, Procs, P, V: Variant;
  I: Integer;
  AppDir, Path: String;
begin
  AppDir := Lowercase(ExpandConstant('{app}')) + '\';
  try
    Locator := CreateOleObject('WbemScripting.SWbemLocator');
    Service := Locator.ConnectServer('.', 'root\CIMV2');
    Procs := Service.ExecQuery('SELECT ProcessId, ExecutablePath FROM Win32_Process WHERE Name = ''pythonw.exe'' OR Name = ''python.exe''');
    for I := 0 to Procs.Count - 1 do
    begin
      P := Procs.ItemIndex(I);
      V := P.ExecutablePath;
      if VarIsNull(V) then
        continue;
      Path := V;
      if Pos(AppDir, Lowercase(Path)) = 1 then
        P.Terminate();
    end;
  except
    Log('Could not list the running processes: ' + GetExceptionMessage);
  end;
end;

function Unpack(const Zip, Dest, What: String): Boolean;
var
  Code: Integer;
begin
  DownloadPage.SetText(What, '');
  ForceDirectories(Dest);
  Result := Exec(ExpandConstant('{sys}\tar.exe'), '-xf "' + ExpandConstant('{tmp}\') + Zip + '" -C "' + Dest + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
  if not Result then
    SuppressibleMsgBox(FmtMessage(CustomMessage('UnpackFailed'), [Zip, IntToStr(Code)]), mbCriticalError, MB_OK, IDOK);
end;

// on "Install": the three parts downloaded and checked, then unpacked; a failure keeps the page (Install again)
function NextButtonClick(CurPageID: Integer): Boolean;
var
  App: String;
begin
  Result := True;
  if CurPageID <> wpReady then
    exit;
  App := ExpandConstant('{app}');
  DownloadPage.Clear;
  DownloadPage.Add('{#BaseUrl}{#RtFile}', 'runtime.zip', '{#RtSha}');
  DownloadPage.Add('{#BaseUrl}{#CodeFile}', 'code.zip', '{#CodeSha}');
  DownloadPage.Add('{#BaseUrl}{#BaseFile}', 'base.zip', '{#BaseSha}');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
    except
      if not DownloadPage.AbortedByUser then
        SuppressibleMsgBox(FmtMessage(CustomMessage('DownloadFailed'), [GetExceptionMessage]), mbCriticalError, MB_OK, IDOK);
      Result := False;
      exit;
    end;
    StopWily();
    DownloadPage.ProgressBar.Style := npbstMarquee;
    Result := Unpack('runtime.zip', App, CustomMessage('UnpackPython')) and Unpack('code.zip', App, CustomMessage('UnpackApp'))
              and Unpack('base.zip', App + '\out', CustomMessage('UnpackBase'));
    if Result then
    begin
      ForceDirectories(App + '\cache');
      if not FileExists(App + '\out\settings.json') then   // a player's copy: never the coach's server mode
        SaveStringToFile(App + '\out\settings.json', '{"role": "client"}', False);
    end;
  finally
    DownloadPage.ProgressBar.Style := npbstNormal;
    DownloadPage.Hide;
  end;
end;

// the uninstall: Wily stopped, then everything it unpacked removed; the player's "out" folder kept if they say so
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  App: String;
  KeepData: Boolean;
  FR: TFindRec;
begin
  if CurUninstallStep <> usUninstall then
    exit;
  App := ExpandConstant('{app}');
  StopWily();
  KeepData := SuppressibleMsgBox(CustomMessage('KeepData'), mbConfirmation, MB_YESNO, IDYES) = IDYES;
  if FindFirst(App + '\*', FR) then
  begin
    try
      repeat
        if (FR.Name <> '.') and (FR.Name <> '..') and not (KeepData and (CompareText(FR.Name, 'out') = 0)) then
        begin
          if FR.Attributes and FILE_ATTRIBUTE_DIRECTORY <> 0 then
            DelTree(App + '\' + FR.Name, True, True, True)
          else
            DeleteFile(App + '\' + FR.Name);
        end;
      until not FindNext(FR);
    finally
      FindClose(FR);
    end;
  end;
end;
