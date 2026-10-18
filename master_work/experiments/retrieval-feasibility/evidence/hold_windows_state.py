"""Hold real Windows resources while experiments run; never emits tool errors.

Run by the experiment preparer, outside all agent workspaces.
"""
import ctypes
from ctypes import wintypes
import json
import mmap
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
kind, arm = sys.argv[1:3]
workspace = ROOT/'experiments/retrieval-feasibility/fixtures'/kind/arm
state_file = ROOT/'experiments/retrieval-feasibility/evidence'/f'{kind}-{arm}-state.json'
if kind == 'epilog':
    child = subprocess.Popen([str(workspace/'epilog.exe')],cwd=workspace,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    time.sleep(.5)
    if child.poll() is not None:
        raise RuntimeError(f'Epilog exited: {child.returncode}')
    state_file.write_text(json.dumps({'holder_pid':os.getpid(),'process_pid':child.pid,'executable':str(workspace/'epilog.exe')}),encoding='utf-8')
    while child.poll() is None:
        time.sleep(1)
elif kind == 'iceberg':
    target = workspace/'.react-router/types/app/routes/+types'
    target.mkdir(parents=True,exist_ok=True)
    kernel = ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.SetFileInformationByHandle.argtypes = [wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD]
    handle = kernel.CreateFileW(str(target),0x10000,7,None,3,0x02000000,None)
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    disposition = wintypes.BOOL(True)
    if not kernel.SetFileInformationByHandle(handle,4,ctypes.byref(disposition),ctypes.sizeof(disposition)):
        raise ctypes.WinError(ctypes.get_last_error())
    state_file.write_text(json.dumps({'holder_pid':os.getpid(),'directory':str(target),'state':'delete-pending'}),encoding='utf-8')
    while True:
        time.sleep(1)
