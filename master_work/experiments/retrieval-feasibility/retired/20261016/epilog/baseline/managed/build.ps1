param([ValidateSet('native','controlled')][string]$Mode = 'controlled')
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$build = Join-Path $root 'build'
New-Item -ItemType Directory -Force $build | Out-Null
if ($Mode -eq 'controlled') {
  & (Join-Path $root 'inject_failure.ps1')
  exit 1
}
$compiler = Get-Command clang++ -ErrorAction Stop
& $compiler.Source (Join-Path $root 'src\main.cpp') '-std=c++17' '-Wall' '-Wextra' '-o' (Join-Path $build 'epilog.exe')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output "native build: $build\epilog.exe"
