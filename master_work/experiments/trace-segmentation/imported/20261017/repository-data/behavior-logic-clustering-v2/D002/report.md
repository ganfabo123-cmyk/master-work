# D002 behavior clustering

Slices: 43

## Target clusters

Clusters: 14; residual: 1

- `target-01` (3): filetype:.py, json, op:read, py, tool:read, user, __init__, __version__, actually, add
- `target-02` (2): _iconsvg, app, both, bundled, call, changed, check, clean, clock, content
- `target-03` (3): already, app, binding, calls, carefully, change, check, clean, content, cpu
- `target-04` (3): asm, boot, cfg, change, check, command, entry, filetype:.asm, filetype:.c, filetype:.cfg
- `target-05` (6): add, after, already, before, both, check, command, dev, echo, everything
- `target-06` (4): agent, anonymity, anyone, anything, asking, base, before, both, briefly, cd
- `target-07` (3): add, adding, batch, completed, cpp, current, dev, entry, file, files
- `target-08` (2): about, across, add, after, already, api, app, appcontext, apply, approach
- `target-09` (3): across, adaptive, adapts, adding, alive, already, api, applicable, approach, base
- `target-10` (2): actual, actually, add, after, again, already, approach, assert, atoms, avoid
- `target-11` (3): bin, binary, boot, clean, code, complete, config, doesn, etc, everything
- `target-12` (2): add, after, allocator, already, api, approach, arg, around, because, before
- `target-13` (4): add, already, android, apk, attach, before, cat, cd, check, clean
- `target-14` (2): activity, add, added, after, against, android, api, apply, approach, author

## Logic clusters

Clusters: 2; residual: 1

- `logic-01` (22): U → A → T:list → T:read → A → T:list → T:read → A → T:list → T:read → A → T:edit → A → T:edit → A → T:read → A → U → A → T:list → A → T:write → A → T:edit → A → T:list → T:read → A → T:edit → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → U → A → T:read → A → T:write → A → T:write → A → T:read → A → T:write → A → T:write → A → T:write → A → T:read → A → T:edit → A
- `logic-02` (20): T:read → T:write → H → A → T:read → T:edit → A → U → H → A → T:git:other → T:list → T:read → H → A → T:search → T:read → H → A → H → A → T:read → T:list → T:read → H → A → T:create → T:copy → T:run:python → T:read → A → T:run:python → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:run:python → H → A → T:run:python → H → A → H → A → T:read → H → A → T:run:python → H → A → H → A → H

## Cannot-link

Target p10: 0.00726943; logic p10: 0.06958708; edges: 14

