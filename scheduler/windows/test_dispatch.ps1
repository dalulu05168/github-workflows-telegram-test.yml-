$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'dispatch.ps1') -LibraryOnly
$night=[DateTimeOffset]::Parse('2026-10-18T01:00:00Z')
if((Get-DispatchDecision $night @()) -ne 'OUTSIDE_WINDOW'){throw 'night'}
$active=[DateTimeOffset]::Parse('2026-10-18T05:37:00Z')
if((Get-DispatchDecision $active @()) -ne 'DISPATCH'){throw 'active'}
if((Get-DispatchDecision $active @(@{status='in_progress';created_at='2026-10-18T05:00:00Z'})) -ne 'RUN_ALREADY_PENDING'){throw 'overlap'}
if((Get-DispatchDecision $active @(@{status='completed';created_at='2026-10-18T05:34:00Z'})) -ne 'RECENT_CHECK_EXISTS'){throw 'recent'}
$winter=[DateTimeOffset]::Parse('2026-11-02T05:37:00Z')
if((Get-DispatchDecision $winter @()) -ne 'DISPATCH'){throw 'winter DST'}
'PASS: night skips, RO/FR publication windows, overlapping jobs, recent checks, winter DST'

$before=[DateTimeOffset]::Parse('2026-10-18T04:29:00Z')
if((Get-DispatchDecision $before @()) -ne 'OUTSIDE_WINDOW'){throw 'before opening'}
$start=[DateTimeOffset]::Parse('2026-10-18T04:30:00Z')
if((Get-DispatchDecision $start @()) -ne 'DISPATCH'){throw 'opening boundary'}
$gap=[DateTimeOffset]::Parse('2026-10-18T05:00:00Z')
if((Get-DispatchDecision $gap @()) -ne 'OUTSIDE_WINDOW'){throw 'hourly gap'}
if((Get-DispatchDecision $active @(@{status='completed';created_at='2026-10-18T05:27:00Z'})) -ne 'DISPATCH'){throw 'ten minute retry boundary'}
$fall=[DateTimeOffset]::Parse('2026-10-25T05:30:00Z')
if((Get-DispatchDecision $fall @()) -ne 'DISPATCH'){throw 'DST transition day'}
foreach($file in Get-ChildItem $PSScriptRoot -Filter '*.ps1') {
 $tokens=$null; $errors=$null
 [System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$errors) | Out-Null
 if($errors.Count){throw ('PowerShell syntax error: '+$file.Name)}
}
'PASS: boundaries, retry interval, DST transition and all PowerShell script syntax'
