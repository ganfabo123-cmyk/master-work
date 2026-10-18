# D002 behavior clustering

Slices: 43

## Target clusters

Clusters: 5; residual: 0

- `target-01` (3, sessions=3, core=routing_only): cfml, neongpt, gpt, nyan, pygame, reverse, meme, vram, animation, rmsnorm
- `target-02` (17, sessions=8, core=routing_only): peppertino, carbon, keystore, replies, humanizer, charactermodel, agents, seeding, alpinejs, brother
- `target-03` (12, sessions=5, core=routing_only): front, vercel, chdir, createprocesscommon, relay, voicebox, fruit, crowded, afford, fundamentally
- `target-04` (5, sessions=4, core=routing_only): rivals, crushing, heredoc, backslash, recovery, pragma, nativecommanderror, parseerror, adjacent, baz
- `target-05` (6, sessions=4, core=routing_only): minimilast, frostcore, development, rt, ambiguity, loader, modularity, anticheat, architectural, effort

## Logic clusters

Clusters: 7; residual: 0

- `logic-01` (13, sessions=8, core=routing_only): U → A → T:read → T:search → A → T:read → A → T:read → A → T:read → T:edit → A → T:build:make → A → U → A → T:read → T:list → T:read → A → T:read → A → T:write → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:build:make → A → T:edit → T:build:make → A → T:build:make → T:read → T:build:make → U → A → T:read → A → T:write → A → U → A → T:read → A → T:read → T:list → A → T:write → A → T:write
- `logic-02` (6, sessions=6, core=routing_only): U → A → T:read → T:skill → U → A → T:list → A → T:list → T:read → A → T:toolsearch → A → T:todowrite → T:write → T:todowrite → A → T:create → T:write → T:todowrite → A → T:write → T:todowrite → T:create → T:write → A → T:todowrite → T:write → T:todowrite → A → T:write → T:read → T:write → A
- `logic-03` (3, sessions=3, core=routing_only): U → A → T:read → A → T:list → A → T:read → A → T:read → A → T:test:make → T:read → T:test:make → T:read → A → T:read → A → T:compile → T:list → A → T:toolsearch → A → T:todowrite → A → T:read → T:compile → T:read → A → T:edit → T:read → T:edit → T:compile → T:run:m0_verify.exe → A → T:run:epilog.exe → T:read → T:run:epilog.exe → A → T:read → A → T:read → A → T:read → A → T:read → T:search → T:read → A → T:read → A → T:write → T:run:python → T:compile → T:run:check_escape2.exe → T:read → T:compile → T:run:check_escape2.exe → A → T:powershell → T:compile
- `logic-04` (13, sessions=4, core=routing_only): H → A → T:read → H → A → H → T:list → T:read → T:list → T:search → T:read → H → A → T:read → H → A → T:read → T:list → H → A → T:write → A → T:list → T:read → H → A → T:read → T:search → H → A → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → T:read → H → A → T:write → H → A → T:remove → H → A → H → A → T:read → T:search → T:read → H → A
- `logic-05` (6, sessions=1, core=routing_only): H → A → H → T:create → T:write → A → T:read → T:edit → A → H → A → T:create → T:write → A → T:read → T:edit → H → A → H → A → H → A → T:edit → A → H → A → H → A → T:read → T:edit → A → H → A → H → A → T:read → T:edit → A → H → A → H → A → H → A → H → A → H → A → T:edit → A → H → A → T:run:wsl → H → A → T:run:wsl → H → T:run:wsl → A → T:run:wsl
- `logic-06` (1, sessions=1, core=routing_only): T:semanticsearch → T:search → T:list → T:read → T:search → T:read → T:list → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:search → T:read → T:list → T:search → T:read → T:search → T:read
- `logic-07` (1, sessions=1, core=routing_only): U → H → T:websearch → H → A

## Cannot-link

Target p10: 0.0042086; logic p10: 0.0589636; edges: 123


This directory is an independent forward experiment: it rewards shared high-similarity coverage and penalizes over-sized groups using the smooth split pressure.
