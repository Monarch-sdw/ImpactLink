$runtimePath = Join-Path $PSScriptRoot '.runtime\processes.json'
if (-not (Test-Path -LiteralPath $runtimePath)) { Write-Output 'No saved local processes.'; exit }
$saved = Get-Content -LiteralPath $runtimePath -Raw | ConvertFrom-Json
foreach ($processId in @($saved.backend,$saved.frontend)) {
    $processInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$processId" -ErrorAction SilentlyContinue
    if ($processInfo -and ($processInfo.CommandLine -like '*uvicorn app.main:app*8017*' -or $processInfo.CommandLine -like '*next*3017*')) {
        # Stop only the saved process and its direct children, after identity checks.
        Get-CimInstance Win32_Process -Filter "ParentProcessId=$processId" | ForEach-Object { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
        Stop-Process -Id $processId -ErrorAction SilentlyContinue
    }
}
Write-Output 'Stopped the saved ImpactLink processes.'
