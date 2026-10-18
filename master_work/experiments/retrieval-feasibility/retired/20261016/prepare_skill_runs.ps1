param(
  [string]$WorkspaceRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path,
  [string]$ManagementRoot = "$WorkspaceRoot\experiments\skill-management\skill-management-system",
  [string]$RunsRoot = "$WorkspaceRoot\experiments\skill-management\runs"
)

$sourceData = Join-Path $ManagementRoot 'data'
$sourceConfig = Join-Path $ManagementRoot 'config.json'
if (!(Test-Path -LiteralPath $sourceData) -or !(Test-Path -LiteralPath $sourceConfig)) {
  throw "skill-management-system data/config not found under $ManagementRoot"
}

New-Item -ItemType Directory -Force -Path $RunsRoot | Out-Null
foreach ($fixture in @('epilog', 'iceberg', 'mydatabase')) {
  $runName = "$fixture-managed"
  $runRoot = Join-Path $RunsRoot $runName
  $runData = Join-Path $runRoot 'data'
  $runConfig = Join-Path $runRoot 'config.json'
  New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
  if (!(Test-Path -LiteralPath $runData)) {
    Copy-Item -LiteralPath $sourceData -Destination $runData -Recurse
  }
  $config = Get-Content -LiteralPath $sourceConfig -Raw | ConvertFrom-Json
  $config.corpus_root = (Join-Path $WorkspaceRoot 'experiments\skill-management\dynamic-retrieval-test\skills_b')
  $config.index_path = (Join-Path $WorkspaceRoot 'dynamic-retrieval-test\skills_b\index.jsonl')
  $config.embedding_cache = (Join-Path $WorkspaceRoot 'experiments\skill-management\dynamic-retrieval-test\embedding_cache.json')
  $config.data_dir = $runData
  $json = $config | ConvertTo-Json -Depth 20
  [IO.File]::WriteAllText($runConfig, $json + [Environment]::NewLine, [Text.UTF8Encoding]::new($false))
  Write-Output "prepared ${runName}: $runConfig"
}
