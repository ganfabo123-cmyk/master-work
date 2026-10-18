$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Remove-Item -LiteralPath (Join-Path $root 'build') -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force (Join-Path $root 'build') | Out-Null
Write-Output 'epilog fixture reset'
