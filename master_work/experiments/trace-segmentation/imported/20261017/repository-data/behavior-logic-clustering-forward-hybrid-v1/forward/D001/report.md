# D001 behavior clustering

Slices: 65

## Target clusters

Clusters: 5; residual: 0

- `target-01` (5): filetype:.py, op:read, py, tool:read, op:edit, op:run:python, op:search, op:write, print, python
- `target-02` (7): css, op:read, tool:read, html, index, js, op:edit, style, tool:edit, filetype:.html
- `target-03` (18): op:read, tool:read, op:edit, op:write, tool:edit, tool:write, op:search, op:list, route, tool:powershell
- `target-04` (19): op:read, tool:bash, op:list, home, tail, tool:read, grep, op:search, filetype:.md, git
- `target-05` (16): op:read, tool:read, exe, function, op:edit, op:write, tool:edit, tool:write, completed, tool:powershell

## Logic clusters

Clusters: 6; residual: 0

- `logic-01` (30): U → A → T:read → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:write → A → U → A → T:read → A → T:todowrite → A → T:edit → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → T:todowrite → A → T:write → A → T:todowrite → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:read → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A
- `logic-02` (23): H → A → T:read → H → A → H → T:list → T:read → T:list → T:search → T:read → H → A → T:read → H → A → T:read → T:list → H → A → T:write → A → T:list → T:read → H → A → T:read → T:search → H → A → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → T:read → H → A → T:write → H → A → T:remove → H → A → H → A → T:read → T:search → T:read → H → A
- `logic-03` (9): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit
- `logic-04` (2): T:compile → T:run:epilog.exe → A → T:run:epilog.exe → A → T:run:epilog.exe → A → T:write → A → T:read → T:write → A → T:read → T:edit → A → T:read → T:edit → T:compile → A → T:write → T:compile → A → T:edit → T:compile → A → T:run:epilog.exe → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:compile → T:run:epilog.exe → A → T:run:epilog.exe → A → T:run:epilog.exe → A → T:read → A → T:read → A → T:read → A → T:edit → T:compile → T:run:epilog.exe → A → T:run:epilog.exe → U → A → T:list → T:write → A → U → A
- `logic-05` (1): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read
- `logic-06` (1): U → H → T:websearch → H → A

## Cannot-link

Target p10: 0.00419113; logic p10: 0.05161596; edges: 291


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
