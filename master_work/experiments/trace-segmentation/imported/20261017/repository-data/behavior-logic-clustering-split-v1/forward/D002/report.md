# D002 behavior clustering

Slices: 43

## Target clusters

Clusters: 6; residual: 0

- `target-01` (3): filetype:.py, op:read, py, tool:read, __init__, __version__, additions, availability, block, catch
- `target-02` (9): op:list, op:read, tool:read, base, core, reference, references, op:edit, tool:edit, takes
- `target-03` (9): op:edit, op:read, tool:edit, tool:read, op:write, tool:write, op:search, tool:bash, op:list, command
- `target-04` (13): makefile, op:read, tool:read, filetype:.h, filetype:makefile, op:list, complete, header, tool:todowrite, op:edit
- `target-05` (8): git, grep, home, op:list, op:read, op:search, tail, tool:bash, cat, java
- `target-06` (1): academic, access, adversarial, adversary, ai, alone, alternatives, ambiguity, ambiguous, analysis

## Logic clusters

Clusters: 6; residual: 0

- `logic-01` (13): U → A → T:read → T:search → A → T:read → A → T:read → A → T:read → T:edit → A → T:build:make → A → U → A → T:read → T:list → T:read → A → T:read → A → T:write → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:build:make → A → T:edit → T:build:make → A → T:build:make → T:read → T:build:make → U → A → T:read → A → T:write → A → U → A → T:read → A → T:read → T:list → A → T:write → A → T:write
- `logic-02` (6): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit
- `logic-03` (3): U → A → T:read → A → T:list → A → T:read → A → T:read → A → T:test:make → T:read → T:test:make → T:read → A → T:read → A → T:compile → T:list → A → T:toolsearch → A → T:todowrite → A → T:read → T:compile → T:read → A → T:edit → T:read → T:edit → T:compile → T:run:m0_verify.exe → A → T:run:epilog.exe → T:read → T:run:epilog.exe → A → T:read → A → T:read → A → T:read → A → T:read → T:search → T:read → A → T:read → A → T:write → T:run:python → T:compile → T:run:check_escape2.exe → T:read → T:compile → T:run:check_escape2.exe → A → T:powershell → T:compile
- `logic-04` (17): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-05` (3): A → T:list → A → H → A → H → A → T:search → A → H → A → T:search → T:read → T:search → H → A
- `logic-06` (1): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read

## Cannot-link

Target p10: 0.00561127; logic p10: 0.06935699; edges: 123


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
