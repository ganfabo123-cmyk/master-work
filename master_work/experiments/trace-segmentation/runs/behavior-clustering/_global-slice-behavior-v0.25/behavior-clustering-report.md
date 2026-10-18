# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：41
- 相似度阈值：0.25
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：20

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 6 | 4 | search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect | edit, read, search, write, list | .css, .odin, .ts, .html, .scss |
| B002 | 6 | 3 | execute > inspect > execute > inspect > modify > execute | read, edit, search, list, run:powershell.exe | .odin, .md, .ts, .png, .output |
| B003 | 5 | 4 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, list, write | .odin, .1, .c, .hpp, .h |
| B004 | 5 | 3 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, search, edit, run:adb, list | .java, .svelte, .ts, .json, .log |
| B005 | 5 | 2 | modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify | read, edit, search, run:python, write | .java, .groovy, .tsx, .md, .css |
| B006 | 5 | 4 | execute > create > execute > create > execute > inspect > execute | write, read, list, edit, search | .js, .tsx, .css, .ts, .py |
| B007 | 4 | 4 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, edit, run:python, read, list | .py, .cfml, .cpp, .md, .c |
| B008 | 4 | 4 | create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect | read, edit, write, run:wsl, run:epilog.exe | .tsx, .c, .sh, .py, .h |
| B009 | 3 | 3 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, read, write, list, build:make | .c, .odin, .py, .h, .md |
| B010 | 3 | 2 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | edit, read, write, search, list | .ts, .json, .html, .js, .mjs |
| B011 | 3 | 3 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | list, write, read, edit, run:bun | .html, .ts, .py, .md, .txt |
| B012 | 3 | 3 | execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create | edit, read, write, run:wsl, search | .c, .sh, .md, .h, makefile |
| B013 | 3 | 2 | modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify | edit, read, write, build:npm | .h, .cpp, .tsx, .css, makefile |
| B014 | 3 | 3 | inspect > modify > inspect > execute > inspect > modify | read, edit, search, fetch, run:wsl | .js, .odin, .c |
| B015 | 3 | 2 | execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create | edit, write, read, search, create | .cpp, .svelte, .ts, .exe, .hpp |
| B016 | 2 | 1 | search > plan > execute > plan > create > execute > create > execute > create | write, run:yggdrasil.exe, edit, build:make, run:powershell | .jsx, .js, .ps1, .cpp, .h |
| B017 | 2 | 2 | execute > inspect > create > inspect > modify > execute | read, run:python, search, list, run:glab | .md, .jsonl, .yml, .py, .json |
| B018 | 2 | 2 | inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute | read, compile, edit, search, list | .cpp, .md, .exe, .hpp, .h |
| B019 | 2 | 2 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .c, .md, .h, .exe |
| B020 | 2 | 1 | search > inspect > search > execute > create > execute > create | write, edit, read, run:wsl.exe, search | .sh, .c, makefile, .h, .log |
| B021 | 2 | 2 |  |  |  |
| B022 | 2 | 2 | execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify | read, edit, write, run:powershell.exe, search | .cpp, .h, makefile, .c, .ps1 |
| B023 | 2 | 1 | inspect > create > execute > create > search > tool > execute > create | edit, read, write, run:epilog.exe, compile | .c, .h, .md, makefile, .exe |
| B024 | 2 | 1 | create > execute > create > modify > execute | read, search, list, remove, create | .yml, .log, .md, .txt, .sh |
| B025 | 2 | 1 | execute > search > tool > execute > tool > execute > inspect > execute > search > tool | read, search, run:python, run:glab, run:adb | .png, .apk, .md, .0, .sh |
| B026 | 1 | 1 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | edit, run:python, write, search, read | .py, .cfml, .gitignore |
| B027 | 1 | 1 | modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify | search, edit, build:npm, list, read | .scss, .ts, .css |
| B028 | 1 | 1 | execute > inspect > search > inspect > modify > tool > execute | read, run:npx, list, edit | .json, .html, .js |
| B029 | 1 | 1 | modify > plan > search > modify > execute > modify | edit, read, list, search | makefile, .c, .cfg, .asm, .h |
| B030 | 1 | 1 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .ps1, .exe |
| B031 | 1 | 1 | tool > search > plan > execute > create | write, edit, read, list, run:npx | .tsx, .js, .ts, .json, .css |
| B032 | 1 | 1 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | search, read, run:build.sh, build:make | .c, .md, .ps1, .sh, .exe |
| B033 | 1 | 1 | create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect | read, edit, write, list, fetch | .ts, .tsx, .json, .output, .md |
| B034 | 1 | 1 | inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan | edit, write, read, build:npm, search | .tsx, .css, .md, .ts |
| B035 | 1 | 1 | tool > inspect > execute > modify > execute | read, run:python, search, list, git:diff | .json, .js, .svelte, .tool, .repos |
| B036 | 1 | 1 | modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute | list, read, write, git:other, git:add | .md, .gitignore |
| B037 | 1 | 1 | inspect > create > execute | list, create, read | .svelte, .ts |
| B038 | 1 | 1 | create > plan > create > modify > create > plan > execute | write, edit | .hpp, .cpp |
| B039 | 1 | 1 | tool > inspect | read | .py |
| B040 | 1 | 1 | search > tool > execute | read, git:other, list, create, copy |  |
| B041 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify; inspect > modify > inspect > modify > inspect > modify > search > inspect > modify > tool > modify; create > execute > inspect > modify > inspect > modify > inspect > search > inspect > modify

常见转移：[['inspect', 'modify', 22], ['modify', 'inspect', 18], ['search', 'inspect', 8], ['inspect', 'search', 8], ['search', 'create', 3], ['modify', 'search', 3]]

### B002

execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute > modify > execute; modify > inspect > modify > execute > inspect > execute; execute > inspect > execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 12], ['inspect', 'execute', 9], ['modify', 'execute', 7], ['inspect', 'modify', 3], ['execute', 'modify', 1], ['modify', 'inspect', 1]]

### B003

inspect > search > inspect > search > plan > create > plan > modify > plan > create; search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 9], ['search', 'inspect', 8], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B004

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create; execute > inspect > execute > inspect > execute > inspect > modify > execute > inspect > modify > tool > execute; execute > modify > create > modify > execute > inspect > execute > inspect > execute > modify > execute > inspect

常见转移：[['inspect', 'execute', 15], ['execute', 'inspect', 15], ['inspect', 'modify', 4], ['execute', 'modify', 3], ['execute', 'create', 3], ['modify', 'execute', 3]]

### B005

modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; execute > create > modify > execute > modify > execute > tool > execute > modify; inspect > create > modify > execute > modify > create > modify > execute > modify; create > modify > execute > modify > create > modify > search > inspect > modify > create > modify > execute > tool

常见转移：[['modify', 'execute', 11], ['create', 'modify', 8], ['execute', 'modify', 7], ['inspect', 'modify', 4], ['modify', 'create', 4], ['execute', 'create', 3]]

### B006

execute > create > execute > create > execute > inspect > execute; inspect > execute > create > execute > inspect > create > execute; execute > modify > execute > inspect > create > execute > create > execute; execute > create > execute > inspect > modify > inspect > create > execute; inspect > execute > create > execute > inspect > modify

常见转移：[['create', 'execute', 9], ['execute', 'create', 6], ['execute', 'inspect', 5], ['inspect', 'execute', 3], ['inspect', 'create', 3], ['inspect', 'modify', 2]]

### B007

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create; inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect

常见转移：[['create', 'plan', 16], ['plan', 'create', 16], ['create', 'inspect', 3], ['inspect', 'create', 3], ['plan', 'execute', 3], ['execute', 'create', 3]]

### B008

create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect; create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect; execute > inspect > execute > create > inspect > create > inspect > modify > inspect > modify > inspect > modify > create; modify > inspect > modify > inspect > modify > execute > create > inspect > create > inspect > modify > inspect > modify > execute > create > execute > modify > execute

常见转移：[['inspect', 'modify', 13], ['create', 'inspect', 9], ['modify', 'inspect', 8], ['modify', 'execute', 7], ['execute', 'create', 6], ['inspect', 'create', 3]]

### B009

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; modify > inspect > modify > create > inspect > plan > modify > inspect > modify; inspect > modify > inspect > modify > create > execute

常见转移：[['inspect', 'modify', 6], ['modify', 'inspect', 4], ['modify', 'create', 3], ['create', 'execute', 2], ['inspect', 'plan', 2], ['execute', 'modify', 1]]

### B010

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; search > execute > search > inspect > modify > search > inspect > create > modify > inspect; modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 6], ['search', 'inspect', 6], ['inspect', 'modify', 5], ['inspect', 'search', 3], ['inspect', 'create', 3], ['create', 'modify', 3]]

### B011

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute; create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create; execute > search > execute > inspect > create > execute > inspect > execute > create > modify > execute > modify > execute

常见转移：[['execute', 'search', 4], ['inspect', 'execute', 3], ['create', 'execute', 3], ['search', 'execute', 3], ['execute', 'create', 3], ['modify', 'execute', 3]]

### B012

execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 7], ['inspect', 'search', 6], ['search', 'inspect', 6], ['execute', 'inspect', 4], ['modify', 'execute', 3], ['modify', 'search', 2]]

### B013

modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify; modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify; modify > inspect > modify > inspect > modify > execute > modify > inspect > create > modify > execute > modify

常见转移：[['modify', 'inspect', 7], ['inspect', 'modify', 7], ['modify', 'execute', 6], ['execute', 'modify', 3], ['inspect', 'create', 2], ['plan', 'create', 2]]

### B014

inspect > modify > inspect > execute > inspect > modify; modify > search > modify > inspect > execute > inspect > modify > inspect > modify > execute > inspect > execute; modify > search > inspect > modify > inspect > search > execute > inspect > modify

常见转移：[['inspect', 'modify', 6], ['modify', 'inspect', 4], ['execute', 'inspect', 4], ['inspect', 'execute', 3], ['modify', 'search', 2], ['search', 'modify', 1]]

### B015

execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create; create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search; create > plan > execute > plan > execute > create > inspect > execute > search > plan > execute > create > plan > create > plan > create

常见转移：[['plan', 'execute', 8], ['create', 'plan', 6], ['plan', 'create', 5], ['execute', 'plan', 4], ['execute', 'create', 4], ['create', 'inspect', 4]]

### B016

search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute

常见转移：[['create', 'execute', 6], ['execute', 'create', 5], ['execute', 'plan', 2], ['plan', 'create', 2], ['search', 'plan', 1], ['plan', 'execute', 1]]

### B017

execute > inspect > create > inspect > modify > execute; execute > inspect > modify > execute

常见转移：[['execute', 'inspect', 2], ['inspect', 'modify', 2], ['modify', 'execute', 2], ['inspect', 'create', 1], ['create', 'inspect', 1]]

### B018

inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 4], ['inspect', 'modify', 3], ['plan', 'execute', 2], ['modify', 'inspect', 2], ['modify', 'execute', 2]]

### B019

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect

常见转移：[['inspect', 'execute', 5], ['execute', 'inspect', 4], ['plan', 'execute', 4], ['execute', 'plan', 3], ['create', 'plan', 2], ['search', 'inspect', 2]]

### B020

search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute

常见转移：[['execute', 'create', 4], ['create', 'execute', 4], ['search', 'inspect', 2], ['inspect', 'search', 1], ['search', 'execute', 1], ['modify', 'execute', 1]]

### B021

; tool

常见转移：[]

### B022

execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify; search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['search', 'inspect', 4], ['inspect', 'create', 4], ['create', 'plan', 4], ['plan', 'search', 3], ['modify', 'inspect', 2], ['create', 'inspect', 2]]

### B023

inspect > create > execute > create > search > tool > execute > create; execute > create > search > tool > execute > create > execute > modify > inspect > modify > create > inspect > modify

常见转移：[['execute', 'create', 4], ['create', 'execute', 2], ['create', 'search', 2], ['search', 'tool', 2], ['tool', 'execute', 2], ['inspect', 'modify', 2]]

### B024

create > execute > create > modify > execute; create > modify > execute > search > tool > execute > modify > create > execute > tool

常见转移：[['create', 'execute', 2], ['create', 'modify', 2], ['modify', 'execute', 2], ['execute', 'create', 1], ['execute', 'search', 1], ['search', 'tool', 1]]

### B025

execute > search > tool > execute > tool > execute > inspect > execute > search > tool; tool > execute > inspect > execute > search > tool > execute > inspect > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 5], ['tool', 'execute', 4], ['execute', 'search', 3], ['search', 'tool', 3], ['execute', 'tool', 1]]

### B026

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify

常见转移：[['plan', 'modify', 2], ['plan', 'create', 2], ['create', 'plan', 2], ['modify', 'execute', 2], ['execute', 'modify', 2], ['modify', 'create', 1]]

### B027

modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify

常见转移：[['modify', 'search', 4], ['search', 'modify', 3], ['search', 'execute', 2], ['execute', 'search', 2], ['search', 'inspect', 1], ['inspect', 'modify', 1]]

### B028

execute > inspect > search > inspect > modify > tool > execute

常见转移：[['execute', 'inspect', 1], ['inspect', 'search', 1], ['search', 'inspect', 1], ['inspect', 'modify', 1], ['modify', 'tool', 1], ['tool', 'execute', 1]]

### B029

modify > plan > search > modify > execute > modify

常见转移：[['modify', 'plan', 1], ['plan', 'search', 1], ['search', 'modify', 1], ['modify', 'execute', 1], ['execute', 'modify', 1]]

### B030

create

常见转移：[]

### B031

tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B032

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect

常见转移：[['modify', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'tool', 1], ['tool', 'search', 1]]

### B033

create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['create', 'inspect', 3], ['inspect', 'create', 3], ['create', 'plan', 2], ['plan', 'create', 2], ['execute', 'inspect', 2], ['inspect', 'execute', 1]]

### B034

inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan

常见转移：[['modify', 'plan', 5], ['plan', 'modify', 3], ['inspect', 'modify', 2], ['plan', 'execute', 2], ['execute', 'plan', 2], ['plan', 'create', 1]]

### B035

tool > inspect > execute > modify > execute

常见转移：[['tool', 'inspect', 1], ['inspect', 'execute', 1], ['execute', 'modify', 1], ['modify', 'execute', 1]]

### B036

modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute

常见转移：[['modify', 'execute', 2], ['execute', 'modify', 1], ['execute', 'plan', 1], ['plan', 'execute', 1], ['execute', 'search', 1], ['search', 'inspect', 1]]

### B037

inspect > create > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1]]

### B038

create > plan > create > modify > create > plan > execute

常见转移：[['create', 'plan', 2], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'create', 1], ['plan', 'execute', 1]]

### B039

tool > inspect

常见转移：[['tool', 'inspect', 1]]

### B040

search > tool > execute

常见转移：[['search', 'tool', 1], ['tool', 'execute', 1]]

### B041

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

