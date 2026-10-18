# D001 behavior clustering

Slices: 65

## Target clusters

Clusters: 20; residual: 1

- `target-01` (3): address, back, cfml, codeberg, completed, cryptoscam, dangerous, directive, directives, disclosure
- `target-02` (4): css, filetype:.json, fonts, html, index, js, op:edit, op:list, op:read, tool:edit
- `target-03` (3): bios, changed, colour, command, entry, false, filetype:.c, filetype:.h, filetype:makefile, framebuffer
- `target-04` (5): commands, git, github, op:git:other, op:list, op:read, removes, rule, session, skill
- `target-05` (2): adding, batch, bin, binary, clangd, completed, cpp, creating, entry, exe
- `target-06` (3): adding, batch, cli, codegen, codegenoptions, completed, copy, cpp, diagnostics, expected
- `target-07` (3): apply, apps, backed, bytecode, cannot, cat, class, clear, compile, compilejava
- `target-08` (3): across, adaptive, adapts, adding, alive, applicable, base, based, breakpoints, canonical
- `target-09` (4): allocated, dmls, filetype:.odin, odin, op:edit, op:read, tool:edit, tool:read, details, dll
- `target-10` (5): atoms, builtins, clang, compile, completed, database, engine, epilog, erroraction, etc
- `target-11` (3): bin, binary, boot, complete, config, etc, filetype:.c, init, initramfs, kernel
- `target-12` (3): automatically, background, changed, command, copy, exact, filetype:.output, grep, install, interrupted
- `target-13` (2): adds, allocator, allocs, ar, arg, around, audit, bare, basic, bitmask
- `target-14` (2): agents, based, blocks, body, bun, bundler, carbon, childitem, comments, configured
- `target-15` (3): archive, axis, books, css, different, dominion, eden, filetype:.css, filetype:.md, filetype:.tsx
- `target-16` (2): filetype:.py, op:read, py, request, tool:read, __main__, __name__, __version__, _encoded, a500
- `target-17` (3): apple, bun, components, count, db, documents, filetype:.ts, frontend, host, invoke
- `target-18` (3): bentofolio, box, breakpoints, css, filetype:.css, grid, mobile, op:read, overflow, selector
- `target-19` (4): android, apk, attach, cat, device, dsp, flow, git, gradle, grep
- `target-20` (4): android, binaries, commit, download, droid, failed, failure, fdroid, ffdroiddata, glab

## Logic clusters

Clusters: 3; residual: 1

- `logic-01` (30): U → A → T:read → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:edit → A → T:write → A → U → A → T:read → A → T:todowrite → A → T:edit → A → T:edit → A → T:read → A → T:edit → A → T:edit → A → T:edit → T:todowrite → A → T:write → A → T:todowrite → A → U → A → T:read → A → T:read → A → T:edit → A → T:edit → A → T:read → T:edit → A → T:edit → A → T:edit → A → T:edit → A → T:edit → A
- `logic-02` (24): T:read → T:write → H → A → T:read → T:edit → A → U → H → A → T:git:other → T:list → T:read → H → A → T:search → T:read → H → A → H → A → T:read → T:list → T:read → H → A → T:create → T:copy → T:run:python → T:read → A → T:run:python → T:read → H → A → T:search → T:read → H → A → T:search → T:read → H → A → T:run:python → H → A → T:run:python → H → A → H → A → T:read → H → A → T:run:python → H → A → H → A → H
- `logic-03` (10): U → T:skill → U → A → T:toolsearch → T:todowrite → A → T:list → A → T:read → T:list → T:read → A → T:create → T:write → A → T:write → A → T:write → A → T:write → T:todowrite → A → T:skill → U → A → T:read → A → T:write → A → T:create → T:write → A → T:write → T:todowrite → T:write → T:todowrite → T:write → T:todowrite → T:write → A → T:todowrite → T:install:npm → T:read → T:list → T:read → A → T:copy → T:write → A → T:run:npx → A → T:run:npx → T:read → T:edit → T:read → T:edit → A → T:read → T:edit

## Cannot-link

Target p10: 0.00448191; logic p10: 0.05162829; edges: 30

