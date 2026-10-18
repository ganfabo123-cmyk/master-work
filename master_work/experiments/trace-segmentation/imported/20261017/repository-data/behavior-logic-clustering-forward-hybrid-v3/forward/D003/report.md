# D003 behavior clustering

Slices: 45

## Target clusters

Clusters: 4; residual: 0

- `target-01` (8): op:read, tool:read, css, op:edit, tool:edit, html, index, filetype:.html, gets, grid
- `target-02` (18): op:edit, op:read, tool:edit, tool:read, op:list, op:write, tool:write, op:search, live, style
- `target-03` (11): op:read, tool:read, op:edit, tool:bash, tool:edit, op:search, op:write, tool:write, changed, grid
- `target-04` (10): op:read, tool:read, route, routes, documents, op:list, page, ts, components, frontend

## Logic clusters

Clusters: 4; residual: 0

- `logic-01` (26): U → T:read → T:search → T:read → A → T:read → A → T:edit → A → T:read → T:edit → A → T:edit → A → U → A → T:read → A → T:read → T:edit → A → T:edit → A → T:edit → A → U → A → T:search → T:read → A → T:edit → A → T:search → A → T:edit → A → U → T:read → A → T:edit → A → T:edit → A → T:read → T:edit → A → U → T:search → T:edit → A → U → A → T:search → A → T:search → T:edit → A → U → A → T:read
- `logic-02` (9): U → A → U → A → T:askuserquestion → A → T:toolsearch → T:todowrite → T:run:bun → T:run:npx → T:install:bun → T:run:bun → T:list → T:todowrite → A → T:create → T:write → A → T:read → T:write → T:read → T:todowrite → T:write → T:todowrite → T:write → A → T:write → T:list → T:read → T:edit → A → T:edit → A → T:write → T:todowrite → A → T:write → T:create → T:write → T:todowrite → A → T:write → A → T:create → T:write → T:todowrite → A → T:read → T:write → A → T:write → A → T:run:bun → T:build:bun → A → T:read → T:write → A → T:edit → A
- `logic-03` (10): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-04` (1): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read

## Cannot-link

Target p10: 0.00395709; logic p10: 0.07096986; edges: 112


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
