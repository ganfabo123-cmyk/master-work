# D007 behavior clustering

Slices: 27

## Target clusters

Clusters: 9; residual: 5

- `target-01` (5): add, because, before, codegen, completed, cpp, diagnostics, errors, expected, file
- `target-02` (2): acceptance, actually, add, after, again, already, anna, anna_croft, approach, atoms
- `target-03` (3): cpp, database, engine, epilog, extern, filetype:.cpp, filetype:.hpp, hpp, implement, implementation
- `target-04` (2): about, add, adding, api, architecture, batch, bin, binary, both, built
- `target-05` (2): across, actually, add, after, again, already, anything, args, because, become
- `target-06` (2): actual, actually, add, adds, after, allocator, allocs, already, api, approach
- `target-07` (2): actually, adapts, add, adding, after, app, auto, automatically, base, based
- `target-08` (2): atoms, builtins, cpp, database, engine, epilog, files, filetype:.cpp, headers, hpp
- `target-09` (2): aapt, actually, ads, after, against, already, android, androidx, api, apk

## Logic clusters

Clusters: 4; residual: 0

- `logic-01` (13): T:powershell → T:run:dmls.exe → A → T:list → A → T:run:dxdiag.exe → T:run:dmls.exe → T:powershell → T:run:gflags.exe → T:run:where.exe → T:powershell → A → T:list → A → T:read → A → T:list → A → T:copy → T:list → A → T:edit → A → T:run:cmd → T:powershell → A → T:powershell → T:run:handle64.exe → T:remove → T:powershell → A → U → A → T:read → A → T:list → T:read → A → T:read → A → T:write → A → T:write → A → T:write → A → T:search → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:skill → U
- `logic-02` (5): U → A → T:toolsearch → A → T:todowrite → T:create → T:todowrite → A → T:write → U → A → T:remove → T:create → A → T:write → U → A → T:remove → A → T:write → A → T:write → A → T:write → A → T:write → A → T:write → A
- `logic-03` (6): T:todowrite → T:write → T:todowrite → A → T:test:make → A → T:run:test_indexing.exe → T:run:test_solver.exe → A → T:powershell → A → T:list → A → T:read → A → T:powershell → A → T:run:test_indexing.exe → A → T:powershell → A → T:read → A → T:edit → A → T:read → A → T:edit → A → T:powershell → A → T:read → A → T:edit → A → T:edit → A → T:powershell → A → T:run:test_solver.exe → A → T:run:dbg_test.exe → A → T:compile → T:run:dbg2_test.exe → A → T:read → A → T:edit → T:run:dbg2_test.exe → A → T:powershell → A → T:run:test_indexing.exe → T:run:test_solver.exe → T:run:test_atoms.exe → A → T:powershell → T:run:test_solver2025.exe → T:run:test_indexing2025.exe
- `logic-04` (3): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log

## Cannot-link

Target p10: 0.00555196; logic p10: 0.06386801; edges: 3

