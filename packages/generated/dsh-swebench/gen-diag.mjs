// Diagnostic: generate the built-lib eval scripts for one django case into a
// fixed host dir so the docker run can mount and execute them exactly like
// swb_eval does. NOT part of the shipped plugin.
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { buildEvalLauncher, buildEvaluator } from './lib/scripts.js'
import { runnerForInstance } from './lib/cases.js'

const instanceId = process.argv[2] ?? 'django__django-10924'
const runner = runnerForInstance(instanceId)
const dir = new URL('./.diag/', import.meta.url).pathname.replace(/^\/([A-Za-z]):/, '$1:/')
mkdirSync(dir, { recursive: true })
writeFileSync(join(dir, 'run.sh'), buildEvalLauncher(), 'utf8')
writeFileSync(join(dir, 'evaluator.py'), buildEvaluator(instanceId, runner), 'utf8')
console.log(`written ${instanceId} (${runner}) to`, dir)