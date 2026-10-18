# D005 behavior clustering

Slices: 45

## Target clusters

Clusters: 6; residual: 0

- `target-01` (5): entry, op:edit, op:read, op:write, process, tool:edit, tool:read, tool:write, windows, adding
- `target-02` (9): css, op:read, tool:read, op:edit, tool:edit, html, index, op:write, style, tool:write
- `target-03` (18): op:edit, op:read, tool:edit, tool:read, op:list, filetype:.md, op:search, op:write, tool:bash, tool:write
- `target-04` (5): command, entry, filetype:.c, filetype:.h, filetype:makefile, framebuffer, gop, grub, kernel, makefile
- `target-05` (4): buttons, dmls, filetype:.odin, grid, odin, op:read, return, tool:read, _handle_stat_clicks, allocation
- `target-06` (5): db, documents, filetype:.ts, frontend, host, mydatabase, op:read, page, route, routes

## Logic clusters

Clusters: 4; residual: 0

- `logic-01` (27): U → A → T:read → T:search → A → T:read → A → T:read → A → T:read → T:edit → A → T:build:make → A → U → A → T:read → T:list → T:read → A → T:read → A → T:write → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:build:make → A → T:edit → T:build:make → A → T:build:make → T:read → T:build:make → U → A → T:read → A → T:write → A → U → A → T:read → A → T:read → T:list → A → T:write → A → T:write
- `logic-02` (4): U → A → T:read → T:list → T:read → A → T:read → A → T:read → A → T:toolsearch → T:todowrite → A
- `logic-03` (7): U → A → U → A → T:askuserquestion → A → T:toolsearch → T:todowrite → T:run:bun → T:run:npx → T:install:bun → T:run:bun → T:list → T:todowrite → A → T:create → T:write → A → T:read → T:write → T:read → T:todowrite → T:write → T:todowrite → T:write → A → T:write → T:list → T:read → T:edit → A → T:edit → A → T:write → T:todowrite → A → T:write → T:create → T:write → T:todowrite → A → T:write → A → T:create → T:write → T:todowrite → A → T:read → T:write → A → T:write → A → T:run:bun → T:build:bun → A → T:read → T:write → A → T:edit → A
- `logic-04` (7): T:run:adb → T:list → T:read → H → A → T:search → T:read → H → A → T:edit → T:run:build-apk.sh → T:read → T:run:adb → T:read → T:run:adb → T:read → H → A → T:read → T:edit → H → A → T:askuserquestion → H → A → T:git:checkout → T:git:add → T:git:status → T:git:commit → H → A → T:run:adb → T:search → H → A → T:run:adb → H → A → T:run:adb → T:search → H → A → H → T:run:adb → H → A → T:run:adb → H → A → T:run:adb → A → H → T:search → T:read → H → A → H → A → T:run:adb → T:read

## Cannot-link

Target p10: 0.00423735; logic p10: 0.09225317; edges: 99


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
