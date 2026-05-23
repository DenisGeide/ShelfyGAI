param(
    [string]$DownloadUrl = "https://github.com/shelfygai/shelfygai/releases/download/v0.1.0/ShelfyGAI-Setup-0.1.0.exe",
    [string]$DownloadSha256 = "",
    [string]$InnoCompiler
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$IconPath = Join-Path $ProjectRoot "build\assets\app_icon.ico"

if (-not (Test-Path -LiteralPath $IconPath)) {
    $Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $Python)) {
        $Python = "python"
    }
    $IconSource = Join-Path $ProjectRoot "src\shelfygai\resources\app_icon.svg"
    & $Python (Join-Path $ProjectRoot "scripts\generate_icon.py") `
        --source $IconSource `
        --output $IconPath
}

if (-not $InnoCompiler) {
    $Command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
        $InnoCompiler = $Command.Source
    }
}

if (-not $InnoCompiler) {
    $ProgramFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
    if ($ProgramFilesX86) {
        $DefaultInnoPath = Join-Path $ProgramFilesX86 "Inno Setup 6\ISCC.exe"
        if (Test-Path -LiteralPath $DefaultInnoPath) {
            $InnoCompiler = $DefaultInnoPath
        }
    }
}

if (-not $InnoCompiler -or -not (Test-Path -LiteralPath $InnoCompiler)) {
    throw "Inno Setup compiler not found. Install Inno Setup 6 or pass -InnoCompiler <path-to-ISCC.exe>."
}

if (-not $DownloadUrl.StartsWith("https://", [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to build a web installer with a non-HTTPS download URL: $DownloadUrl"
}

if ($DownloadSha256 -and $DownloadSha256 -notmatch "^[A-Fa-f0-9]{64}$") {
    throw "DownloadSha256 must be empty or a 64-character SHA-256 hex string."
}

$InstallerScript = Join-Path $ProjectRoot "installer\ShelfyGAI-WebSetup.iss"
$CompilerArgs = @(
    "/DMyAppDownloadURL=`"$DownloadUrl`"",
    "/DMyAppDownloadSHA256=`"$DownloadSha256`"",
    $InstallerScript
)

& $InnoCompiler @CompilerArgs
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$InstallerOutput = Join-Path $ProjectRoot "dist\installer\ShelfyGAI-WebSetup-0.1.0.exe"
Write-Host "Web installer output: $InstallerOutput"
Write-Host "Download URL embedded: $DownloadUrl"
if ($DownloadSha256) {
    Write-Host "SHA-256 verification embedded: $DownloadSha256"
}
else {
    Write-Host "SHA-256 verification not embedded. Add -DownloadSha256 for release builds."
}
