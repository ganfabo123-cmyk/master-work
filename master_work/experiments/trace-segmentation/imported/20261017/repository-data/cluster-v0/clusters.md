# 切片聚类 v0.2

97 个切片；16 个初始候选；证据分门槛 0.75、不同会话至少 2 个；1 个簇过线；2 个切片入簇；95 个暂未归簇。

证据分是透明规则分，不是校准概率。过线簇是待核查的 skill 抽样候选，不等于已证实可抽象出 skill。共同证据表示至少两个成员包含该项。

| 簇 | 证据分 | 成员 | 会话 | 至少两成员共有的任务词 | 共同操作证据 |
|---|---:|---:|---:|---|---|
| [C001](#c001) | 0.761 | 2 | 2 | vercel | read+vercel.json, read+main.js, edit+vercel.json, read+index.html |

## C001

证据分 0.761；最低两两综合相似度 0.216。共同任务词：vercel。共同文件操作：read+vercel.json, read+main.js, edit+vercel.json, read+index.html。共同操作+文件类型：read+.json, edit+.json, read+.js, read+.html。

成员：

- `claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2__segment-01`
- `claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04`

两两连接：

- `claude_code__11ef2190-67e2-4707-8212-ab12ebffdbc2__segment-01` ↔ `claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-04`，综合 0.216；任务词 0.143，具体文件操作 0.405。

## 暂缓的候选

证据分不足或仅来自同一会话的组合暂缓；同项目不同任务容易产生虚高分。

| 候选 | 证据分 | 会话 | 暂缓原因 | 成员 | 共同任务词 |
|---|---:|---:|---|---|---|
| P001 | 0.636 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01`, `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02`, `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03` | multiboot, gop, grub, mb2, multiboot2 |
| P002 | 0.781 | 1 | insufficient_distinct_sessions | `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`, `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02` | cfml, cryptoscam, milestone, directive, nyancat |
| P003 | 0.617 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`, `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-03` | cryptoscam, cfml, directive, dangerous, dangerous_codeberg |
| P004 | 0.900 | 1 | insufficient_distinct_sessions | `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`, `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03` | taskbar, peppertino, icons, clock, alpine |
| P005 | 0.738 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02`, `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03` | lucide, clock, icon, icontosvg, svg |
| P007 | 0.758 | 1 | insufficient_distinct_sessions | `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-01`, `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03` | lexer, codegen, jsx, cpp, diagnostics |
| P008 | 0.813 | 1 | insufficient_distinct_sessions | `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-03`, `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05` | sysinfo, smp, cpio, initrd, rdinit |
| P009 | 0.628 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05`, `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06` | bochs, ko, cpio, smp, initrd |
| P010 | 0.874 | 1 | insufficient_distinct_sessions | `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`, `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03` | frostcore, rt, ng, quickjs, runtimes |
| P011 | 0.562 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`, `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03` | subreddit, reddit, carbon, md3 |
| P012 | 0.900 | 1 | insufficient_distinct_sessions | `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02`, `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-04` | eve, timeline, beginnings, books, connections |
| P013 | 0.815 | 1 | insufficient_distinct_sessions | `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02`, `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-05` | michael, lucifer, yhwh, gabriel, timeline |
| P014 | 0.811 | 1 | insufficient_distinct_sessions | `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-01`, `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-02` | libyggdrasil, shim, yggdrasil, ygg_alloc, yggdrasil_c_api |
| P015 | 0.506 | 1 | evidence_score_below_threshold, insufficient_distinct_sessions | `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01`, `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-04` | orv, backend, db, server |
| P016 | 0.842 | 1 | insufficient_distinct_sessions | `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`, `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-04` | orv, db, frontend, page |

## 暂未归簇

- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-01`
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-02`
- `claude_code__07b57159-218e-4330-a64e-0ec4b4355056__segment-03`
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-01`
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-02`
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-03`
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-04`
- `claude_code__09d9abe9-0a02-4bd1-8129-3b864695079d__segment-05`
- `claude_code__0ca72c0c-ac42-400a-8ca6-cc31a787225f__segment-01`
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-01`
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-02`
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-03`
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-04`
- `claude_code__17c2cf98-e64a-43c6-932e-fa7efcade358__segment-05`
- `claude_code__2965219c-42ad-45af-889c-4581ecbe0103__segment-01`
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-01`
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-02`
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-03`
- `claude_code__39082932-131c-40a9-872d-1d3ac8ed1fd6__segment-04`
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-01`
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-02`
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-03`
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-04`
- `claude_code__3be5ba0c-62b2-4645-8589-9216be0c10d8__segment-05`
- `claude_code__4130c9a7-ee88-443a-91b5-224accd13629__segment-01`
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-01`
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-02`
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-03`
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-04`
- `claude_code__4222016d-1932-4abb-94b3-463203bd8876__segment-05`
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-01`
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-02`
- `claude_code__479c5e9f-a299-457f-8459-5948adf8aa8e__segment-03`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-01`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-02`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-03`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-04`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-05`
- `claude_code__47d9fc04-420c-47bb-8ac0-85780af22632__segment-06`
- `claude_code__4c09dfa9-ff25-4b4c-a2d0-d2fd702c64ee__segment-01`
- `claude_code__674e0f5c-c481-4830-b2ef-3e1e069a2b7f__segment-01`
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-01`
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-02`
- `claude_code__6a7964ed-6f92-4eee-ae5e-3f91a6445833__segment-03`
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-01`
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-02`
- `claude_code__7563bddf-c1a0-4c3e-86ee-062bf288e6d3__segment-03`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-01`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-02`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-03`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-04`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-05`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-06`
- `claude_code__860618e1-0cf6-43c6-81cf-fe67123082ba__segment-07`
- `claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-01`
- `claude_code__89cf9e13-a4bd-4cf9-9486-7c89737bec1b__segment-02`
- `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-01`
- `claude_code__92833a43-c30d-4b44-8447-c32ee17d6e6e__segment-02`
- `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-01`
- `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-02`
- `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-03`
- `claude_code__a20a4070-6246-4e9e-adf6-f38b0c1dc3fa__segment-04`
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-01`
- `claude_code__ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a__segment-02`
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-01`
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-02`
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-03`
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-04`
- `claude_code__c84c0ad3-c368-40df-87b1-5ef9effe237a__segment-05`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-01`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-02`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-03`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-04`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-05`
- `claude_code__c99032e9-377b-4ae9-a9a9-ec7752b059cd__segment-06`
- `claude_code__comparia-voting-fields-anon__segment-01`
- `claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-01`
- `claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-02`
- `claude_code__d4c4d47d-642c-4c26-a866-51ab85587896__segment-03`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-01`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-02`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-03`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-04`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-05`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-06`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-07`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-08`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-09`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-10`
- `claude_code__da5d32d6-547f-45ae-a5b5-4747ed06542f__segment-11`
- `claude_code__da6566ff-0116-4424-bb59-660623f9eb31__segment-01`
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-01`
- `claude_code__f93127ef-dec9-4d58-964b-ee660964ec4d__segment-02`
- `cursor__debaa898-grafana-loki-monitoring__segment-01`
- `opencode__ses_129b55f7effeSKRtimLg9wxpXa__segment-01`
