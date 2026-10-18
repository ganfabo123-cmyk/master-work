"""Prepare source-backed replacements; never runs inside agent workspaces."""
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[3]

def blocks(r):
    c = r.get('message',{}).get('content',[])
    return c if isinstance(c,list) else []

def snapshot(tid,prefix,stop,extensions=None):
    rows=[json.loads(s) for s in (ROOT/'data/raw/agent-traces/sessions/claude_code'/f'{tid}.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
    results={b['tool_use_id']:b for r in rows for b in blocks(r) if b.get('type')=='tool_result' and 'tool_use_id' in b}
    files={}; provenance={}
    for i,r in enumerate(rows[:stop]):
        for b in blocks(r):
            if b.get('type')!='tool_use':continue
            a=b.get('input',{}); p=re.sub('/+','/',a.get('file_path','').replace('\\','/'))
            if not p.lower().startswith(prefix.lower()):continue
            rel=p[len(prefix):]
            if extensions and Path(rel).suffix not in extensions:continue
            result=results.get(b['id'],{})
            if not result or result.get('is_error') or 'tool_use_error' in str(result.get('content','')):continue
            if b['name']=='Write':files[rel]=a['content']
            elif b['name']=='Edit':
                if rel not in files:raise ValueError(f'No base for {rel}:{i+1}')
                if a['old_string'] not in files[rel]:raise ValueError(f'Edit mismatch {rel}:{i+1}')
                files[rel]=files[rel].replace(a['old_string'],a['new_string'],-1 if a.get('replace_all') else 1)
            else:continue
            provenance.setdefault(rel,[]).append({'line':i+1,'operation':b['name']})
    return files,provenance,rows,results

def save(name,files,provenance,tid,line):
    for arm in ('baseline','managed'):
        base=ROOT/'experiments/retrieval-feasibility/fixtures'/name/arm
        for rel,content in files.items():
            p=base/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(content,encoding='utf8',newline='\n')
    (ROOT/'experiments/retrieval-feasibility/evidence'/f'{name}-sources.json').write_text(json.dumps({'trace_id':tid,'failure_line':line,'files':provenance},indent=2),encoding='utf8')


def main():
    tid='c99032e9-377b-4ae9-a9a9-ec7752b059cd'
    files,prov,rows,results=snapshot(tid,'d:/Epilog/',945,{'.cpp','.hpp'})
    files['build.bat']='@echo off\nif not exist build\\tests mkdir build\\tests\nclang++ -std=c++23 -Wall -Wextra -Wpedantic -Iinclude -Itests -g -O0 internals/atoms.cpp internals/variables.cpp internals/terms.cpp parser/lexer.cpp parser/parser.cpp engine/database.cpp engine/unifier.cpp engine/builtins.cpp engine/solver.cpp repl.cpp tests/test_atoms.cpp -o build/tests/test_atoms.exe\nif errorlevel 1 exit /b %errorlevel%\nbuild\\tests\\test_atoms.exe\n'
    files['README.md']='# Epilog tests\n\n`./build.bat` compiles and runs the atom table tests.\n'
    save('epilog-tests',files,prov,tid,947)
    
    tid='4130c9a7-ee88-443a-91b5-224accd13629'
    files,prov,rows,results=snapshot(tid,'d:/CODSOFT/JOB_BOARD/frontend/',216)
    def shell_result(command):
        for r in rows:
            for b in blocks(r):
                if b.get('type')=='tool_use' and b.get('input',{}).get('command')==command:
                    return results[b['id']]['content']
        raise ValueError(command)
    files['package.json']=shell_result('cat d:/CODSOFT/JOB_BOARD/frontend/package.json')
    files['src/router.tsx']=shell_result('ls d:/CODSOFT/JOB_BOARD/frontend/src/routes && cat d:/CODSOFT/JOB_BOARD/frontend/src/router.tsx').split('import ',1)[1]
    files['src/router.tsx']='import '+files['src/router.tsx']
    files['vite.config.ts']=shell_result('cat d:/CODSOFT/JOB_BOARD/frontend/vite.config.ts && cat d:/CODSOFT/JOB_BOARD/frontend/src/styles.css').split('\n@import ',1)[0]
    # tsconfig is not present in the trace; preserve the options proven by diagnostics.
    files['tsconfig.json']=json.dumps({'compilerOptions':{'target':'ES2022','lib':['ES2022','DOM','DOM.Iterable'],'module':'ESNext','moduleResolution':'bundler','jsx':'react-jsx','strict':True,'skipLibCheck':True,'esModuleInterop':True,'allowImportingTsExtensions':True,'resolveJsonModule':True,'noEmit':True,'verbatimModuleSyntax':True,'noUnusedLocals':True,'noUnusedParameters':True,'types':['vite/client'],'paths':{'#/*':['./src/*']}},'include':['src']},indent=2)
    files['README.md']='# Job Board frontend\n\n`npx tsc --noEmit` checks the frontend. `npm run dev` starts development.\n'
    save('job-board',files,prov,tid,218)
    print('Restored Epilog test and Job Board source snapshots')

if __name__ == "__main__":
    main()
