# Bound verification of our own EXE; never starts the ordinary user launcher.
$ErrorActionPreference = 'Stop'
$themeExe = Join-Path $PSScriptRoot 'exe\applauncher.exe'
$themePreviousPlatform = $env:QT_QPA_PLATFORM
try {
    foreach ($themePlatform in @('offscreen', 'windows')) {
        $env:QT_QPA_PLATFORM = $themePlatform
        $themeOutput = Join-Path $PSScriptRoot "theme_bundle_$themePlatform"
        $themeProcess = Start-Process -FilePath $themeExe -ArgumentList @('--verify-design', ('"' + $themeOutput + '"')) -WindowStyle Hidden -PassThru
        try {
            if (-not $themeProcess.WaitForExit(40000)) {
                throw "Theme verification timed out: $themePlatform"
            }
            $themeProcess.Refresh()
            if ($themeProcess.ExitCode -ne 0) {
                throw "Theme verification failed: $themePlatform (exit $($themeProcess.ExitCode))"
            }
            $themeResult = Get-Content -LiteralPath (Join-Path $themeOutput 'verification.json') -Raw | ConvertFrom-Json
            if (-not $themeResult.passed -or -not $themeResult.frozen -or $themeResult.platform -ne $themePlatform) {
                throw "Invalid verification result: $themePlatform"
            }
            $themeResult | ConvertTo-Json -Depth 5
        }
        finally {
            if (-not $themeProcess.HasExited) {
                Get-CimInstance Win32_Process -Filter "ParentProcessId=$($themeProcess.Id)" |
                    Where-Object { $_.ExecutablePath -eq $themeExe } |
                    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
                Stop-Process -Id $themeProcess.Id -Force
            }
        }
    }
}
finally {
    if ($null -eq $themePreviousPlatform) {
        Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue
    }
    else {
        $env:QT_QPA_PLATFORM = $themePreviousPlatform
    }
}
