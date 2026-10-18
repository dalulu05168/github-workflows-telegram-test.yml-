$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -ErrorAction SilentlyContinue
if ($task) {
    Stop-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -Confirm:$false
}
Write-Host 'Local fallback removed. Repository scheduler and Telegram settings were not changed.'
