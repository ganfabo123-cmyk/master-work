# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：37
- 相似度阈值：0.25
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：21

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 11 | 5 | inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute | read, edit, search, run:adb, list | .odin, .java, .svelte, .md, .log |
| B002 | 6 | 4 | search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect | edit, read, search, write, list | .css, .odin, .ts, .html, .scss |
| B003 | 5 | 4 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, list, write | .odin, .1, .c, .hpp, .h |
| B004 | 5 | 4 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .cpp, .c, .exe, .md |
| B005 | 4 | 4 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, search, list, edit, run:python | .java, .json, .cpp, .md, .png |
| B006 | 4 | 3 | search > inspect > search > execute > create > execute > create | write, edit, read, run:wsl.exe, search | .sh, .c, makefile, .py, .h |
| B007 | 4 | 4 | create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect | read, edit, write, run:wsl, run:epilog.exe | .tsx, .c, .sh, .py, .h |
| B008 | 3 | 3 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, edit, run:python, read, list | .py, .cfml, .cpp, .hpp, .md |
| B009 | 3 | 3 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, read, write, list, run:python | .odin, .ts, .py, .md, license |
| B010 | 3 | 2 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | edit, read, write, search, list | .ts, .json, .html, .js, .mjs |
| B011 | 3 | 3 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | list, write, read, edit, run:bun | .html, .ts, .py, .md, .txt |
| B012 | 3 | 2 | inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create | read, write, edit, list, fetch | .ts, .tsx, .json, .h, .c |
| B013 | 3 | 2 | modify > inspect > modify > create > inspect > plan > modify > inspect > modify | edit, read, build:make, list, write | .c, .tsx, .h, .css, makefile |
| B014 | 3 | 3 | execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create | edit, read, write, run:wsl, search | .c, .sh, .md, .h, makefile |
| B015 | 3 | 2 | modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify | read, search, edit, run:python, test:gradle | .java, .groovy, .md, .models, .bat |
| B016 | 3 | 3 | execute > inspect > create > inspect > modify > execute | read, run:python, search, list, edit | .json, .md, .jsonl, .js, .yml |
| B017 | 3 | 3 | inspect > execute > create > execute > inspect > create > execute | read, write, list, edit, search | .js, .tsx, .css, .ts, .md |
| B018 | 2 | 1 | search > plan > execute > plan > create > execute > create > execute > create | write, run:yggdrasil.exe, edit, build:make, run:powershell | .jsx, .js, .ps1, .cpp, .h |
| B019 | 2 | 2 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .ps1, .exe |
| B020 | 2 | 2 | inspect > modify > inspect > execute > inspect > modify | read, search, edit, run:wsl | .js, .odin, .c |
| B021 | 2 | 2 |  |  |  |
| B022 | 2 | 2 | execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify | read, edit, write, run:powershell.exe, search | .cpp, .h, makefile, .c, .ps1 |
| B023 | 2 | 1 | inspect > create > modify > execute > modify > create > modify > execute > modify | edit, write, build:npm, read, list | .tsx, .md, .css, .html |
| B024 | 2 | 1 | inspect > create > execute > create > search > tool > execute > create | edit, read, write, run:epilog.exe, compile | .c, .h, .md, makefile, .exe |
| B025 | 2 | 1 | create > modify > execute > search > tool > execute > modify > create > execute > tool | read, search, list, remove, create | .yml, .log, .md, .txt, .sh |
| B026 | 1 | 1 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | edit, run:python, write, search, read | .py, .cfml, .gitignore |
| B027 | 1 | 1 | modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify | search, edit, build:npm, list, read | .scss, .ts, .css |
| B028 | 1 | 1 | execute > inspect > search > inspect > modify > tool > execute | read, run:npx, list, edit | .json, .html, .js |
| B029 | 1 | 1 | modify > plan > search > modify > execute > modify | edit, read, list, search | makefile, .c, .cfg, .asm, .h |
| B030 | 1 | 1 | modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify | edit, read, write | .h, .cpp, makefile |
| B031 | 1 | 1 | tool > search > plan > execute > create | write, edit, read, list, run:npx | .tsx, .js, .ts, .json, .css |
| B032 | 1 | 1 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | search, read, run:build.sh, build:make | .c, .md, .ps1, .sh, .exe |
| B033 | 1 | 1 | inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan | edit, write, read, build:npm, search | .tsx, .css, .md, .ts |
| B034 | 1 | 1 | modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute | list, read, write, git:other, git:add | .md, .gitignore |
| B035 | 1 | 1 | tool > inspect | read | .py |
| B036 | 1 | 1 | search > tool > execute | read, git:other, list, create, copy |  |
| B037 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect; execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute > modify > execute; modify > search > modify > inspect > execute > inspect > modify > inspect > modify > execute > inspect > execute

常见转移：[['execute', 'inspect', 26], ['inspect', 'execute', 17], ['modify', 'execute', 15], ['inspect', 'modify', 11], ['execute', 'modify', 4], ['modify', 'inspect', 4]]

### B002

search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify; inspect > modify > inspect > modify > inspect > modify > search > inspect > modify > tool > modify; create > execute > inspect > modify > inspect > modify > inspect > search > inspect > modify

常见转移：[['inspect', 'modify', 22], ['modify', 'inspect', 18], ['search', 'inspect', 8], ['inspect', 'search', 8], ['search', 'create', 3], ['modify', 'search', 3]]

### B003

inspect > search > inspect > search > plan > create > plan > modify > plan > create; search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 9], ['search', 'inspect', 8], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B004

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect; execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create; create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search; create > plan > execute > plan > execute > create > inspect > execute > search > plan > execute > create > plan > create > plan > create

常见转移：[['plan', 'execute', 12], ['create', 'plan', 8], ['inspect', 'execute', 7], ['execute', 'plan', 7], ['plan', 'create', 6], ['execute', 'create', 5]]

### B005

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; tool > execute > inspect > execute > search > tool > execute > inspect > execute > inspect > execute > inspect > execute

常见转移：[['inspect', 'execute', 15], ['execute', 'inspect', 12], ['search', 'tool', 2], ['tool', 'inspect', 2], ['execute', 'modify', 2], ['execute', 'search', 2]]

### B006

search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute; execute > create > execute > create > execute > inspect > execute; execute > modify > execute > inspect > create > execute > create > execute

常见转移：[['create', 'execute', 8], ['execute', 'create', 7], ['search', 'inspect', 2], ['modify', 'execute', 2], ['inspect', 'create', 2], ['execute', 'inspect', 2]]

### B007

create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect; create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect; execute > inspect > execute > create > inspect > create > inspect > modify > inspect > modify > inspect > modify > create; modify > inspect > modify > inspect > modify > execute > create > inspect > create > inspect > modify > inspect > modify > execute > create > execute > modify > execute

常见转移：[['inspect', 'modify', 13], ['create', 'inspect', 9], ['modify', 'inspect', 8], ['modify', 'execute', 7], ['execute', 'create', 6], ['inspect', 'create', 3]]

### B008

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create; create > plan > create > modify > create > plan > execute

常见转移：[['create', 'plan', 9], ['plan', 'create', 7], ['create', 'modify', 3], ['inspect', 'create', 2], ['plan', 'execute', 2], ['modify', 'create', 2]]

### B009

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; inspect > modify > inspect > modify > create > execute; inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create

常见转移：[['inspect', 'modify', 6], ['modify', 'inspect', 4], ['modify', 'create', 3], ['create', 'execute', 3], ['execute', 'inspect', 3], ['inspect', 'execute', 3]]

### B010

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; search > execute > search > inspect > modify > search > inspect > create > modify > inspect; modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 6], ['search', 'inspect', 6], ['inspect', 'modify', 5], ['inspect', 'search', 3], ['inspect', 'create', 3], ['create', 'modify', 3]]

### B011

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute; create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create; execute > search > execute > inspect > create > execute > inspect > execute > create > modify > execute > modify > execute

常见转移：[['execute', 'search', 4], ['inspect', 'execute', 3], ['create', 'execute', 3], ['search', 'execute', 3], ['execute', 'create', 3], ['modify', 'execute', 3]]

### B012

inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect; create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['plan', 'create', 12], ['create', 'plan', 11], ['create', 'inspect', 5], ['inspect', 'create', 4], ['inspect', 'search', 3], ['search', 'plan', 2]]

### B013

modify > inspect > modify > create > inspect > plan > modify > inspect > modify; modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify; modify > inspect > modify > inspect > modify > execute > modify > inspect > create > modify > execute > modify

常见转移：[['modify', 'inspect', 7], ['inspect', 'modify', 6], ['modify', 'execute', 4], ['execute', 'modify', 3], ['plan', 'modify', 2], ['modify', 'create', 1]]

### B014

execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 7], ['inspect', 'search', 6], ['search', 'inspect', 6], ['execute', 'inspect', 4], ['modify', 'execute', 3], ['modify', 'search', 2]]

### B015

modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; execute > create > modify > execute > modify > execute > tool > execute > modify; create > execute > create > modify > execute

常见转移：[['modify', 'execute', 5], ['execute', 'create', 4], ['create', 'modify', 3], ['execute', 'modify', 3], ['create', 'inspect', 1], ['inspect', 'modify', 1]]

### B016

execute > inspect > create > inspect > modify > execute; tool > inspect > execute > modify > execute; execute > inspect > modify > execute

常见转移：[['modify', 'execute', 3], ['execute', 'inspect', 2], ['inspect', 'modify', 2], ['inspect', 'create', 1], ['create', 'inspect', 1], ['tool', 'inspect', 1]]

### B017

inspect > execute > create > execute > inspect > create > execute; execute > create > execute > inspect > modify > inspect > create > execute; inspect > execute > create > execute > inspect > modify

常见转移：[['create', 'execute', 5], ['execute', 'create', 3], ['execute', 'inspect', 3], ['inspect', 'execute', 2], ['inspect', 'create', 2], ['inspect', 'modify', 2]]

### B018

search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute

常见转移：[['create', 'execute', 6], ['execute', 'create', 5], ['execute', 'plan', 2], ['plan', 'create', 2], ['search', 'plan', 1], ['plan', 'execute', 1]]

### B019

create; inspect > create > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1]]

### B020

inspect > modify > inspect > execute > inspect > modify; modify > search > inspect > modify > inspect > search > execute > inspect > modify

常见转移：[['inspect', 'modify', 4], ['modify', 'inspect', 2], ['execute', 'inspect', 2], ['inspect', 'execute', 1], ['modify', 'search', 1], ['search', 'inspect', 1]]

### B021

; tool

常见转移：[]

### B022

execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify; search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['search', 'inspect', 4], ['inspect', 'create', 4], ['create', 'plan', 4], ['plan', 'search', 3], ['modify', 'inspect', 2], ['create', 'inspect', 2]]

### B023

inspect > create > modify > execute > modify > create > modify > execute > modify; create > modify > execute > modify > create > modify > search > inspect > modify > create > modify > execute > tool

常见转移：[['create', 'modify', 5], ['modify', 'execute', 4], ['execute', 'modify', 3], ['modify', 'create', 3], ['inspect', 'create', 1], ['modify', 'search', 1]]

### B024

inspect > create > execute > create > search > tool > execute > create; execute > create > search > tool > execute > create > execute > modify > inspect > modify > create > inspect > modify

常见转移：[['execute', 'create', 4], ['create', 'execute', 2], ['create', 'search', 2], ['search', 'tool', 2], ['tool', 'execute', 2], ['inspect', 'modify', 2]]

### B025

create > modify > execute > search > tool > execute > modify > create > execute > tool; execute > search > tool > execute > tool > execute > inspect > execute > search > tool

常见转移：[['execute', 'search', 3], ['search', 'tool', 3], ['tool', 'execute', 3], ['execute', 'tool', 2], ['create', 'modify', 1], ['modify', 'execute', 1]]

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

modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify

常见转移：[['inspect', 'modify', 3], ['modify', 'inspect', 2], ['modify', 'execute', 2], ['plan', 'create', 2], ['execute', 'inspect', 1], ['execute', 'tool', 1]]

### B031

tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B032

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect

常见转移：[['modify', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'tool', 1], ['tool', 'search', 1]]

### B033

inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan

常见转移：[['modify', 'plan', 5], ['plan', 'modify', 3], ['inspect', 'modify', 2], ['plan', 'execute', 2], ['execute', 'plan', 2], ['plan', 'create', 1]]

### B034

modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute

常见转移：[['modify', 'execute', 2], ['execute', 'modify', 1], ['execute', 'plan', 1], ['plan', 'execute', 1], ['execute', 'search', 1], ['search', 'inspect', 1]]

### B035

tool > inspect

常见转移：[['tool', 'inspect', 1]]

### B036

search > tool > execute

常见转移：[['search', 'tool', 1], ['tool', 'execute', 1]]

### B037

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

