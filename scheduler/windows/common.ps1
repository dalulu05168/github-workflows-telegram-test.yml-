$repository = 'dalulu05168/github-workflows-telegram-test.yml-'
function Resolve-GitHubCLI {
    $portable = Join-Path $PSScriptRoot 'bin/gh.exe'
    if (Test-Path $portable) { return $portable }
    $installed = Get-Command gh -ErrorAction SilentlyContinue
    if ($installed) { return $installed.Source }
    throw 'GitHub CLI not found. Extract the complete package including bin/gh.exe.'
}
function Write-DispatcherStatus([string]$Message) {
    $dir = Join-Path $PSScriptRoot 'logs'
    New-Item -ItemType Directory -Path $dir -Force | Out-Null
    $file = Join-Path $dir 'dispatcher.log'
    if ((Test-Path $file) -and (Get-Item $file).Length -gt 1048576) {
        Move-Item $file (Join-Path $dir 'dispatcher.previous.log') -Force
    }
    $line = [DateTimeOffset]::UtcNow.ToString('o') + ' ' + $Message
    Add-Content -LiteralPath $file -Value $line -Encoding UTF8
    Write-Output $line
}
