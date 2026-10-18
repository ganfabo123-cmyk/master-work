# D007 behavior clustering

Slices: 27

## Target clusters

Clusters: 3; residual: 0

- `target-01` (7): op:read, tool:bash, filetype:.md, op:search, target, version, zero, builds, end, op:list
- `target-02` (14): op:write, tool:write, op:read, tool:read, parser, tool:powershell, op:edit, tool:edit, completed, makefile
- `target-03` (6): database, engine, epilog, solver, atoms, builtins, cpp, filetype:.cpp, hpp, implementation

## Logic clusters

Clusters: 5; residual: 0

- `logic-01` (12): U → A → T:agent → A → T:read → A → T:read → A → T:write → T:toolsearch → T:todowrite → T:write → T:todowrite → A → T:write → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:write → A → T:write → A → T:read → A
- `logic-02` (4): U → A → T:toolsearch → A → T:todowrite → T:create → T:todowrite → A → T:write → U → A → T:remove → T:create → A → T:write → U → A → T:remove → A → T:write → A → T:write → A → T:write → A → T:write → A → T:write → A
- `logic-03` (7): U → A → T:read → A → T:list → A → T:read → A → T:read → A → T:test:make → T:read → T:test:make → T:read → A → T:read → A → T:compile → T:list → A → T:toolsearch → A → T:todowrite → A → T:read → T:compile → T:read → A → T:edit → T:read → T:edit → T:compile → T:run:m0_verify.exe → A → T:run:epilog.exe → T:read → T:run:epilog.exe → A → T:read → A → T:read → A → T:read → A → T:read → T:search → T:read → A → T:read → A → T:write → T:run:python → T:compile → T:run:check_escape2.exe → T:read → T:compile → T:run:check_escape2.exe → A → T:powershell → T:compile
- `logic-04` (3): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log
- `logic-05` (1): T:write → A → T:todowrite → T:remove → T:todowrite → T:write → T:todowrite → T:compile → A → T:run:epilog.exe → A → T:run:epilog.exe → A → T:todowrite → A

## Cannot-link

Target p10: 0.00363237; logic p10: 0.06321375; edges: 45


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
