; ShelfyGAI web installer bootstrapper.
; Produces one small EXE that downloads the full offline installer from a
; GitHub Release URL, verifies an optional SHA-256 hash, then launches it.

#define MyAppName "ShelfyGAI"
#define MyAppVersion "0.1.0"
#define MyAppVersionInfo "0.1.0.0"
#define MyAppPublisher "ShelfyGAI contributors"
#define MyAppURL "https://github.com/shelfygai/shelfygai"
#define MyAppInstallerName "ShelfyGAI-Setup-0.1.0.exe"

#ifndef MyAppDownloadURL
#define MyAppDownloadURL "https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe"
#endif

#ifndef MyAppDownloadSHA256
#define MyAppDownloadSHA256 ""
#endif

[Setup]
AppId={{A2D9DF1E-75AF-49D8-A1E2-4E4A86A4F4A7}
AppName={#MyAppName} Web Installer
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion} Web Installer
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
CreateAppDir=no
CreateUninstallRegKey=no
Uninstallable=no
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=ShelfyGAI-WebSetup-{#MyAppVersion}
SetupIconFile=..\build\assets\app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
VersionInfoVersion={#MyAppVersionInfo}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=ShelfyGAI web installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
CloseApplications=no
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
english.DownloadPageCaption=Downloading ShelfyGAI
english.DownloadPageDescription=Setup is downloading the full ShelfyGAI installer from GitHub Releases.
english.DownloadFailed=ShelfyGAI could not be downloaded. Check your internet connection and try again.
english.LaunchingFullInstaller=Launching the ShelfyGAI installer...
english.ReadyLabel=Setup will download ShelfyGAI from:%n%n{#MyAppDownloadURL}%n%nNothing is installed until the downloaded installer starts.

[Run]
Filename: "{tmp}\{#MyAppInstallerName}"; Parameters: "/SP-"; StatusMsg: "{cm:LaunchingFullInstaller}"; Flags: waituntilterminated skipifdoesntexist

[Code]
var
  DownloadPage: TDownloadWizardPage;

function OnDownloadProgress(
  const Url, FileName: String;
  const Progress, ProgressMax: Int64
): Boolean;
begin
  Result := True;
end;

procedure InitializeWizard;
begin
  DownloadPage :=
    CreateDownloadPage(
      CustomMessage('DownloadPageCaption'),
      CustomMessage('DownloadPageDescription'),
      @OnDownloadProgress
    );
  DownloadPage.ShowBaseNameInsteadOfUrl := True;
  WizardForm.ReadyMemo.Lines.Text := CustomMessage('ReadyLabel');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  DownloadPage.Clear;
  DownloadPage.Add(
    '{#MyAppDownloadURL}',
    '{#MyAppInstallerName}',
    '{#MyAppDownloadSHA256}'
  );
  DownloadPage.Show;
  try
    DownloadPage.Download;
  except
    Result := CustomMessage('DownloadFailed') + #13#10 + GetExceptionMessage;
  finally
    DownloadPage.Hide;
  end;
end;
