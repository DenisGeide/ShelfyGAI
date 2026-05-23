param(
    [switch]$Clean,
    [switch]$SkipChecks,
    [switch]$InstallBuildDeps,
    [switch]$SmokeTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}
$env:PYTHONPATH = Join-Path $ProjectRoot "src"

if ($Clean) {
    & (Join-Path $PSScriptRoot "clean_build.ps1")
}

if ($InstallBuildDeps) {
    & $Python -m pip install -e ".[build]"
}

& $Python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed. Run: .\scripts\build_exe.ps1 -InstallBuildDeps"
}

if (-not $SkipChecks) {
    & $Python -m ruff check . --no-cache
    & $Python -m pytest -p no:cacheprovider
}

$IconSource = Join-Path $ProjectRoot "src\shelfygai\resources\app_icon.svg"
$IconOutput = Join-Path $ProjectRoot "build\assets\app_icon.ico"
& $Python (Join-Path $ProjectRoot "scripts\generate_icon.py") `
    --source $IconSource `
    --output $IconOutput

$SpecPath = Join-Path $ProjectRoot "shelfygai.spec"
& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath (Join-Path $ProjectRoot "dist") `
    --workpath (Join-Path $ProjectRoot "build\pyinstaller") `
    $SpecPath

$ExePath = Join-Path $ProjectRoot "dist\ShelfyGAI\ShelfyGAI.exe"
if (-not (Test-Path -LiteralPath $ExePath)) {
    throw "Expected executable was not created: $ExePath"
}

if ($SmokeTest) {
    $SmokeAppData = Join-Path $ProjectRoot "build\smoke-appdata"
    New-Item -ItemType Directory -Force -Path $SmokeAppData | Out-Null
    $PreviousAppData = $env:APPDATA
    $PreviousQtPlatform = $env:QT_QPA_PLATFORM
    try {
        $env:APPDATA = $SmokeAppData
        $env:QT_QPA_PLATFORM = "offscreen"
        $SmokeProcess = Start-Process `
            -FilePath $ExePath `
            -ArgumentList "--packaging-smoke-test" `
            -Wait `
            -PassThru
        if ($SmokeProcess.ExitCode -ne 0) {
            throw "Packaged app smoke test failed with exit code $($SmokeProcess.ExitCode)"
        }
        $SettingsPath = Join-Path $SmokeAppData "ShelfyGAI\settings.json"
        $LogPath = Join-Path $SmokeAppData "ShelfyGAI\logs\shelfygai.log"
        if (-not (Test-Path -LiteralPath $SettingsPath)) {
            throw "Smoke test did not create settings: $SettingsPath"
        }
        if (-not (Test-Path -LiteralPath $LogPath)) {
            throw "Smoke test did not create log: $LogPath"
        }
    }
    finally {
        $env:APPDATA = $PreviousAppData
        $env:QT_QPA_PLATFORM = $PreviousQtPlatform
    }
}

Write-Host "Built ShelfyGAI package: $(Split-Path -Parent $ExePath)"
Write-Host "Executable: $ExePath"
