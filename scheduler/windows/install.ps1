$ErrorActionPreference='Stop'
if(-not (Get-Command gh -ErrorAction SilentlyContinue)){throw 'Install GitHub CLI from https://cli.github.com/ then run this installer again.'}
& gh auth status
if($LASTEXITCODE -ne 0){throw 'Run gh auth login in your own terminal first. Never send tokens through chat.'}
$dispatcher=Join-Path $PSScriptRoot 'dispatch.ps1'
if(-not (Test-Path $dispatcher)){throw 'Missing dispatch.ps1; extract the complete directory.'}
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -ExecutionPolicy Bypass -File "'+$dispatcher+'"')
$trigger=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10) -RepetitionDuration (New-TimeSpan -Days 365)
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 3)
Register-ScheduledTask -TaskName 'TelegramFinanceNewsFallback' -Action $action -Trigger $trigger -Settings $settings -Description 'Free local wakeup for existing finance-news-live workflow. Requires logged-in PC and network.' -Force | Out-Null
Write-Output 'Installed. Keep this directory. PC must be on, logged in and online. Does not change news selection or Telegram secrets.'
