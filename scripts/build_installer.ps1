param(
    [switch]$Clean,
    [switch]$SkipChecks,
    [switch]$InstallBuildDeps,
    [switch]$SkipExeBuild,
    [string]$InnoCompiler
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ExePath = Join-Path $ProjectRoot "dist\ShelfyGAI\ShelfyGAI.exe"

if (-not $SkipExeBuild) {
    & (Join-Path $PSScriptRoot "build_exe.ps1") `
        -Clean:$Clean `
        -SkipChecks:$SkipChecks `
        -InstallBuildDeps:$InstallBuildDeps
}

if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Packaged executable not found. Run .\scripts\build_exe.ps1 first: $ExePath"
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

$InstallerScript = Join-Path $ProjectRoot "installer\ShelfyGAI.iss"
& $InnoCompiler $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$InstallerOutput = Join-Path $ProjectRoot "dist\installer"
$InstallerFile = Join-Path $InstallerOutput "ShelfyGAI-Setup-v0.1.0.exe"
if (-not (Test-Path -LiteralPath $InstallerFile)) {
    throw "Expected installer was not created: $InstallerFile"
}
Write-Host "Installer output: $InstallerFile"
