# D007 behavior clustering

Slices: 27

## Target clusters

Clusters: 4; residual: 0

- `target-01` (4, sessions=3, core=routing_only): cfml, backlog, mrs, esbuild, pixel, rollup, inference, nyan, pygame, rust
- `target-02` (9, sessions=6, core=routing_only): convert, shifting, kernel, grub, scss, effort, feeding, interface, iv, leaked
- `target-03` (7, sessions=4, core=routing_only): gitignore, req, characters, dashes, parts, heredoc, backslash, settimeout, es, gc
- `target-04` (7, sessions=2, core=routing_only): languages, nasa, guidelines, least, capacity, cassert, equivalents, jumping, ny, piped

## Logic clusters

Clusters: 5; residual: 0

- `logic-01` (13, sessions=8, core=routing_only): T:powershell → T:run:dmls.exe → A → T:list → A → T:run:dxdiag.exe → T:run:dmls.exe → T:powershell → T:run:gflags.exe → T:run:where.exe → T:powershell → A → T:list → A → T:read → A → T:list → A → T:copy → T:list → A → T:edit → A → T:run:cmd → T:powershell → A → T:powershell → T:run:handle64.exe → T:remove → T:powershell → A → U → A → T:read → A → T:list → T:read → A → T:read → A → T:write → A → T:write → A → T:write → A → T:search → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:skill → U
- `logic-02` (4, sessions=4, core=routing_only): U → A → T:toolsearch → A → T:todowrite → T:create → T:todowrite → A → T:write → U → A → T:remove → T:create → A → T:write → U → A → T:remove → A → T:write → A → T:write → A → T:write → A → T:write → A → T:write → A
- `logic-03` (6, sessions=5, core=routing_only): T:todowrite → T:write → T:todowrite → A → T:test:make → A → T:run:test_indexing.exe → T:run:test_solver.exe → A → T:powershell → A → T:list → A → T:read → A → T:powershell → A → T:run:test_indexing.exe → A → T:powershell → A → T:read → A → T:edit → A → T:read → A → T:edit → A → T:powershell → A → T:read → A → T:edit → A → T:edit → A → T:powershell → A → T:run:test_solver.exe → A → T:run:dbg_test.exe → A → T:compile → T:run:dbg2_test.exe → A → T:read → A → T:edit → T:run:dbg2_test.exe → A → T:powershell → A → T:run:test_indexing.exe → T:run:test_solver.exe → T:run:test_atoms.exe → A → T:powershell → T:run:test_solver2025.exe → T:run:test_indexing2025.exe
- `logic-04` (3, sessions=2, core=routing_only): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log
- `logic-05` (1, sessions=1, core=routing_only): T:write → A → T:todowrite → T:remove → T:todowrite → T:write → T:todowrite → T:compile → A → T:run:epilog.exe → A → T:run:epilog.exe → A → T:todowrite → A

## Cannot-link

Target p10: 0.00198744; logic p10: 0.05600613; edges: 44


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
