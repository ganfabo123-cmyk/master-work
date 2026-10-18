param([ValidateSet('success','controlled-failure')][string]$Mode = 'controlled-failure')
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Mode -eq 'controlled-failure') {
  $env:FIXTURE_BUILD_FAILURE = '1'
  node (Join-Path $root 'build.js')
  exit $LASTEXITCODE
}
Remove-Item Env:FIXTURE_BUILD_FAILURE -ErrorAction SilentlyContinue
node (Join-Path $root 'build.js')
exit $LASTEXITCODE
