# -*- coding: utf-8 -*-
import json, sys
f=r"D:\PycharmProjects\CodeHarness\master_work\data\raw\agent-traces\sessions\claude_code\7563bddf-c1a0-4c3e-86ee-062bf288e6d3.jsonl"
lines=open(f,encoding='utf-8',errors='replace').read().splitlines()
for n in [107,123,148,194,238,253,499,502,507,516,574,578,711,815]:
    j=json.loads(lines[n-1])
    print(n, j.get('timestamp'), j.get('type'))
