$ErrorActionPreference = 'Stop'
try {
    . (Join-Path $PSScriptRoot 'common.ps1')
    $gh = Resolve-GitHubCLI
    & $gh auth status --hostname github.com
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'First use: authorize your own GitHub account in the official browser page.'
        & $gh auth login --hostname github.com --git-protocol https --web
        if ($LASTEXITCODE -ne 0) { throw 'GitHub authorization was not completed.' }
    }
    $permission = & $gh api "repos/$repository" --jq '.permissions.push'
    if ($LASTEXITCODE -ne 0 -or "$permission".Trim() -ne 'true') {
        throw 'This GitHub account cannot dispatch this repository. Use its owner or an account with write access.'
    }
    $dispatcher = Join-Path $PSScriptRoot 'dispatch.ps1'
    if (-not (Test-Path $dispatcher)) { throw 'Missing dispatch.ps1. Extract the complete package.' }
    $powershell = Join-Path $env:SystemRoot 'System32/WindowsPowerShell/v1.0/powershell.exe'
    $action = New-ScheduledTaskAction -Execute $powershell -Argument ('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $dispatcher + '"') -WorkingDirectory $PSScriptRoot
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Description 'Local wakeup of existing news workflow; logged-in PC and network required.' -Force | Out-Null
    $task = Get-ScheduledTask -TaskName 'TelegramFinanceNewsFallback'
    if (-not $task) { throw 'Task registration could not be verified.' }
    Write-Host 'INSTALLED: TelegramFinanceNewsFallback. First check in about one minute, then every ten minutes.'
    Write-Host 'Keep this folder in place. Stay logged in, awake and online. No Telegram key is stored here.'
    Write-Host 'Use status.cmd to inspect the task and logs. Accepted dispatch does not prove delivery.'
} catch {
    Write-Host ('INSTALL FAILED: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
