# D004 behavior clustering

Slices: 29

## Target clusters

Clusters: 3; residual: 0

- `target-01` (10): op:list, op:search, op:edit, op:write, tool:edit, tool:read, tool:write, header, title, css
- `target-02` (11): tool:read, css, html, index, op:edit, tool:edit, op:list, op:write, tool:write, filetype:.html
- `target-03` (8): documents, route, components, layout, op:write, page, routes, tool:read, tool:write, ts

## Logic clusters

Clusters: 5; residual: 0

- `logic-01` (4): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit
- `logic-02` (15): U → A → T:read → A → T:edit → A → T:edit → A → T:edit → T:read → T:edit → A → T:edit → A → U → A → T:read → T:search → A → T:edit → A → T:list → T:write → A → T:edit → A → T:edit → A → T:edit → A → U → A → T:list → A → T:read → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:search → T:edit → A
- `logic-03` (5): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read
- `logic-04` (3): U → A → T:powershell → A → T:dev:bun → A → T:powershell → A → T:read → A → T:edit → A → T:edit → A → T:read → T:write → A → T:build:bun → T:search → T:dev:bun → A → T:dev:bun → A
- `logic-05` (2): U → A → T:create → T:list → A → T:list → A → T:read → U

## Cannot-link

Target p10: 0.0044402; logic p10: 0.07143062; edges: 45


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
