# D002 behavior clustering

Slices: 43

## Target clusters

Clusters: 14; residual: 1

- `target-01` (3): filetype:.py, op:read, py, tool:read, __init__, __version__, additions, availability, block, catch
- `target-02` (2): _iconsvg, bundled, changed, clock, core, creates, dist, dom, element, elements
- `target-03` (3): binding, carefully, cpu, goes, htop, js, op:edit, op:read, pattern, refresh
- `target-04` (3): asm, boot, cfg, command, entry, filetype:.asm, filetype:.c, filetype:.cfg, filetype:.h, filetype:makefile
- `target-05` (6): command, interrupted, op:edit, op:read, op:search, op:write, request, shell, tool:bash, tool:edit
- `target-06` (4): agent, anonymity, anyone, anything, asking, base, briefly, chosen, cleaned, coding
- `target-07` (3): adding, batch, completed, cpp, entry, header, makefile, op:read, op:write, rewrite
- `target-08` (2): appcontext, apply, apps, avoid, backed, breakage, bug, bytecode, cannot, cat
- `target-09` (3): adaptive, adapts, adding, alive, applicable, base, based, breakpoints, canonical, catalog
- `target-10` (2): assert, atoms, avoid, bash, bat, bug, builtins, called, carefully, causes
- `target-11` (3): bin, binary, boot, complete, config, etc, filetype:.c, init, initramfs, kernel
- `target-12` (2): allocator, arg, bin, boundary, cat, cleanest, cmake, codebase, completed, context
- `target-13` (4): android, apk, attach, cat, device, dsp, flow, git, gradle, grep
- `target-14` (2): activity, android, apply, author, authors, autoupdatemode, b64, base64, binaries, blocker

## Logic clusters

Clusters: 2; residual: 1

- `logic-01` (22): U → A → T:list → T:read → A → T:list → T:read → A → T:list → T:read → A → T:edit → A → T:edit → A → T:read → A → U → A → T:list → A → T:write → A → T:edit → A → T:list → T:read → A → T:edit → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → U → A → T:read → A → T:write → A → T:write → A → T:read → A → T:write → A → T:write → A → T:write → A → T:read → A → T:edit → A
- `logic-02` (20): T:read → T:write → H → A → T:read → T:edit → A → U → H → A → T:git:other → T:list → T:read → H → A → T:search → T:read → H → A → H → A → T:read → T:list → T:read → H → A → T:create → T:copy → T:run:python → T:read → A → T:run:python → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:run:python → H → A → T:run:python → H → A → H → A → T:read → H → A → T:run:python → H → A → H → A → H

## Cannot-link

Target p10: 0.00561127; logic p10: 0.06935699; edges: 13

