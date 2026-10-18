# D008 behavior clustering

Slices: 24

## Target clusters

Clusters: 8; residual: 0

- `target-01` (2): accept, active, actual, actually, add, added, affects, after, already, always
- `target-02` (3): about, add, agent, anonymity, anyone, anything, apache, asking, base, before
- `target-03` (3): across, adaptive, adapts, adding, alive, already, api, applicable, approach, base
- `target-04` (3): actually, add, added, after, already, approach, automatically, background, before, both
- `target-05` (2): abel, about, across, add, adding, after, again, alone, angel, angelic
- `target-06` (2): actually, add, after, already, always, applied, around, available, becomes, before
- `target-07` (5): android, apk, code, confirm, dev, device, done, dsp, echo, find
- `target-08` (4): android, api, before, binaries, both, clean, commit, dev, done, download

## Logic clusters

Clusters: 2; residual: 0

- `logic-01` (9): U → A → T:read → A → T:list → A → T:write → A → U → A → T:list → T:run:node → T:run:npm → T:run:npx → A → T:run:npx → A → T:list → T:read → T:list → T:read → A → T:read → A → T:write → A → T:remove → A → T:typecheck:npm → A → T:dev:npm → T:remove → T:list → T:remove → T:dev:npm → T:list → T:run:cmd → A → T:run:cmd → A → T:run:node → A → T:run:cmd → A → T:run:cmd → A → T:dev:npm → A → T:run:cmd → A → T:read → A → T:search → A → T:search → A → T:search → T:read → T:search → A
- `logic-02` (15): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read

## Cannot-link

Target p10: 0.0075284; logic p10: 0.07186999; edges: 0

