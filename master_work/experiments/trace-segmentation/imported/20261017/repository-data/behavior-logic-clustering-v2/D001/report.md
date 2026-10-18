# D001 behavior clustering

Slices: 65

## Target clusters

Clusters: 20; residual: 1

- `target-01` (3): actually, add, address, back, both, cd, cfml, codeberg, completed, content
- `target-02` (4): added, build, check, css, filetype:.json, fix, fonts, html, index, issue
- `target-03` (3): about, add, after, already, bios, both, build, changed, check, colour
- `target-04` (5): check, claude, code, commands, directory, files, first, get, git, github
- `target-05` (2): add, adding, batch, bin, binary, both, build, call, calls, check
- `target-06` (3): add, adding, after, approach, batch, because, before, build, building, cli
- `target-07` (3): add, after, already, api, apply, approach, apps, backed, before, both
- `target-08` (3): across, adaptive, adapts, adding, alive, already, api, applicable, approach, base
- `target-09` (4): actual, actually, add, allocated, build, correct, dmls, filetype:.odin, first, fix
- `target-10` (5): atoms, before, both, build, builtins, check, clang, clean, compile, completed
- `target-11` (3): bin, binary, boot, build, clean, code, complete, config, doesn, etc
- `target-12` (3): actually, add, added, after, already, approach, automatically, background, before, both
- `target-13` (2): actual, actually, add, adds, after, allocator, allocs, already, api, approach
- `target-14` (2): about, actually, add, after, agents, already, api, app, based, before
- `target-15` (3): already, app, archive, axis, books, both, build, cd, claude, clean
- `target-16` (2): filetype:.py, json, op:read, py, request, tool:read, user, __main__, __name__, __version__
- `target-17` (3): apple, before, built, bun, cd, check, clean, components, count, db
- `target-18` (3): bentofolio, box, breakpoints, css, exactly, filetype:.css, fix, grid, instead, make
- `target-19` (4): add, already, android, apk, attach, before, build, cat, cd, check
- `target-20` (4): android, api, before, binaries, both, build, cd, check, clean, commit

## Logic clusters

Clusters: 3; residual: 1

- `logic-01` (30): U → A → T:read → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:write → A → U → A → T:read → A → T:todowrite → A → T:edit → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → T:todowrite → A → T:write → A → T:todowrite → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:read → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A
- `logic-02` (24): T:read → T:write → H → A → T:read → T:edit → A → U → H → A → T:git:other → T:list → T:read → H → A → T:search → T:read → H → A → H → A → T:read → T:list → T:read → H → A → T:create → T:copy → T:run:python → T:read → A → T:run:python → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:run:python → H → A → T:run:python → H → A → H → A → T:read → H → A → T:run:python → H → A → H → A → H
- `logic-03` (10): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit

## Cannot-link

Target p10: 0.00615941; logic p10: 0.05255671; edges: 32

