# D003 behavior clustering

Slices: 45

## Target clusters

Clusters: 13; residual: 10

- `target-01` (2): _iconsvg, bundled, changed, clock, core, creates, dist, dom, element, elements
- `target-02` (2): array, assets, attachment, auriel, cache, camera, cleanurls, control, cpu, css
- `target-03` (2): accessible, address, auto, bad, called, command, desktop, drive, entry, failed
- `target-04` (2): args, argument, better, bin, bios, bit, broken, changed, clangd, colour
- `target-05` (3): adaptive, adapts, adding, alive, applicable, base, based, breakpoints, canonical, catalog
- `target-06` (3): auto, bat, block, buf, carefully, core, creating, deb, details, dll
- `target-07` (2): buttons, dmls, exit, filetype:.odin, grid, increase, interrupted, odin, ok, op:read
- `target-08` (3): ac0, af22632, appdata, arch, automatically, bash, bb, bin, binary, boot
- `target-09` (4): archive, axis, books, css, dominion, eden, filetype:.css, filetype:.md, filetype:.tsx, form
- `target-10` (2): adjectives, aesthetic, apple, audit, author, books, capitalization, compound, conventions, covers
- `target-11` (3): bun, clear, convertto, db, documents, filetype:.ts, frontend, host, invoke, mydatabase
- `target-12` (2): auto, bentofolio, box, breakpoint, breakpoints, changes, clamp, clip, clips, constraint
- `target-13` (5): android, apk, builds, button, cat, commit, debug, dsp, dump, end

## Logic clusters

Clusters: 2; residual: 1

- `logic-01` (34): U → A → T:list → T:read → A → T:list → T:read → A → T:list → T:read → A → T:edit → A → T:edit → A → T:read → A → U → A → T:list → A → T:write → A → T:edit → A → T:list → T:read → A → T:edit → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → U → A → T:read → A → T:write → A → T:write → A → T:read → A → T:write → A → T:write → A → T:write → A → T:read → A → T:edit → A
- `logic-02` (10): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read

## Cannot-link

Target p10: 0.00395709; logic p10: 0.07096986; edges: 8


## Reverse cannot-link partitions

Target: 5 anti-clusters seeded from 99 low-similarity edges (p10=0.00395709); all members covered.

- `target-reverse-01` (9)
- `target-reverse-02` (9)
- `target-reverse-03` (9)
- `target-reverse-04` (9)
- `target-reverse-05` (9)

Logic: 2 anti-clusters seeded from 13 low-similarity edges (p10=0.07096986); all members covered.

- `logic-reverse-01` (22): U → A → T:read → T:skill → U → A → T:list → A → T:list → T:read → A → T:toolsearch → A → T:todowrite → T:write → T:todowrite → A → T:create → T:write → T:todowrite → A → T:write → T:todowrite → T:create → T:write → A → T:todowrite → T:write → T:todowrite → A → T:write → T:read → T:write → A
- `logic-reverse-02` (23): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read
