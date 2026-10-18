"""Run normal project commands and compare with the original failure signatures."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT/'experiments/retrieval-feasibility/evidence'
SPECS = {
    'epilog-tests': ('c99032e9-377b-4ae9-a9a9-ec7752b059cd', 946, ["redefinition of '_reg___LINE__'", "redefinition of '_test_body___LINE__'", '17 errors generated.'], ['cmd.exe','/d','/c','build.bat']),
    'job-board': ('4130c9a7-ee88-443a-91b5-224accd13629', 217, ['TS1484','TS6133','TS2554'], ['cmd.exe','/d','/c','npx.cmd tsc --noEmit']),
    'epilog-solver': ('c99032e9-377b-4ae9-a9a9-ec7752b059cd', 1127, ["expected '.', got operator '.'", '18/22 tests passed  (4 FAILED)'], ['cmd.exe','/d','/c','build.bat']),
}

def check(name, arm):
    tid, row, expected, command = SPECS[name]
    cwd = ROOT/'experiments/retrieval-feasibility/fixtures'/name/arm
    rows = [json.loads(s) for s in (ROOT/'data/raw/agent-traces/sessions/claude_code'/f'{tid}.jsonl').read_text(encoding='utf-8').splitlines() if s.strip()]
    original = next(b['content'] for b in rows[row]['message']['content'] if b.get('type') == 'tool_result')
    (EVIDENCE/f'{name}-original-error.txt').write_text(original,encoding='utf-8')
    attempts = []
    for attempt in range(1, 4):
        env = dict(os.environ)
        env['PATH'] = str(EVIDENCE/'runtime/node_modules/node/bin')+os.pathsep+env['PATH']
        process = subprocess.Popen(command,cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        timed_out = False
        try:
            raw, _ = process.communicate(timeout=12)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            raw, _ = process.communicate(timeout=10)
        output = raw.decode('utf-8',errors='replace')
        log = EVIDENCE/f'{name}-{arm}-attempt-{attempt}.log'
        log.write_text(output,encoding='utf-8')
        matched = not timed_out and process.returncode != 0 and all(s in output for s in expected)
        diagnostics_equal = None
        comparison_scope = None
        if name == 'job-board':
            diagnostics = lambda text: [line.strip() for line in text.splitlines() if re.search(r'error TS\d+:',line)]
            diagnostics_equal = diagnostics(output) == diagnostics(original) and len(diagnostics(original)) == 14
            comparison_scope = 'All 14 original TypeScript diagnostics, including location, code and text.'
        elif name == 'epilog-tests':
            diagnostics = lambda text: re.findall(r"test_atoms.cpp:(\d+):(\d+): error: (redefinition of '[^']+')",text)
            original_diagnostics = diagnostics(original)
            actual_diagnostics = diagnostics(output)
            diagnostics_equal = len(original_diagnostics) == 6 and actual_diagnostics[:6] == original_diagnostics and len(actual_diagnostics) == 17
            comparison_scope = 'Original trace truncates compiler output: all 6 recorded atom-test diagnostics match exactly; local compiler emits 17. Remaining original diagnostics are unavailable.'
        elif name == 'epilog-solver':
            clean = lambda text: re.sub(r'\x1b\[[0-9;]*m', '', text)
            diagnostics = lambda text: re.findall(r'\[load\] parse error[^\r\n]+',clean(text))
            debug = '[DEBUG two-body] loaded=-1 db.clause_count=1 db.pred_count=1 arena.count=6'
            diagnostics_equal = len(diagnostics(original)) == 3 and diagnostics(output) == diagnostics(original) and debug in output and debug in clean(original)
            comparison_scope = 'All three original parser error lines and the original debug state match, after removing ANSI highlighting; the full test run also contains the original separate assert test failure.'
        if diagnostics_equal is not None:
            matched = matched and diagnostics_equal
        attempts.append({'attempt':attempt,'exit_code':process.returncode,'timed_out':timed_out,'matches_original_target':matched,'recorded_target_diagnostics_equal':diagnostics_equal,'comparison_scope':comparison_scope,'log':str(log)})
    return {'fixture':name,'arm':arm,'command':command,'cwd':str(cwd),'original_trace':tid,'original_line':row+1,'required_error_fragments':expected,'attempts':attempts,'verdict':'PASS' if all(a['matches_original_target'] for a in attempts) else 'FAIL'}

def manifest(name, arm):
    base = ROOT/'experiments/retrieval-feasibility/fixtures'/name/arm
    result = {}
    for path in base.rglob('*'):
        if not path.is_file():
            continue
        rel = path.relative_to(base)
        if any(p in ('node_modules','.react-router','.svelte-kit','build') for p in rel.parts) or rel.name == 'skill-runtime-hint.cordis.yml' or path.suffix in ('.exe','.ilk','.pdb','.o','.obj'):
            continue
        result[rel.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result

if __name__ == '__main__':
    pairs = [(name,arm) for name in SPECS for arm in ('baseline','managed')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda pair:check(*pair),pairs))
    equality = {name:manifest(name,'baseline') == manifest(name,'managed') for name in SPECS}
    report = {'results':results,'paired_source_hashes_equal':equality,'overall':'PASS' if all(r['verdict']=='PASS' for r in results) and all(equality.values()) else 'FAIL'}
    (EVIDENCE/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    for r in results:
        print(r['fixture'],r['arm'],r['verdict'],[a['exit_code'] for a in r['attempts']])
    print('paired_source_hashes_equal',equality)
    print('overall',report['overall'])
