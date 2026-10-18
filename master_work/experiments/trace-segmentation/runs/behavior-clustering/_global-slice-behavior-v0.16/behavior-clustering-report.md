# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：26
- 相似度阈值：0.16
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：16

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 12 | 8 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | write, edit, read, list, search | .c, .h, .sh, .ts, makefile |
| B002 | 9 | 6 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, read, write, list, search | .css, .odin, .ts, .html, .c |
| B003 | 8 | 5 | inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute | read, edit, search, list, run:powershell.exe | .odin, .cpp, .md, .exe, .bat |
| B004 | 7 | 4 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | read, edit, search, run:python, write | .java, .py, .groovy, .tsx, .md |
| B005 | 7 | 6 | modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify | read, edit, write, run:wsl, run:epilog.exe | .tsx, .c, .sh, .h, .py |
| B006 | 5 | 4 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, read, edit, run:python, list | .py, .cfml, .ts, .tsx, .cpp |
| B007 | 5 | 4 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, list, write | .odin, .1, .c, .hpp, .h |
| B008 | 5 | 3 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, search, edit, run:adb, list | .java, .svelte, .ts, .json, .log |
| B009 | 5 | 3 | execute > inspect > create > inspect > modify > execute | read, search, run:python, list, create | .yml, .log, .md, .json, .svelte |
| B010 | 5 | 4 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .cpp, .c, .exe, .md |
| B011 | 4 | 2 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | edit, search, read, write, list | .ts, .json, .html, .js, .scss |
| B012 | 4 | 4 | execute > inspect > search > inspect > modify > tool > execute | read, edit, write, run:wsl, list | .c, .sh, .md, .js, .h |
| B013 | 3 | 3 | inspect > modify > inspect > execute > inspect > modify | read, edit, search, fetch, run:wsl | .js, .odin, .c |
| B014 | 2 | 1 | search > plan > execute > plan > create > execute > create > execute > create | write, run:yggdrasil.exe, edit, build:make, run:powershell | .jsx, .js, .ps1, .cpp, .h |
| B015 | 2 | 2 |  |  |  |
| B016 | 2 | 2 | execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify | read, edit, write, run:powershell.exe, search | .cpp, .h, makefile, .c, .ps1 |
| B017 | 2 | 2 | inspect > create > execute | list, read, create, git:other, copy | .svelte, .ts |
| B018 | 2 | 1 | execute > search > tool > execute > tool > execute > inspect > execute > search > tool | read, search, run:python, run:glab, run:adb | .png, .apk, .md, .0, .sh |
| B019 | 1 | 1 | modify > plan > search > modify > execute > modify | edit, read, list, search | makefile, .c, .cfg, .asm, .h |
| B020 | 1 | 1 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .ps1, .exe |
| B021 | 1 | 1 | tool > search > plan > execute > create | write, edit, read, list, run:npx | .tsx, .js, .ts, .json, .css |
| B022 | 1 | 1 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | search, read, run:build.sh, build:make | .c, .md, .ps1, .sh, .exe |
| B023 | 1 | 1 | inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan | edit, write, read, build:npm, search | .tsx, .css, .md, .ts |
| B024 | 1 | 1 | create > plan > create > modify > create > plan > execute | write, edit | .hpp, .cpp |
| B025 | 1 | 1 | tool > inspect | read | .py |
| B026 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute; search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute; execute > create > execute > create > execute > inspect > execute; inspect > execute > create > execute > inspect > create > execute

常见转移：[['create', 'execute', 18], ['execute', 'create', 17], ['inspect', 'create', 8], ['execute', 'inspect', 8], ['inspect', 'execute', 6], ['execute', 'search', 5]]

### B002

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; modify > inspect > modify > create > inspect > plan > modify > inspect > modify; search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 28], ['modify', 'inspect', 22], ['search', 'inspect', 9], ['inspect', 'search', 8], ['modify', 'search', 4], ['modify', 'create', 3]]

### B003

inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect; execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute > modify > execute; modify > inspect > modify > execute > inspect > execute

常见转移：[['execute', 'inspect', 17], ['inspect', 'execute', 13], ['modify', 'execute', 9], ['inspect', 'modify', 6], ['modify', 'inspect', 3], ['plan', 'execute', 2]]

### B004

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify; modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; execute > create > modify > execute > modify > execute > tool > execute > modify; inspect > create > modify > execute > modify > create > modify > execute > modify

常见转移：[['modify', 'execute', 15], ['execute', 'modify', 10], ['create', 'modify', 8], ['modify', 'create', 5], ['execute', 'create', 4], ['inspect', 'modify', 4]]

### B005

modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify; create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect; create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect; modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify; modify > inspect > modify > inspect > modify > execute > modify > inspect > create > modify > execute > modify

常见转移：[['inspect', 'modify', 20], ['modify', 'inspect', 15], ['modify', 'execute', 13], ['create', 'inspect', 9], ['execute', 'create', 6], ['inspect', 'create', 5]]

### B006

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create; inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect; create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['create', 'plan', 18], ['plan', 'create', 18], ['create', 'inspect', 6], ['inspect', 'create', 6], ['plan', 'execute', 3], ['execute', 'create', 3]]

### B007

inspect > search > inspect > search > plan > create > plan > modify > plan > create; search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 9], ['search', 'inspect', 8], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B008

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create; execute > inspect > execute > inspect > execute > inspect > modify > execute > inspect > modify > tool > execute; execute > modify > create > modify > execute > inspect > execute > inspect > execute > modify > execute > inspect

常见转移：[['inspect', 'execute', 15], ['execute', 'inspect', 15], ['inspect', 'modify', 4], ['execute', 'modify', 3], ['execute', 'create', 3], ['modify', 'execute', 3]]

### B009

execute > inspect > create > inspect > modify > execute; tool > inspect > execute > modify > execute; create > execute > create > modify > execute; create > modify > execute > search > tool > execute > modify > create > execute > tool; execute > inspect > modify > execute

常见转移：[['modify', 'execute', 5], ['execute', 'inspect', 2], ['inspect', 'modify', 2], ['execute', 'modify', 2], ['create', 'execute', 2], ['create', 'modify', 2]]

### B010

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect; execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create; create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search; create > plan > execute > plan > execute > create > inspect > execute > search > plan > execute > create > plan > create > plan > create

常见转移：[['plan', 'execute', 12], ['create', 'plan', 8], ['inspect', 'execute', 7], ['execute', 'plan', 7], ['plan', 'create', 6], ['execute', 'create', 5]]

### B011

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify; search > execute > search > inspect > modify > search > inspect > create > modify > inspect; modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 10], ['search', 'inspect', 7], ['inspect', 'modify', 6], ['search', 'execute', 4], ['execute', 'search', 4], ['search', 'modify', 4]]

### B012

execute > inspect > search > inspect > modify > tool > execute; execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 8], ['inspect', 'search', 7], ['search', 'inspect', 7], ['execute', 'inspect', 5], ['modify', 'execute', 3], ['modify', 'search', 2]]

### B013

inspect > modify > inspect > execute > inspect > modify; modify > search > modify > inspect > execute > inspect > modify > inspect > modify > execute > inspect > execute; modify > search > inspect > modify > inspect > search > execute > inspect > modify

常见转移：[['inspect', 'modify', 6], ['modify', 'inspect', 4], ['execute', 'inspect', 4], ['inspect', 'execute', 3], ['modify', 'search', 2], ['search', 'modify', 1]]

### B014

search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute

常见转移：[['create', 'execute', 6], ['execute', 'create', 5], ['execute', 'plan', 2], ['plan', 'create', 2], ['search', 'plan', 1], ['plan', 'execute', 1]]

### B015

; tool

常见转移：[]

### B016

execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify; search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['search', 'inspect', 4], ['inspect', 'create', 4], ['create', 'plan', 4], ['plan', 'search', 3], ['modify', 'inspect', 2], ['create', 'inspect', 2]]

### B017

inspect > create > execute; search > tool > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1], ['search', 'tool', 1], ['tool', 'execute', 1]]

### B018

execute > search > tool > execute > tool > execute > inspect > execute > search > tool; tool > execute > inspect > execute > search > tool > execute > inspect > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 5], ['tool', 'execute', 4], ['execute', 'search', 3], ['search', 'tool', 3], ['execute', 'tool', 1]]

### B019

modify > plan > search > modify > execute > modify

常见转移：[['modify', 'plan', 1], ['plan', 'search', 1], ['search', 'modify', 1], ['modify', 'execute', 1], ['execute', 'modify', 1]]

### B020

create

常见转移：[]

### B021

tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B022

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect

常见转移：[['modify', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'tool', 1], ['tool', 'search', 1]]

### B023

inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan

常见转移：[['modify', 'plan', 5], ['plan', 'modify', 3], ['inspect', 'modify', 2], ['plan', 'execute', 2], ['execute', 'plan', 2], ['plan', 'create', 1]]

### B024

create > plan > create > modify > create > plan > execute

常见转移：[['create', 'plan', 2], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'create', 1], ['plan', 'execute', 1]]

### B025

tool > inspect

常见转移：[['tool', 'inspect', 1]]

### B026

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

