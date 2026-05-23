param(
    [switch]$SkipChecks
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

$Version = (& $Python -c "from shelfygai import __version__; print(__version__)").Trim()
$ReleaseName = "ShelfyGAI-$Version-win-x64"
$ReleaseRoot = Join-Path $ProjectRoot "dist\release"
$StageDir = Join-Path $ReleaseRoot $ReleaseName
$ZipPath = Join-Path $ReleaseRoot "$ReleaseName.zip"
$ChecksumsPath = Join-Path $ReleaseRoot "SHA256SUMS.txt"
$ReleaseNotesPath = Join-Path $ProjectRoot "docs\RELEASE_NOTES_$Version.md"

& (Join-Path $PSScriptRoot "clean_build.ps1")
& (Join-Path $PSScriptRoot "build_exe.ps1") -SkipChecks:$SkipChecks

New-Item -ItemType Directory -Force -Path $StageDir | Out-Null
$AppPackageDir = Join-Path $ProjectRoot "dist\ShelfyGAI"
if (-not (Test-Path -LiteralPath (Join-Path $AppPackageDir "ShelfyGAI.exe"))) {
    throw "Packaged executable not found: $AppPackageDir"
}
Copy-Item -Path (Join-Path $AppPackageDir "*") -Destination $StageDir -Recurse -Force
Copy-Item -LiteralPath (Join-Path $ProjectRoot "LICENSE") -Destination $StageDir
Copy-Item -LiteralPath (Join-Path $ProjectRoot "README.md") -Destination $StageDir

if (-not (Test-Path -LiteralPath $ReleaseNotesPath)) {
    throw "Release notes not found: $ReleaseNotesPath"
}
Copy-Item -LiteralPath $ReleaseNotesPath -Destination (Join-Path $StageDir "RELEASE_NOTES.md")

if (Test-Path -LiteralPath $ZipPath) {
    Remove-Item -LiteralPath $ZipPath -Force
}

Compress-Archive -Path (Join-Path $StageDir "*") -DestinationPath $ZipPath

$Hash = Get-FileHash -Algorithm SHA256 -LiteralPath $ZipPath
"$($Hash.Hash.ToLowerInvariant())  $ReleaseName.zip" | Set-Content -LiteralPath $ChecksumsPath

Write-Host "Release package: $ZipPath"
Write-Host "Checksums: $ChecksumsPath"
