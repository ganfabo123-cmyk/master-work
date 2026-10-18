# D007 behavior clustering

Slices: 27

## Target clusters

Clusters: 9; residual: 5

- `target-01` (5): codegen, completed, cpp, diagnostics, expected, filetype:.cpp, filetype:.h, filetype:makefile, fixtures, in_progress
- `target-02` (2): acceptance, anna, anna_croft, atoms, bash, bat, bridge, builds, builtins, carefully
- `target-03` (3): cpp, database, engine, epilog, extern, filetype:.cpp, filetype:.hpp, hpp, implement, implementation
- `target-04` (2): adding, architecture, batch, bin, binary, cache, complete, completed, contains, cpp
- `target-05` (2): anything, args, become, breaks, bug, completed, covers, debug, debugging, display
- `target-06` (2): adds, allocator, allocs, ar, arg, audit, bare, basic, bitmask, bottom
- `target-07` (2): adapts, adding, auto, automatically, base, based, blocks, breakpoints, catch, close
- `target-08` (2): atoms, builtins, cpp, database, engine, epilog, filetype:.cpp, headers, hpp, internals
- `target-09` (2): aapt, ads, android, androidx, apk, application, appsflyer, assets, backup, badging

## Logic clusters

Clusters: 4; residual: 1

- `logic-01` (12): U → A → T:agent → A → T:read → A → T:read → A → T:write → T:toolsearch → T:todowrite → T:write → T:todowrite → A → T:write → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:write → A → T:write → A → T:read → A
- `logic-02` (4): U → A → T:toolsearch → A → T:todowrite → T:create → T:todowrite → A → T:write → U → A → T:remove → T:create → A → T:write → U → A → T:remove → A → T:write → A → T:write → A → T:write → A → T:write → A → T:write → A
- `logic-03` (7): U → A → T:read → A → T:list → A → T:read → A → T:read → A → T:test:make → T:read → T:test:make → T:read → A → T:read → A → T:compile → T:list → A → T:toolsearch → A → T:todowrite → A → T:read → T:compile → T:read → A → T:edit → T:read → T:edit → T:compile → T:run:m0_verify.exe → A → T:run:epilog.exe → T:read → T:run:epilog.exe → A → T:read → A → T:read → A → T:read → A → T:read → T:search → T:read → A → T:read → A → T:write → T:run:python → T:compile → T:run:check_escape2.exe → T:read → T:compile → T:run:check_escape2.exe → A → T:powershell → T:compile
- `logic-04` (3): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log

## Cannot-link

Target p10: 0.00363237; logic p10: 0.06321375; edges: 3


## Reverse cannot-link partitions

Target: 3 anti-clusters seeded from 36 low-similarity edges (p10=0.00363237); all members covered.

- `target-reverse-01` (9)
- `target-reverse-02` (9)
- `target-reverse-03` (9)

Logic: 2 anti-clusters seeded from 9 low-similarity edges (p10=0.06321375); all members covered.

- `logic-reverse-01` (14): H → A → T:toolsearch → H → A → T:mcp__haven__list_sessions → H → A → T:run:glab → T:run:python → T:search → H → A → T:run:glab → T:run:python → H → A → T:askuserquestion → H → A → T:run:glab → T:run:python → T:read → H → A → T:remove → T:run:gh → T:read → T:list → H → A → T:search → T:read → T:remove → T:create → H → A
- `logic-reverse-02` (13): H → A → T:run:python → H → A → T:toolsearch → T:mcp__claude-in-chrome__tabs_context_mcp → T:mcp__claude-in-chrome__navigate → H → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:mcp__claude-in-chrome__computer → H → A → T:read → T:search → H → A → T:edit → T:write → H → A → T:fetch → T:search → T:read → H → A → T:git:add → T:git:status → T:git:commit → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → H → A → T:read → T:edit → H → T:typecheck:npm → A → T:dev:npm → T:search → T:read → H → A → T:mcp__claude-in-chrome__navigate → T:mcp__claude-in-chrome__computer → H → A → T:git:add → T:git:commit → T:git:push → T:read → T:git:log
