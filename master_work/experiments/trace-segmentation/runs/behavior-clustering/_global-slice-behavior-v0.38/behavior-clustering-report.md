# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：71
- 相似度阈值：0.38
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：11

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 3 | 3 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, edit, run:python, read, list | .py, .cfml, .cpp, .c, .h |
| B002 | 3 | 3 | create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect | read, edit, write, run:epilog.exe, compile | .tsx, .c, .py, .h, .css |
| B003 | 3 | 2 | inspect > modify > inspect > modify > inspect > modify > search > inspect > modify > tool > modify | edit, read, search, run:python, write | .css, .html, .md, .js, .txt |
| B004 | 3 | 2 | execute > inspect > execute > inspect > modify > execute | read, search, list, fetch, run:adb | .ts, .log, .output, makefile, .env |
| B005 | 2 | 1 | search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect | read, edit, write, list, search | .ts, .scss, .html, .json, .mjs |
| B006 | 2 | 1 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | write, list, edit, read, search | .ts, .mjs, .json, .js, .gitignore |
| B007 | 2 | 2 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, write, list | .odin, .c, .h, .md, .asm |
| B008 | 2 | 1 | modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify | read, edit, search, write, run:python | .java, .groovy, .md |
| B009 | 2 | 2 | execute > inspect > create > inspect > modify > execute | read, run:python, search, list, run:glab | .md, .jsonl, .yml, .py, .json |
| B010 | 2 | 2 | inspect > modify > inspect > execute > inspect > modify | read, fetch, edit | .odin |
| B011 | 2 | 1 | search > inspect > search > inspect > search | search, list, read | .1, .c, .h, readme |
| B012 | 2 | 2 | execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create | edit, read, write, run:wsl, list | .sh, .c, makefile, .output, .h |
| B013 | 2 | 2 |  |  |  |
| B014 | 2 | 2 | inspect > execute > create > execute > inspect > create > execute | write, read, list, edit, search | .js, .tsx, .css, .md, .json |
| B015 | 2 | 1 | modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify | edit, read, build:npm, write | .tsx, .css, .md |
| B016 | 2 | 1 | inspect > create > modify > execute > modify > create > modify > execute > modify | edit, write, build:npm, read, list | .tsx, .md, .css, .html |
| B017 | 2 | 2 | modify > execute > inspect > execute > inspect > execute > modify > execute | edit, read, search, list, write | .odin, .md, .png, .dll, .0 |
| B018 | 2 | 1 | execute > modify > execute > inspect > create > execute > create > execute | write, read, dev:bun, build:bun, search | .ts, .svelte, .env |
| B019 | 2 | 1 | inspect > create > execute > create > search > tool > execute > create | edit, read, write, run:epilog.exe, compile | .c, .h, .md, makefile, .exe |
| B020 | 2 | 1 | create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search | edit, write, read, compile, create | .cpp, .exe, .hpp, makefile, .md |
| B021 | 2 | 1 | execute > inspect > execute > inspect > execute > inspect > modify > execute > inspect > modify > tool > execute | read, edit, run:adb, search, run:node | .svelte, .log, .png, .mjs, .yml |
| B022 | 2 | 1 | execute > search > tool > execute > tool > execute > inspect > execute > search > tool | read, search, run:python, run:glab, run:adb | .png, .apk, .md, .0, .sh |
| B023 | 1 | 1 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, write, run:python, read, list | .py, .md, license, .cfml, .c |
| B024 | 1 | 1 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | edit, run:python, write, search, read | .py, .cfml, .gitignore |
| B025 | 1 | 1 | modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify | search, edit, build:npm, list, read | .scss, .ts, .css |
| B026 | 1 | 1 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | list, read, write, edit, search | .html, .md |
| B027 | 1 | 1 | execute > inspect > search > inspect > modify > tool > execute | read, run:npx, list, edit | .json, .html, .js |
| B028 | 1 | 1 | modify > plan > search > modify > execute > modify | edit, read, list, search | makefile, .c, .cfg, .asm, .h |
| B029 | 1 | 1 | modify > inspect > modify > create > inspect > plan > modify > inspect > modify | edit, read, build:make, list, write | .c, .h, makefile, .o |
| B030 | 1 | 1 | execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create | read, edit, build:make, write, search | .c, .md, .h, .js, .o |
| B031 | 1 | 1 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, search, git:other, git:diff, edit | .json, .py, .ts, .md, license |
| B032 | 1 | 1 | search > plan > execute > plan > create > execute > create > execute > create | write, create, remove | .h, .cpp, makefile, .ps1 |
| B033 | 1 | 1 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .ps1, .exe |
| B034 | 1 | 1 | modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify | edit, read, write | .h, .cpp, makefile |
| B035 | 1 | 1 | modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute | write, run:yggdrasil.exe, edit, build:make, run:powershell | .jsx, .js, .ps1, .cpp, .exe |
| B036 | 1 | 1 | inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute | read, search, edit, list, run:gradle | .java, .gradle, .groovy, .properties, .md |
| B037 | 1 | 1 | execute > create > modify > execute > modify > execute > tool > execute > modify | read, search, run:python, edit, test:gradle | .java, .models, .groovy |
| B038 | 1 | 1 | tool > search > plan > execute > create | write, edit, read, list, run:npx | .tsx, .js, .ts, .json, .css |
| B039 | 1 | 1 | inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute | read, compile, search, list, test:make | .cpp, .exe, .md, .h, .hpp |
| B040 | 1 | 1 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, build:odin, list | .odin, .md, .dll, .exe, .bat |
| B041 | 1 | 1 | search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify | edit, read, search, build:odin, write | .odin, .exe |
| B042 | 1 | 1 | inspect > modify > inspect > modify > create > execute | edit, read, list, remove, write | .odin, .exe, .bin |
| B043 | 1 | 1 | search > inspect > search > inspect > plan > inspect > create | read, list | .hpp, .cpp, .md, makefile |
| B044 | 1 | 1 | create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect | read, edit, write, run:test_indexing.exe, run:test_solver.exe | .cpp, .md, makefile, .bat, .exe |
| B045 | 1 | 1 | search > inspect > search > execute > create > execute > create | write, edit, read, create, copy | .c, makefile, .sh, .h |
| B046 | 1 | 1 | create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect | run:wsl, read, write, edit, create | .sh, .output, .c, makefile |
| B047 | 1 | 1 | modify > execute > create > execute > create > execute > search > inspect > create > execute | run:wsl.exe, write, edit, search, read | .sh, .log, makefile, .output, .gz |
| B048 | 1 | 1 | execute > create > execute > create > execute > inspect > execute | run:python, write, read, list | .py |
| B049 | 1 | 1 | inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect | read, write, search, list, edit | .c, .h, .md, .exe, makefile |
| B050 | 1 | 1 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | search, read, run:build.sh, build:make | .c, .md, .ps1, .sh, .exe |
| B051 | 1 | 1 | execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify | edit, read, write, search, build:make | .c, .h, makefile, .md |
| B052 | 1 | 1 | inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect | write, read, list, create | .tsx, .md, .css, .json |
| B053 | 1 | 1 | create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect | read, edit, write, list, fetch | .ts, .tsx, .json, .output, .md |
| B054 | 1 | 1 | inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan | edit, write, read, build:npm, search | .tsx, .css, .md, .ts |
| B055 | 1 | 1 | tool > inspect > execute > modify > execute | read, run:python, search, list, git:diff | .json, .js, .svelte, .tool, .repos |
| B056 | 1 | 1 | search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan | read, edit, write, run:powershell.exe, list | .cpp, .ps1, .h, makefile, .exe |
| B057 | 1 | 1 | modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute | list, read, write, git:other, git:add | .md, .gitignore |
| B058 | 1 | 1 | modify > inspect > modify > execute > inspect > execute | run:powershell.exe, read, edit, build:odin, run:cmd | .odin, .bat, .exe, .length, .getstream |
| B059 | 1 | 1 | create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create | list, write, read, run:python.exe | .py, .txt |
| B060 | 1 | 1 | execute > search > execute > inspect > create > execute > inspect > execute > create > modify > execute > modify > execute | list, run:bun, edit, create, read | .ts |
| B061 | 1 | 1 | execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create | write, edit, read, build:bun, search | .svelte, .ts, .scss, .html, .js |
| B062 | 1 | 1 | inspect > create > execute | list, create, read | .svelte, .ts |
| B063 | 1 | 1 | create > plan > create > modify > create > plan > execute | write, edit | .hpp, .cpp |
| B064 | 1 | 1 | tool > inspect | read | .py |
| B065 | 1 | 1 | modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create | edit, read, search, write, list | .html, .json, .js, .txt, .css |
| B066 | 1 | 1 | inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create | write, read, list, edit, run:node | .ts, .kts, .kt, .md, .json |
| B067 | 1 | 1 | create > execute > create > modify > execute | read, git:checkout, git:status, list, git:add | .bat, gradlew, .jar, .properties |
| B068 | 1 | 1 | create > modify > execute > search > tool > execute > modify > create > execute > tool | read, search, list, remove, create | .yml, .log, .md, .txt, .sh |
| B069 | 1 | 1 | search > tool > execute | read, git:other, list, create, copy |  |
| B070 | 1 | 1 | modify > search > inspect > modify > inspect > search > execute > inspect > modify | read, search, edit, run:wsl | .js, .c |
| B071 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create

常见转移：[['plan', 'create', 12], ['create', 'plan', 11], ['inspect', 'create', 3], ['create', 'modify', 3], ['create', 'inspect', 2], ['modify', 'plan', 2]]

### B002

create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect; execute > inspect > execute > create > inspect > create > inspect > modify > inspect > modify > inspect > modify > create; modify > inspect > modify > inspect > modify > execute > create > inspect > create > inspect > modify > inspect > modify > execute > create > execute > modify > execute

常见转移：[['inspect', 'modify', 10], ['modify', 'inspect', 7], ['create', 'inspect', 6], ['modify', 'execute', 5], ['execute', 'create', 4], ['inspect', 'create', 3]]

### B003

inspect > modify > inspect > modify > inspect > modify > search > inspect > modify > tool > modify; create > execute > inspect > modify > inspect > modify > inspect > search > inspect > modify; modify > inspect > modify > inspect > search > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 11], ['modify', 'inspect', 8], ['search', 'inspect', 3], ['inspect', 'search', 2], ['modify', 'search', 1], ['modify', 'tool', 1]]

### B004

execute > inspect > execute > inspect > modify > execute; execute > inspect > execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect

常见转移：[['execute', 'inspect', 7], ['inspect', 'execute', 4], ['modify', 'execute', 3], ['inspect', 'modify', 2]]

### B005

search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify

常见转移：[['inspect', 'search', 5], ['modify', 'inspect', 5], ['search', 'inspect', 4], ['inspect', 'modify', 4], ['search', 'create', 2], ['create', 'modify', 2]]

### B006

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; search > execute > search > inspect > modify > search > inspect > create > modify > inspect

常见转移：[['search', 'inspect', 5], ['inspect', 'modify', 3], ['modify', 'search', 3], ['search', 'execute', 2], ['execute', 'search', 2], ['inspect', 'search', 2]]

### B007

inspect > search > inspect > search > plan > create > plan > modify > plan > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 4], ['search', 'inspect', 2], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B008

modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute

常见转移：[['modify', 'execute', 5], ['inspect', 'modify', 3], ['execute', 'create', 2], ['inspect', 'execute', 2], ['create', 'modify', 2], ['execute', 'modify', 2]]

### B009

execute > inspect > create > inspect > modify > execute; execute > inspect > modify > execute

常见转移：[['execute', 'inspect', 2], ['inspect', 'modify', 2], ['modify', 'execute', 2], ['inspect', 'create', 1], ['create', 'inspect', 1]]

### B010

inspect > modify > inspect > execute > inspect > modify; modify > search > modify > inspect > execute > inspect > modify > inspect > modify > execute > inspect > execute

常见转移：[['inspect', 'modify', 4], ['modify', 'inspect', 3], ['inspect', 'execute', 3], ['execute', 'inspect', 3], ['modify', 'search', 1], ['search', 'modify', 1]]

### B011

search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create

常见转移：[['search', 'inspect', 4], ['inspect', 'search', 4], ['search', 'execute', 1], ['execute', 'create', 1]]

### B012

execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 5], ['inspect', 'search', 4], ['search', 'inspect', 4], ['modify', 'search', 2], ['modify', 'inspect', 2], ['execute', 'create', 2]]

### B013

; tool

常见转移：[]

### B014

inspect > execute > create > execute > inspect > create > execute; inspect > execute > create > execute > inspect > modify

常见转移：[['create', 'execute', 3], ['inspect', 'execute', 2], ['execute', 'create', 2], ['execute', 'inspect', 2], ['inspect', 'create', 1], ['inspect', 'modify', 1]]

### B015

modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify; modify > inspect > modify > inspect > modify > execute > modify > inspect > create > modify > execute > modify

常见转移：[['modify', 'inspect', 5], ['modify', 'execute', 4], ['inspect', 'modify', 4], ['execute', 'modify', 3], ['modify', 'search', 1], ['search', 'modify', 1]]

### B016

inspect > create > modify > execute > modify > create > modify > execute > modify; create > modify > execute > modify > create > modify > search > inspect > modify > create > modify > execute > tool

常见转移：[['create', 'modify', 5], ['modify', 'execute', 4], ['execute', 'modify', 3], ['modify', 'create', 3], ['inspect', 'create', 1], ['modify', 'search', 1]]

### B017

modify > execute > inspect > execute > inspect > execute > modify > execute; modify > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 4], ['inspect', 'execute', 4], ['modify', 'execute', 3], ['execute', 'modify', 1]]

### B018

execute > modify > execute > inspect > create > execute > create > execute; execute > create > execute > inspect > modify > inspect > create > execute

常见转移：[['create', 'execute', 4], ['execute', 'inspect', 2], ['inspect', 'create', 2], ['execute', 'create', 2], ['execute', 'modify', 1], ['modify', 'execute', 1]]

### B019

inspect > create > execute > create > search > tool > execute > create; execute > create > search > tool > execute > create > execute > modify > inspect > modify > create > inspect > modify

常见转移：[['execute', 'create', 4], ['create', 'execute', 2], ['create', 'search', 2], ['search', 'tool', 2], ['tool', 'execute', 2], ['inspect', 'modify', 2]]

### B020

create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search; create > plan > execute > plan > execute > create > inspect > execute > search > plan > execute > create > plan > create > plan > create

常见转移：[['plan', 'execute', 6], ['create', 'plan', 5], ['execute', 'plan', 3], ['plan', 'create', 3], ['execute', 'create', 3], ['create', 'inspect', 2]]

### B021

execute > inspect > execute > inspect > execute > inspect > modify > execute > inspect > modify > tool > execute; execute > modify > create > modify > execute > inspect > execute > inspect > execute > modify > execute > inspect

常见转移：[['execute', 'inspect', 7], ['inspect', 'execute', 4], ['modify', 'execute', 3], ['inspect', 'modify', 2], ['execute', 'modify', 2], ['modify', 'tool', 1]]

### B022

execute > search > tool > execute > tool > execute > inspect > execute > search > tool; tool > execute > inspect > execute > search > tool > execute > inspect > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 5], ['tool', 'execute', 4], ['execute', 'search', 3], ['search', 'tool', 3], ['execute', 'tool', 1]]

### B023

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan

常见转移：[['inspect', 'modify', 2], ['execute', 'modify', 1], ['modify', 'create', 1], ['create', 'execute', 1], ['execute', 'inspect', 1], ['modify', 'inspect', 1]]

### B024

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify

常见转移：[['plan', 'modify', 2], ['plan', 'create', 2], ['create', 'plan', 2], ['modify', 'execute', 2], ['execute', 'modify', 2], ['modify', 'create', 1]]

### B025

modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify

常见转移：[['modify', 'search', 4], ['search', 'modify', 3], ['search', 'execute', 2], ['execute', 'search', 2], ['search', 'inspect', 1], ['inspect', 'modify', 1]]

### B026

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute

常见转移：[['execute', 'search', 2], ['inspect', 'execute', 1], ['search', 'tool', 1], ['tool', 'create', 1], ['create', 'execute', 1], ['search', 'execute', 1]]

### B027

execute > inspect > search > inspect > modify > tool > execute

常见转移：[['execute', 'inspect', 1], ['inspect', 'search', 1], ['search', 'inspect', 1], ['inspect', 'modify', 1], ['modify', 'tool', 1], ['tool', 'execute', 1]]

### B028

modify > plan > search > modify > execute > modify

常见转移：[['modify', 'plan', 1], ['plan', 'search', 1], ['search', 'modify', 1], ['modify', 'execute', 1], ['execute', 'modify', 1]]

### B029

modify > inspect > modify > create > inspect > plan > modify > inspect > modify

常见转移：[['modify', 'inspect', 2], ['inspect', 'modify', 2], ['modify', 'create', 1], ['create', 'inspect', 1], ['inspect', 'plan', 1], ['plan', 'modify', 1]]

### B030

execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create

常见转移：[['execute', 'inspect', 3], ['inspect', 'modify', 2], ['modify', 'execute', 2], ['inspect', 'search', 2], ['search', 'inspect', 2], ['inspect', 'create', 1]]

### B031

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify

常见转移：[['inspect', 'execute', 4], ['execute', 'inspect', 3], ['tool', 'inspect', 2], ['inspect', 'search', 1], ['search', 'tool', 1], ['inspect', 'tool', 1]]

### B032

search > plan > execute > plan > create > execute > create > execute > create

常见转移：[['create', 'execute', 2], ['execute', 'create', 2], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1]]

### B033

create

常见转移：[]

### B034

modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify

常见转移：[['inspect', 'modify', 3], ['modify', 'inspect', 2], ['modify', 'execute', 2], ['plan', 'create', 2], ['execute', 'inspect', 1], ['execute', 'tool', 1]]

### B035

modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute

常见转移：[['create', 'execute', 4], ['execute', 'create', 3], ['modify', 'create', 1], ['create', 'inspect', 1], ['inspect', 'execute', 1], ['execute', 'plan', 1]]

### B036

inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute

常见转移：[['inspect', 'execute', 4], ['execute', 'inspect', 3], ['execute', 'create', 1], ['create', 'execute', 1]]

### B037

execute > create > modify > execute > modify > execute > tool > execute > modify

常见转移：[['modify', 'execute', 2], ['execute', 'modify', 2], ['execute', 'create', 1], ['create', 'modify', 1], ['execute', 'tool', 1], ['tool', 'execute', 1]]

### B038

tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B039

inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute

常见转移：[['inspect', 'execute', 3], ['execute', 'inspect', 2], ['execute', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'modify', 1]]

### B040

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute

常见转移：[['execute', 'inspect', 2], ['inspect', 'execute', 2], ['execute', 'plan', 2], ['plan', 'execute', 2], ['plan', 'create', 1], ['create', 'plan', 1]]

### B041

search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 7], ['modify', 'inspect', 5], ['search', 'inspect', 1], ['modify', 'execute', 1], ['execute', 'inspect', 1], ['inspect', 'search', 1]]

### B042

inspect > modify > inspect > modify > create > execute

常见转移：[['inspect', 'modify', 2], ['modify', 'inspect', 1], ['modify', 'create', 1], ['create', 'execute', 1]]

### B043

search > inspect > search > inspect > plan > inspect > create

常见转移：[['search', 'inspect', 2], ['inspect', 'search', 1], ['inspect', 'plan', 1], ['plan', 'inspect', 1], ['inspect', 'create', 1]]

### B044

create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect

常见转移：[['execute', 'inspect', 3], ['inspect', 'modify', 2], ['create', 'modify', 1], ['modify', 'plan', 1], ['plan', 'create', 1], ['create', 'plan', 1]]

### B045

search > inspect > search > execute > create > execute > create

常见转移：[['execute', 'create', 2], ['search', 'inspect', 1], ['inspect', 'search', 1], ['search', 'execute', 1], ['create', 'execute', 1]]

### B046

create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect

常见转移：[['create', 'inspect', 3], ['inspect', 'modify', 3], ['modify', 'execute', 2], ['execute', 'create', 2], ['modify', 'inspect', 1]]

### B047

modify > execute > create > execute > create > execute > search > inspect > create > execute

常见转移：[['create', 'execute', 3], ['execute', 'create', 2], ['modify', 'execute', 1], ['execute', 'search', 1], ['search', 'inspect', 1], ['inspect', 'create', 1]]

### B048

execute > create > execute > create > execute > inspect > execute

常见转移：[['execute', 'create', 2], ['create', 'execute', 2], ['execute', 'inspect', 1], ['inspect', 'execute', 1]]

### B049

inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect

常见转移：[['inspect', 'execute', 3], ['execute', 'inspect', 2], ['search', 'inspect', 2], ['inspect', 'search', 2], ['plan', 'execute', 2], ['execute', 'search', 1]]

### B050

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect

常见转移：[['modify', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'tool', 1], ['tool', 'search', 1]]

### B051

execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify

常见转移：[['inspect', 'create', 3], ['plan', 'search', 2], ['search', 'inspect', 2], ['create', 'inspect', 2], ['execute', 'tool', 1], ['tool', 'plan', 1]]

### B052

inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect

常见转移：[['create', 'plan', 5], ['plan', 'create', 4], ['plan', 'execute', 2], ['execute', 'create', 2], ['inspect', 'tool', 1], ['tool', 'search', 1]]

### B053

create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['create', 'inspect', 3], ['inspect', 'create', 3], ['create', 'plan', 2], ['plan', 'create', 2], ['execute', 'inspect', 2], ['inspect', 'execute', 1]]

### B054

inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan

常见转移：[['modify', 'plan', 5], ['plan', 'modify', 3], ['inspect', 'modify', 2], ['plan', 'execute', 2], ['execute', 'plan', 2], ['plan', 'create', 1]]

### B055

tool > inspect > execute > modify > execute

常见转移：[['tool', 'inspect', 1], ['inspect', 'execute', 1], ['execute', 'modify', 1], ['modify', 'execute', 1]]

### B056

search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['create', 'plan', 3], ['search', 'inspect', 2], ['plan', 'create', 2], ['inspect', 'plan', 1], ['plan', 'search', 1], ['inspect', 'create', 1]]

### B057

modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute

常见转移：[['modify', 'execute', 2], ['execute', 'modify', 1], ['execute', 'plan', 1], ['plan', 'execute', 1], ['execute', 'search', 1], ['search', 'inspect', 1]]

### B058

modify > inspect > modify > execute > inspect > execute

常见转移：[['modify', 'inspect', 1], ['inspect', 'modify', 1], ['modify', 'execute', 1], ['execute', 'inspect', 1], ['inspect', 'execute', 1]]

### B059

create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create

常见转移：[['inspect', 'create', 2], ['create', 'search', 1], ['search', 'inspect', 1], ['create', 'execute', 1], ['execute', 'search', 1], ['search', 'execute', 1]]

### B060

execute > search > execute > inspect > create > execute > inspect > execute > create > modify > execute > modify > execute

常见转移：[['execute', 'inspect', 2], ['modify', 'execute', 2], ['execute', 'search', 1], ['search', 'execute', 1], ['inspect', 'create', 1], ['create', 'execute', 1]]

### B061

execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create

常见转移：[['plan', 'execute', 2], ['create', 'inspect', 2], ['plan', 'create', 2], ['execute', 'modify', 1], ['modify', 'execute', 1], ['execute', 'tool', 1]]

### B062

inspect > create > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1]]

### B063

create > plan > create > modify > create > plan > execute

常见转移：[['create', 'plan', 2], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'create', 1], ['plan', 'execute', 1]]

### B064

tool > inspect

常见转移：[['tool', 'inspect', 1]]

### B065

modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 3], ['inspect', 'modify', 2], ['tool', 'inspect', 2], ['search', 'inspect', 1], ['search', 'modify', 1], ['modify', 'inspect', 1]]

### B066

inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create

常见转移：[['inspect', 'execute', 3], ['execute', 'inspect', 2], ['execute', 'create', 2], ['modify', 'inspect', 2], ['inspect', 'modify', 2], ['create', 'modify', 1]]

### B067

create > execute > create > modify > execute

常见转移：[['create', 'execute', 1], ['execute', 'create', 1], ['create', 'modify', 1], ['modify', 'execute', 1]]

### B068

create > modify > execute > search > tool > execute > modify > create > execute > tool

常见转移：[['create', 'modify', 1], ['modify', 'execute', 1], ['execute', 'search', 1], ['search', 'tool', 1], ['tool', 'execute', 1], ['execute', 'modify', 1]]

### B069

search > tool > execute

常见转移：[['search', 'tool', 1], ['tool', 'execute', 1]]

### B070

modify > search > inspect > modify > inspect > search > execute > inspect > modify

常见转移：[['inspect', 'modify', 2], ['modify', 'search', 1], ['search', 'inspect', 1], ['modify', 'inspect', 1], ['inspect', 'search', 1], ['search', 'execute', 1]]

### B071

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

