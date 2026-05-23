Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Targets = @(
    "build",
    "dist"
)

foreach ($Target in $Targets) {
    $Path = Join-Path $ProjectRoot $Target
    $Resolved = Resolve-Path -LiteralPath $Path -ErrorAction SilentlyContinue
    if ($null -eq $Resolved) {
        continue
    }

    $ResolvedPath = $Resolved.Path
    if (-not $ResolvedPath.StartsWith($ProjectRoot.Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside project: $ResolvedPath"
    }

    Remove-Item -LiteralPath $ResolvedPath -Recurse -Force
    Write-Host "Removed $ResolvedPath"
}
