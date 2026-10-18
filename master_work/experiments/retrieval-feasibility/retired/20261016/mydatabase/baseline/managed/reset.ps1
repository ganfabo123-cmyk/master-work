$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Remove-Item -LiteralPath (Join-Path $root 'dist') -Recurse -Force -ErrorAction SilentlyContinue
Write-Output 'mydatabase fixture reset'
