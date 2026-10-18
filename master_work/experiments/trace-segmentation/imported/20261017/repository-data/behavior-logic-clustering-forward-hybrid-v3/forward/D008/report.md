# D008 behavior clustering

Slices: 24

## Target clusters

Clusters: 3; residual: 0

- `target-01` (2): accept, active, affects, always, auto, based, bin, blocks, breaks, builds
- `target-02` (10): tool:read, filetype:.md, op:edit, op:list, tool:edit, reference, tool:bash, web, op:write, tool:write
- `target-03` (12): grep, op:list, op:search, tool:bash, home, install, tail, tool:read, tools, version

## Logic clusters

Clusters: 5; residual: 0

- `logic-01` (4): U → A → T:read → A → T:read → T:edit → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:search → T:read → T:edit → A → U → A → T:askuserquestion → A → T:edit → A → T:edit → A → U → T:askuserquestion → T:edit → A → T:edit → A → U → T:askuserquestion → T:edit → A → U → T:edit → A → U → T:list → T:read → A → U → A → T:read → A → U → T:run:python → A → T:run:python → T:read → A → T:read → A
- `logic-02` (13): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-03` (2): T:write → A → T:write → A → T:write → A → T:todowrite → T:write → T:todowrite → T:list → A → U → A → T:read → A → T:edit → A → T:edit → A → T:build:make → A → U → A → T:read → A → T:edit → A → T:read → T:edit → A → T:powershell → A → U → A → T:read → T:edit → A → T:edit → A → T:write → A → T:build:make → A → U → A → T:search → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:build:make → A → T:run:yggdrasil.exe → A → T:read
- `logic-04` (3): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit
- `logic-05` (2): T:read → T:search → H → T:read → A → T:edit → H → A → T:edit → A → H → T:edit → A → T:edit → A → H → T:search → T:read → A → T:edit → T:read → T:edit → A → T:edit → A → T:edit → A → H → T:list → T:write → A → T:read → T:edit → A → T:edit → A → H → A → T:write → A → T:edit → A → H → A → T:write → A → H → T:run:wsl → T:write → T:run:wsl → H → A → T:write → T:run:wsl → T:read → H → A → H → A → H

## Cannot-link

Target p10: 0.00599494; logic p10: 0.07175988; edges: 30


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
