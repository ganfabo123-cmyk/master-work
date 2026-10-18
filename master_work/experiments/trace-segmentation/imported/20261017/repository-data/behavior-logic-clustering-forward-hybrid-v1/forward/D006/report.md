# D006 behavior clustering

Slices: 36

## Target clusters

Clusters: 4; residual: 0

- `target-01` (5): item, ok, op:edit, op:search, op:write, tool:edit, tool:grep, tool:powershell, tool:write, odin
- `target-02` (14): css, op:edit, tool:edit, index, op:list, html, op:write, tool:write, js, op:search
- `target-03` (6): engine, implementation, makefile, filetype:.md, filetype:makefile, op:write, tool:write, checks, completed, core
- `target-04` (11): op:list, op:write, tool:write, op:edit, page, route, tool:edit, index, pages, based

## Logic clusters

Clusters: 6; residual: 0

- `logic-01` (8): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit
- `logic-02` (20): U → A → T:read → A → T:edit → A → T:edit → A → T:edit → T:read → T:edit → A → T:edit → A → U → A → T:read → T:search → A → T:edit → A → T:list → T:write → A → T:edit → A → T:edit → A → T:edit → A → U → A → T:list → A → T:read → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:search → T:edit → A
- `logic-03` (3): U → T:search → T:edit → A → U → A → T:edit → A → T:search → T:edit → A → U → A → T:search → A → T:list → T:search → A → T:build:npm → T:search → A → T:search → T:build:npm → T:search → A → T:read → T:edit → A → T:edit → A → T:edit → A
- `logic-04` (3): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log
- `logic-05` (2): U → A → T:read → A
- `logic-06` (2): U → A → T:read → T:write → A → T:write → A → U → A → T:list → T:compile → A → T:write → A

## Cannot-link

Target p10: 0.00283755; logic p10: 0.1106552; edges: 64


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
