/**
 * In-container script templates of @deepseek-ai/dsh-swebench. Every tool run
 * generates a bash launcher (and, for eval, a Python evaluator) into the run
 * directory; the launcher is the container entry that copies the host repo
 * into `/testbed`, activates the `testbed` conda environment, and either runs
 * the model command (swb_run) or applies the official test patch and runs the
 * FAIL_TO_PASS / PASS_TO_PASS nodes one by one (swb_eval). All template
 * interpolation happens here with fixed plugin-owned values; model-supplied
 * text (the command) travels as its own file so it can never break the
 * launcher.
 * @module @deepseek-ai/dsh-swebench/scripts
 */

import { CONDA_ACTIVATE, TESTBED } from './docker.js'
import type { CaseRunner } from './cases.js'

/** Marker line prefix the evaluator uses to emit its structured verdict. */
export const EVAL_RESULT_MARKER = 'SWE_EVAL_RESULT'

/** The fixed dataset URL the evaluator fetches inside the container. */
export const DATASET_URL = 'https://datasets-server.huggingface.co/rows?dataset=SWE-bench%2FSWE-bench_Lite&config=default&split=test&offset=0&length=10'

/**
 * Bash launcher for `swb_run`: copy the host repo into `/testbed` (excluding
 * the Windows worktree `.git` pointer), activate the case conda environment,
 * cd into the requested workdir, and execute the model command from
 * `/sweb/command.sh`. The command script is executed with `bash` so a
 * multi-line command keeps its own quoting.
 * @param workdir - in-container working directory for the command.
 * @returns the launcher bash text.
 */
export function buildRunLauncher(workdir: string): string {
  return [
    '#!/bin/bash',
    'set -uo pipefail',
    `tar --exclude=.git -C /host-testbed -cf - . | tar -C ${TESTBED} -xf - || { echo "SWE_RUN: repo copy failed" >&2; exit 90; }`,
    `cd ${TESTBED}`,
    `source ${CONDA_ACTIVATE}`,
    'conda activate testbed',
    `cd ${workdir} || { echo "SWE_RUN: workdir ${workdir} does not exist" >&2; exit 91; }`,
    'bash /sweb/command.sh',
  ].join('\n')
}

/**
 * The evaluator script for `swb_eval`. Runs entirely inside the container with
 * `curl` + Python (the host cannot reach the dataset endpoint; the container
 * can). It reads the dataset row, applies the official `test_patch` to
 * `/testbed` with `git apply --no-index` after CRLF defense, runs every
 * FAIL_TO_PASS and PASS_TO_PASS node through the case runner, and prints one
 * `SWE_EVAL_RESULT <json>` line as the last output. `curl` output stays in
 * the container; the verdict carries only counts and failing test names.
 * @param instanceId - the case to evaluate.
 * @param runner - the case's official test runner.
 * @returns the evaluator python text.
 */
export function buildEvaluator(instanceId: string, runner: CaseRunner): string {
  const runTests = runner === 'runtests'
    ? `def run_tests(nodes):
    # Django batch mode mirrors the official eval script: one runtests.py
    # invocation over the deduplicated module labels of every node's
    # (module.Class) part, then per-node verdicts are parsed from the
    # verbosity-2 output ('FAIL:'/'ERROR:' block headers, '<node> ... ok'
    # success lines). The dataset node form 'test_x (module.Class)' matches
    # both output shapes verbatim. 'python tests/runtests.py' is used
    # instead of './tests/runtests.py' because the Windows-checked-out host
    # repo carries CRLF line endings and the script's shebang would break
    # with a trailing '\\r'.
    import re
    modules = []
    for node in nodes:
        m = re.match(r'^[\\w_]+ \\(([\\w.]+)\\)$', node)
        module = m.group(1).rsplit('.', 1)[0] if m else node
        if module not in modules:
            modules.append(module)
    verdict = {'total': len(nodes), 'passed': 0, 'failed': []}
    try:
        result = subprocess.run(
            ['python', 'tests/runtests.py', '--verbosity', '2', '--settings=test_sqlite', '--parallel', '1'] + modules,
            cwd='/testbed', stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            universal_newlines=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        verdict['failed'] = list(nodes)
        return verdict
    text = (result.stdout if result.stdout else '') + '\\n' + (result.stderr if result.stderr else '')
    failed = set()
    for line in text.splitlines():
        line = line.rstrip()
        if line.startswith('FAIL:') or line.startswith('ERROR:'):
            failed.add(line.split(':', 1)[1].strip())
    passed = set()
    for line in text.splitlines():
        line = line.rstrip()
        if line.endswith(' ... ok'):
            passed.add(line[:line.rfind(' ...')].strip())
    for node in nodes:
        if node in failed:
            verdict['failed'].append(node)
        elif node in passed:
            verdict['passed'] += 1
        else:
            # A node that produced neither an ok line nor a FAIL/ERROR header
            # (e.g. a collection error aborted the batch) counts as failed,
            # so a resolved verdict can never be overstated.
            verdict['failed'].append(node)
    return verdict`
    : `def run_tests(nodes):
    verdict = {'total': len(nodes), 'passed': 0, 'failed': []}
    for node in nodes:
        try:
            result = subprocess.run(['pytest', '-q', node], cwd='/testbed',
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    universal_newlines=True, timeout=600)
            ok = result.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        if ok:
            verdict['passed'] += 1
        else:
            verdict['failed'].append(node)
    return verdict`

  return `import json, os, re, subprocess, sys

DATASET_URL = ${JSON.stringify(DATASET_URL)}
INSTANCE_ID = ${JSON.stringify(instanceId)}

def fetch_row():
    # curl is the one TLS-capable client in these images; python urllib fails
    # on their SSL stack, so download with curl and parse the local file.
    subprocess.run(['curl', '-sS', '-m', '120', DATASET_URL, '-o', '/tmp/ds.json'], check=True)
    data = json.load(open('/tmp/ds.json'))
    for entry in data['rows']:
        if entry['row']['instance_id'] == INSTANCE_ID:
            return entry['row']
    raise SystemExit('SWE_EVAL_ERROR: instance not found in dataset rows')

def apply_test_patch(row):
    patch = row['test_patch']
    open('/tmp/test.patch', 'w').write(patch)
    files = re.findall(r'^diff --git a/(\\S+) b/', patch, re.M)
    for rel in files:
        path = os.path.join('/testbed', rel)
        if os.path.isfile(path):
            subprocess.run(['sed', '-i', 's/\\r$//', path], check=False)
    # py3.6 has no capture_output/text keywords; collect through PIPE like
    # every other in-container subprocess call.
    applied = subprocess.run(['git', 'apply', '--no-index', '/tmp/test.patch'], cwd='/testbed', stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    if applied.returncode != 0:
        raise SystemExit('SWE_EVAL_ERROR: test patch apply failed\\n' + applied.stderr[-2000:])

${runTests}

def main():
    row = fetch_row()
    apply_test_patch(row)
    fail_to_pass = run_tests(row['FAIL_TO_PASS'])
    pass_to_pass = run_tests(row['PASS_TO_PASS'])
    resolved = fail_to_pass['failed'] == [] and pass_to_pass['failed'] == []
    summary = {
        'fail_to_pass': fail_to_pass,
        'pass_to_pass': pass_to_pass,
        'resolved': resolved,
    }
    print('${EVAL_RESULT_MARKER} ' + json.dumps(summary))

main()
`
}

/**
 * Bash launcher for `swb_eval`: copy the host repo into `/testbed`, set the
 * locale the Django images need, run the Python evaluator, and propagate its
 * exit code. The evaluator's stdout (including the result marker) is the
 * launcher's stdout.
 * @returns the launcher bash text.
 */
export function buildEvalLauncher(): string {
  return [
    '#!/bin/bash',
    'set -uo pipefail',
    `tar --exclude=.git -C /host-testbed -cf - . | tar -C ${TESTBED} -xf - || { echo "SWE_EVAL: repo copy failed" >&2; exit 90; }`,
    'cd /testbed',
    // Django's locale handling mirrors the official eval script.
    "sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen 2>/dev/null || true",
    'locale-gen >/dev/null 2>&1 || true',
    'export LANG=en_US.UTF-8 LANGUAGE=en_US:en LC_ALL=en_US.UTF-8',
    `source ${CONDA_ACTIVATE}`,
    'conda activate testbed',
    'python /sweb/evaluator.py',
  ].join('\n')
}
