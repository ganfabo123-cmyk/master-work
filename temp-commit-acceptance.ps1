$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$acceptanceRepoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $acceptanceRepoRoot

function Assert-GitSuccess {
  param([Parameter(Mandatory = $true)][string]$Operation)

  if ($LASTEXITCODE -ne 0) {
    throw "$Operation failed with exit code $LASTEXITCODE."
  }
}

$acceptanceBranch = git branch --show-current
Assert-GitSuccess 'Read current branch'
Write-Host "Branch: $acceptanceBranch"

# Rebuild only the index. Working-tree files and untracked files are untouched.
git restore --staged :/
Assert-GitSuccess 'Clear staged changes'

$acceptanceFiles = @(
  'apps/cli/src/acceptance.ts'
  'apps/cli/src/args.ts'
  'apps/cli/src/bin.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/acceptance.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/config.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/services/acceptance-composition.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/services/acceptance-service.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/tools/start-acceptance.ts'
  'packages/examples/jsonrpc-demo/package.json'
  'packages/examples/jsonrpc-demo/src/runner.ts'
)

git add -- $acceptanceFiles
Assert-GitSuccess 'Stage acceptance files'

$acceptancePartialPatch = @'
diff --git a/packages/cordis_sub_agent/cordis_sub_agent/package.json b/packages/cordis_sub_agent/cordis_sub_agent/package.json
--- a/packages/cordis_sub_agent/cordis_sub_agent/package.json
+++ b/packages/cordis_sub_agent/cordis_sub_agent/package.json
@@ -17,6 +17,10 @@
       "types": "./lib/index.d.ts",
       "default": "./lib/index.js"
     },
+    "./acceptance": {
+      "types": "./lib/acceptance.d.ts",
+      "default": "./lib/acceptance.js"
+    },
     "./src/*": "./src/*",
     "./package.json": "./package.json"
   },
diff --git a/packages/cordis_sub_agent/cordis_sub_agent/src/index.ts b/packages/cordis_sub_agent/cordis_sub_agent/src/index.ts
--- a/packages/cordis_sub_agent/cordis_sub_agent/src/index.ts
+++ b/packages/cordis_sub_agent/cordis_sub_agent/src/index.ts
@@ -102,7 +102,6 @@ export function apply(
       ctx.tools.register(
         startAcceptanceTool(
           acceptance,
-          metadataTasks,
           {
             repoRoot:
               resolve(config.repoRoot),
diff --git a/tsconfig.host.json b/tsconfig.host.json
--- a/tsconfig.host.json
+++ b/tsconfig.host.json
@@ -276,6 +276,7 @@
     { "path": "./packages/preset/persona" },
     { "path": "./packages/preset/think-zh" },
     { "path": "./packages/memory/memory" },
+    { "path": "./packages/cordis_sub_agent/cordis_sub_agent" },
     { "path": "./packages/guard/repeat-tool-reminder" },
     { "path": "./packages/extensions/cordis-host-runner" },
     { "path": "./packages/extensions/tool-cordis" },
diff --git a/tsdown.config.ts b/tsdown.config.ts
--- a/tsdown.config.ts
+++ b/tsdown.config.ts
@@ -16,7 +16,14 @@ function isBuildFaceClient(value: unknown): boolean {
 export default defineConfig(({ env }) => {
   const client = isBuildFaceClient(env?.DSH_BUILD_FACE)
   return {
-    workspace: ['vendor/*', 'packages/*/*', 'apps/cli'],
+    // cordis_sub_agent is a standalone plugin with a package-local lib/index.js
+    // entry, not a standard lib/types/* aggregate package.
+    workspace: [
+      'vendor/*',
+      'packages/*/*',
+      'apps/cli',
+      '!packages/cordis_sub_agent/cordis_sub_agent',
+    ],
     entry: client ? '' : ['lib/types/{index,invariant,startup}.js'],
     outDir: 'lib',
     format: ['esm'],
diff --git a/pnpm-lock.yaml b/pnpm-lock.yaml
--- a/pnpm-lock.yaml
+++ b/pnpm-lock.yaml
@@ -3927,9 +3927,21 @@ importers:
 
   packages/examples/jsonrpc-demo:
     dependencies:
+      '@deepseek-ai/dsh-agent-spine-demo':
+        specifier: workspace:^
+        version: link:../agent-spine-demo
       '@deepseek-ai/dsh-app-boot':
         specifier: workspace:^
         version: link:../../boot/app-boot
+      '@deepseek-ai/dsh-llm-deepseek':
+        specifier: workspace:^
+        version: link:../../llm/llm-deepseek
+      '@deepseek-ai/dsh-llm-pi-ai':
+        specifier: workspace:^
+        version: link:../../llm/llm-pi-ai
+      '@deepseek-ai/dsh-sdk-jsonrpc-server':
+        specifier: workspace:^
+        version: link:../../sdk/server
     devDependencies:
       '@deepseek-ai/cordis':
         specifier: workspace:^
'@

$acceptancePartialPatch | git apply --cached --whitespace=nowarn -
Assert-GitSuccess 'Stage acceptance-only hunks'

$expectedStagedFiles = @(
  'apps/cli/src/acceptance.ts'
  'apps/cli/src/args.ts'
  'apps/cli/src/bin.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/package.json'
  'packages/cordis_sub_agent/cordis_sub_agent/src/acceptance.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/config.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/index.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/services/acceptance-composition.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/services/acceptance-service.ts'
  'packages/cordis_sub_agent/cordis_sub_agent/src/tools/start-acceptance.ts'
  'packages/examples/jsonrpc-demo/package.json'
  'packages/examples/jsonrpc-demo/src/runner.ts'
  'pnpm-lock.yaml'
  'tsconfig.host.json'
  'tsdown.config.ts'
)

$actualStagedFiles = @(git diff --cached --name-only)
Assert-GitSuccess 'Read staged files'

$unexpectedStagedFiles = @($actualStagedFiles | Where-Object { $_ -notin $expectedStagedFiles })
$missingStagedFiles = @($expectedStagedFiles | Where-Object { $_ -notin $actualStagedFiles })
if ($unexpectedStagedFiles.Count -ne 0 -or $missingStagedFiles.Count -ne 0) {
  Write-Host 'Unexpected staged files:'
  $unexpectedStagedFiles | ForEach-Object { Write-Host "  $_" }
  Write-Host 'Missing staged files:'
  $missingStagedFiles | ForEach-Object { Write-Host "  $_" }
  throw 'Staged file set does not match the acceptance commit scope.'
}

git diff --cached --check
Assert-GitSuccess 'Check staged diff'

Write-Host ''
Write-Host 'Staged files:'
git diff --cached --name-status
Assert-GitSuccess 'Show staged files'

Write-Host ''
git diff --cached --stat
Assert-GitSuccess 'Show staged summary'

git commit -m 'feat(cordis-sub-agent): run acceptance from Cordis patches'
Assert-GitSuccess 'Create acceptance commit'

Write-Host ''
git log -1 --oneline
Assert-GitSuccess 'Show created commit'
Write-Host ''
Write-Host 'Remaining working-tree changes were not committed:'
git status --short
Assert-GitSuccess 'Show remaining working-tree changes'
