$env:FIXTURE_BUILD_FAILURE = '1'
node (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'frontend\build.js')
exit $LASTEXITCODE
