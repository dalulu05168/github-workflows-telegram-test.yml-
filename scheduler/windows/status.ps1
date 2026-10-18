$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'common.ps1')
Get-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -ErrorAction SilentlyContinue | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName 'TelegramFinanceNewsFallback' -ErrorAction SilentlyContinue | Format-List LastRunTime,LastTaskResult,NextRunTime
$log = Join-Path $PSScriptRoot 'logs/dispatcher.log'
if (Test-Path $log) { Get-Content -LiteralPath $log -Tail 15 } else { Write-Host 'No local check logged yet.' }
$gh = Resolve-GitHubCLI
& $gh run list --repo $repository --workflow finance-news-live.yml --limit 5
Write-Host 'Workflow success alone is not a delivery receipt. Check its News delivery status summary.'
