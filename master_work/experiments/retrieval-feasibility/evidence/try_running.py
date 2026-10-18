import subprocess,json
from pathlib import Path
root=Path(__file__).resolve().parents[3]
p=subprocess.Popen([str(root/'experiments/retrieval-feasibility/fixtures/epilog/baseline/epilog.exe')],cwd=root/'experiments/retrieval-feasibility/fixtures/epilog/baseline',stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
(root/'experiments/retrieval-feasibility/evidence/epilog-baseline-state.json').write_text(json.dumps({'process_pid':p.pid}),encoding='utf8')
import time
time.sleep(45)
