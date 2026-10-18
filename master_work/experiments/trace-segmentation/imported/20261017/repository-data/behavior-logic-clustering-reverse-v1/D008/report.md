# D008 behavior clustering

Slices: 24

## Target clusters

Clusters: 8; residual: 0

- `target-01` (2): accept, active, affects, always, auto, based, bin, blocks, breaks, builds
- `target-02` (3): agent, anonymity, anyone, anything, apache, asking, base, briefly, chosen, cleaned
- `target-03` (3): adaptive, adapts, adding, alive, applicable, base, based, breakpoints, canonical, catalog
- `target-04` (3): automatically, background, changed, command, copy, exact, filetype:.output, grep, install, interrupted
- `target-05` (2): abel, adding, alone, angel, angelic, archive, ariel, authorial, axis, based
- `target-06` (2): always, applied, becomes, better, chunks, classic, convert, count, cut, detail
- `target-07` (5): android, apk, device, dsp, gradle, grep, home, java, lib, log
- `target-08` (4): android, binaries, commit, download, droid, failed, failure, fdroid, ffdroiddata, glab

## Logic clusters

Clusters: 2; residual: 0

- `logic-01` (9): U → A → T:read → A → T:list → A → T:write → A → U → A → T:list → T:run:node → T:run:npm → T:run:npx → A → T:run:npx → A → T:list → T:read → T:list → T:read → A → T:read → A → T:write → A → T:remove → A → T:typecheck:npm → A → T:dev:npm → T:remove → T:list → T:remove → T:dev:npm → T:list → T:run:cmd → A → T:run:cmd → A → T:run:node → A → T:run:cmd → A → T:run:cmd → A → T:dev:npm → A → T:run:cmd → A → T:read → A → T:search → A → T:search → A → T:search → T:read → T:search → A
- `logic-02` (15): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read

## Cannot-link

Target p10: 0.00599494; logic p10: 0.07175988; edges: 0


## Reverse cannot-link partitions

Target: 3 full groups from 28 cannot-link edges (p10=0.00599494).

- `target-reverse-01` (14)
- `target-reverse-02` (7)
- `target-reverse-03` (3)

Logic: 2 full groups from 2 cannot-link edges (p10=0.07175988).

- `logic-reverse-01` (2): U → A → T:edit → A → U → A → T:list → T:read → A → T:bash → T:read → A → U → A → T:list → T:search → A → U → A → T:list → T:read → A → T:edit → A → T:edit → A → T:edit → A → U → A → T:edit → T:read → A → U → A → T:edit → A → T:edit → A → U → A → T:edit → A → T:read → A → T:edit → A → U → A → T:read → T:edit → A → U → A → T:edit → A → T:edit → A → T:edit → A
- `logic-reverse-02` (22): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
