# D008 behavior clustering

Slices: 24

## Target clusters

Clusters: 3; residual: 0

- `target-01` (10, sessions=4, core=routing_only): yggdrasil, agp, nephilimos, keystore, char, definition, glue, bios, iso, assembling
- `target-02` (7, sessions=4, core=routing_only): replies, rul, nonfreenet, scrutiny, prebuilt, camera, purpose, strangers, tester, readest
- `target-03` (7, sessions=5, core=routing_only): apple, connections, neongpt, gpt, carbon, cursive, humanizer, wisdom, thick, displays

## Logic clusters

Clusters: 3; residual: 0

- `logic-01` (6, sessions=5, core=routing_only): U → A → T:read → A → T:read → T:edit → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:search → T:read → T:edit → A → U → A → T:askuserquestion → A → T:edit → A → T:edit → A → U → T:askuserquestion → T:edit → A → T:edit → A → U → T:askuserquestion → T:edit → A → U → T:edit → A → U → T:list → T:read → A → U → A → T:read → A → U → T:run:python → A → T:run:python → T:read → A → T:read → A
- `logic-02` (15, sessions=5, core=routing_only): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-03` (3, sessions=3, core=routing_only): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit

## Cannot-link

Target p10: 0.00430991; logic p10: 0.06217889; edges: 30


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
