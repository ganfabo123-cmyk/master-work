param([ValidateSet('native','controlled','experiment')][string]$Mode = 'experiment')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Mode -eq 'experiment') {
  & (Join-Path $root 'build.ps1') -Mode native
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
  & (Join-Path $root 'inject_failure.ps1')
  exit 1
}
& (Join-Path $root 'build.ps1') -Mode $Mode
if ($Mode -eq 'controlled') { exit 1 }
Get-Content (Join-Path $root 'query.txt') | & (Join-Path $root 'build\epilog.exe')
exit $LASTEXITCODE
