# D003 behavior clustering

Slices: 45

## Target clusters

Clusters: 3; residual: 0

- `target-01` (20, sessions=9, core=routing_only): databases, virtualpc, oder, elysia, internet, inspired, episodes, ibm, keystore, rollup
- `target-02` (13, sessions=5, core=routing_only): law, instagram, minmax, svh, fruit, cursive, crowded, battle, afford, fundamentally
- `target-03` (12, sessions=5, core=routing_only): till, repl, landmarks, chdir, identifier, dlc, createprocesscommon, relay, lrng, voicebox

## Logic clusters

Clusters: 4; residual: 0

- `logic-01` (26, sessions=9, core=routing_only): U → T:read → T:search → T:read → A → T:read → A → T:edit → A → T:read → T:edit → A → T:edit → A → U → A → T:read → A → T:read → T:edit → A → T:edit → A → T:edit → A → U → A → T:search → T:read → A → T:edit → A → T:search → A → T:edit → A → U → T:read → A → T:edit → A → T:edit → A → T:read → T:edit → A → U → T:search → T:edit → A → U → A → T:search → A → T:search → T:edit → A → U → A → T:read
- `logic-02` (8, sessions=5, core=routing_only): U → A → U → A → T:askuserquestion → A → T:toolsearch → T:todowrite → T:run:bun → T:run:npx → T:install:bun → T:run:bun → T:list → T:todowrite → A → T:create → T:write → A → T:read → T:write → T:read → T:todowrite → T:write → T:todowrite → T:write → A → T:write → T:list → T:read → T:edit → A → T:edit → A → T:write → T:todowrite → A → T:write → T:create → T:write → T:todowrite → A → T:write → A → T:create → T:write → T:todowrite → A → T:read → T:write → A → T:write → A → T:run:bun → T:build:bun → A → T:read → T:write → A → T:edit → A
- `logic-03` (10, sessions=3, core=routing_only): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-04` (1, sessions=1, core=routing_only): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read

## Cannot-link

Target p10: 0.0022985; logic p10: 0.05868398; edges: 112


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
