param(
    [switch]$SkipE2E
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webDir = Join-Path $repoRoot "apps\web"
$serverDir = Join-Path $repoRoot "apps\server"
$pytestExe = Join-Path $serverDir ".venv\Scripts\pytest.exe"
$ruffExe = Join-Path $serverDir ".venv\Scripts\ruff.exe"

function Invoke-Step {
    param(
        [string]$Name,
        [string]$WorkingDirectory,
        [scriptblock]$Action
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $Action
        if ($LASTEXITCODE -ne 0) {
            throw "$Name failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

Invoke-Step -Name "Web lint" -WorkingDirectory $repoRoot -Action {
    pnpm --dir $webDir lint
}

Invoke-Step -Name "Web build" -WorkingDirectory $repoRoot -Action {
    pnpm --dir $webDir build
}

Invoke-Step -Name "Web unit tests" -WorkingDirectory $repoRoot -Action {
    pnpm --dir $webDir test
}

if (-not $SkipE2E) {
    Invoke-Step -Name "Web e2e tests" -WorkingDirectory $repoRoot -Action {
        pnpm --dir $webDir test:e2e
    }
}

Invoke-Step -Name "Server test lint" -WorkingDirectory $serverDir -Action {
    & $ruffExe check tests
}

Invoke-Step -Name "Server pytest" -WorkingDirectory $serverDir -Action {
    & $pytestExe
}

Write-Host ""
Write-Host "All checks passed." -ForegroundColor Green
