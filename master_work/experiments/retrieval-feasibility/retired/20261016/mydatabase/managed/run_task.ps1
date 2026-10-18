param([ValidateSet('success','missing-database','missing-page','build-failure')][string]$Mode = 'missing-page')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if ($Mode -eq 'build-failure') {
  $env:FIXTURE_BUILD_FAILURE = '1'
  node (Join-Path $root 'frontend\build.js')
  exit $LASTEXITCODE
}
$proc = Start-Process -FilePath node -ArgumentList (Join-Path $root 'backend\server.js') -PassThru -WindowStyle Hidden
try {
  Start-Sleep -Milliseconds 300
  $url = if ($Mode -eq 'success') { 'http://127.0.0.1:3317/db/orv/pages/slug/Kim_Dokja' } elseif ($Mode -eq 'missing-database') { 'http://127.0.0.1:3317/db/missing/pages' } else { 'http://127.0.0.1:3317/db/orv/pages/slug/missing' }
  & curl.exe --silent --show-error --write-out "`nstatus=%{http_code}`n" $url
  if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
  Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
}
