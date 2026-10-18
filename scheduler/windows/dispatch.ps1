param([switch]$LibraryOnly)
$ErrorActionPreference='Stop'
$repository='dalulu05168/github-workflows-telegram-test.yml-'
function Get-LocalMarketTime([DateTimeOffset]$Now,[string]$Iana,[string]$Windows) {
 try {$zone=[TimeZoneInfo]::FindSystemTimeZoneById($Iana)}catch{$zone=[TimeZoneInfo]::FindSystemTimeZoneById($Windows)}
 return [TimeZoneInfo]::ConvertTime($Now,$zone)
}
function Test-PublicationWindow([DateTimeOffset]$Local) {
 return (($Local.Hour -eq 7 -and $Local.Minute -ge 30) -or ($Local.Hour -ge 8 -and $Local.Minute -ge 30))
}
function Get-DispatchDecision([DateTimeOffset]$Now,$Runs) {
 $ro=Get-LocalMarketTime $Now 'Europe/Bucharest' 'E. Europe Standard Time'
 $fr=Get-LocalMarketTime $Now 'Europe/Paris' 'Romance Standard Time'
 if(-not (Test-PublicationWindow $ro) -and -not (Test-PublicationWindow $fr)){return 'OUTSIDE_WINDOW'}
 foreach($run in $Runs){
  if($run.status -in @('queued','in_progress','waiting','pending','requested')){return 'RUN_ALREADY_PENDING'}
  $age=($Now-[DateTimeOffset]::Parse($run.created_at)).TotalMinutes
  if($age -ge -2 -and $age -lt 10){return 'RECENT_CHECK_EXISTS'}
 }
 return 'DISPATCH'
}
if($LibraryOnly){return}
$lockPath=Join-Path $PSScriptRoot 'dispatcher.lock'
$lock=$null
try {
 try {$lock=[IO.File]::Open($lockPath,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)}catch{exit 0}
 $now=[DateTimeOffset]::UtcNow
 if((Get-DispatchDecision $now @()) -eq 'OUTSIDE_WINDOW'){exit 0}
 $raw=& gh api "repos/$repository/actions/workflows/finance-news-live.yml/runs?per_page=5" 2>$null
 if($LASTEXITCODE -ne 0){throw 'GitHub authentication or read failed. Run gh auth login first.'}
 $runs=($raw|ConvertFrom-Json).workflow_runs
 $decision=Get-DispatchDecision $now $runs
 if($decision -ne 'DISPATCH'){Write-Output $decision;exit 0}
 & gh workflow run finance-news-live.yml --repo $repository --ref main
 if($LASTEXITCODE -ne 0){throw 'Workflow dispatch rejected. Check GitHub Actions permission.'}
 Write-Output ($now.ToString('o')+' DISPATCH_ACCEPTED: this is not a Telegram delivery receipt.')
}finally{if($lock){$lock.Dispose()}}
