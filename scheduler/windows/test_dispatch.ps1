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
