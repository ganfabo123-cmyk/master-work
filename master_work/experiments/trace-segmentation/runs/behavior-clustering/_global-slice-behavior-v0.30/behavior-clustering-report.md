# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：56
- 相似度阈值：0.3
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：17

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 5 | 3 | search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect | edit, read, write, search, list | .css, .ts, .html, .scss, .md |
| B002 | 5 | 3 | execute > inspect > execute > inspect > modify > execute | read, edit, search, list, run:adb | .odin, .md, .ts, .png, .log |
| B003 | 4 | 4 | create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect | read, edit, write, run:wsl, run:epilog.exe | .tsx, .c, .sh, .py, .h |
| B004 | 3 | 3 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, edit, run:python, read, list | .py, .cfml, .cpp, .c, .h |
| B005 | 3 | 3 | execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create | edit, read, write, run:wsl, search | .c, .sh, .md, .h, makefile |
| B006 | 3 | 2 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, edit, search, run:adb, run:node | .svelte, .json, .log, .png, .mjs |
| B007 | 3 | 1 | modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify | read, search, edit, run:python, test:gradle | .java, .groovy, .md, .models |
| B008 | 3 | 2 | search > inspect > search > inspect > plan > inspect > create | read, search, list | .1, .hpp, .c, .cpp, .h |
| B009 | 3 | 3 | execute > create > execute > create > execute > inspect > execute | write, read, list, edit, search | .js, .tsx, .css, .py, .md |
| B010 | 2 | 2 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, read, write, list, run:python | .odin, .py, .md, license, .cfml |
| B011 | 2 | 1 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | write, list, edit, read, search | .ts, .mjs, .json, .js, .gitignore |
| B012 | 2 | 2 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, write, list | .odin, .c, .h, .md, .asm |
| B013 | 2 | 1 | search > plan > execute > plan > create > execute > create > execute > create | write, run:yggdrasil.exe, edit, build:make, run:powershell | .jsx, .js, .ps1, .cpp, .h |
| B014 | 2 | 2 | inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute | read, search, write, edit, list | .java, .ts, .gradle, .properties, .groovy |
| B015 | 2 | 2 | execute > inspect > create > inspect > modify > execute | read, run:python, search, list, run:glab | .md, .jsonl, .yml, .py, .json |
| B016 | 2 | 2 | inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute | read, compile, edit, search, list | .cpp, .md, .exe, .hpp, .h |
| B017 | 2 | 2 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .c, .md, .h, .exe |
| B018 | 2 | 2 | inspect > modify > inspect > execute > inspect > modify | read, fetch, edit | .odin |
| B019 | 2 | 1 | search > inspect > search > execute > create > execute > create | write, edit, read, run:wsl.exe, search | .sh, .c, makefile, .h, .log |
| B020 | 2 | 2 |  |  |  |
| B021 | 2 | 1 | modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify | edit, read, build:npm, write | .tsx, .css, .md |
| B022 | 2 | 1 | inspect > create > modify > execute > modify > create > modify > execute > modify | edit, write, build:npm, read, list | .tsx, .md, .css, .html |
| B023 | 2 | 2 | create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create | list, run:bun, write, read, edit | .ts, .py, .txt |
| B024 | 2 | 1 | execute > modify > execute > inspect > create > execute > create > execute | write, read, dev:bun, build:bun, search | .ts, .svelte, .env |
| B025 | 2 | 1 | inspect > create > execute > create > search > tool > execute > create | edit, read, write, run:epilog.exe, compile | .c, .h, .md, makefile, .exe |
| B026 | 2 | 1 | create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search | edit, write, read, compile, create | .cpp, .exe, .hpp, makefile, .md |
| B027 | 2 | 1 | execute > search > tool > execute > tool > execute > inspect > execute > search > tool | read, search, run:python, run:glab, run:adb | .png, .apk, .md, .0, .sh |
| B028 | 1 | 1 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | edit, run:python, write, search, read | .py, .cfml, .gitignore |
| B029 | 1 | 1 | modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify | search, edit, build:npm, list, read | .scss, .ts, .css |
| B030 | 1 | 1 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | list, read, write, edit, search | .html, .md |
| B031 | 1 | 1 | execute > inspect > search > inspect > modify > tool > execute | read, run:npx, list, edit | .json, .html, .js |
| B032 | 1 | 1 | modify > plan > search > modify > execute > modify | edit, read, list, search | makefile, .c, .cfg, .asm, .h |
| B033 | 1 | 1 | modify > inspect > modify > create > inspect > plan > modify > inspect > modify | edit, read, build:make, list, write | .c, .h, makefile, .o |
| B034 | 1 | 1 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .ps1, .exe |
| B035 | 1 | 1 | modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify | edit, read, write | .h, .cpp, makefile |
| B036 | 1 | 1 | tool > search > plan > execute > create | write, edit, read, list, run:npx | .tsx, .js, .ts, .json, .css |
| B037 | 1 | 1 | search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify | edit, read, search, build:odin, write | .odin, .exe |
| B038 | 1 | 1 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | search, read, run:build.sh, build:make | .c, .md, .ps1, .sh, .exe |
| B039 | 1 | 1 | execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify | edit, read, write, search, build:make | .c, .h, makefile, .md |
| B040 | 1 | 1 | inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect | write, read, list, create | .tsx, .md, .css, .json |
| B041 | 1 | 1 | create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect | read, edit, write, list, fetch | .ts, .tsx, .json, .output, .md |
| B042 | 1 | 1 | inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan | edit, write, read, build:npm, search | .tsx, .css, .md, .ts |
| B043 | 1 | 1 | tool > inspect > execute > modify > execute | read, run:python, search, list, git:diff | .json, .js, .svelte, .tool, .repos |
| B044 | 1 | 1 | search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan | read, edit, write, run:powershell.exe, list | .cpp, .ps1, .h, makefile, .exe |
| B045 | 1 | 1 | modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute | list, read, write, git:other, git:add | .md, .gitignore |
| B046 | 1 | 1 | modify > inspect > modify > execute > inspect > execute | run:powershell.exe, read, edit, build:odin, run:cmd | .odin, .bat, .exe, .length, .getstream |
| B047 | 1 | 1 | execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create | write, edit, read, build:bun, search | .svelte, .ts, .scss, .html, .js |
| B048 | 1 | 1 | inspect > create > execute | list, create, read | .svelte, .ts |
| B049 | 1 | 1 | create > plan > create > modify > create > plan > execute | write, edit | .hpp, .cpp |
| B050 | 1 | 1 | tool > inspect | read | .py |
| B051 | 1 | 1 | modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create | edit, read, search, write, list | .html, .json, .js, .txt, .css |
| B052 | 1 | 1 | create > execute > create > modify > execute | read, git:checkout, git:status, list, git:add | .bat, gradlew, .jar, .properties |
| B053 | 1 | 1 | create > modify > execute > search > tool > execute > modify > create > execute > tool | read, search, list, remove, create | .yml, .log, .md, .txt, .sh |
| B054 | 1 | 1 | search > tool > execute | read, git:other, list, create, copy |  |
| B055 | 1 | 1 | modify > search > inspect > modify > inspect > search > execute > inspect > modify | read, search, edit, run:wsl | .js, .c |
| B056 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; inspect > modify > inspect > modify > inspect > modify > search > inspect > modify > tool > modify; create > execute > inspect > modify > inspect > modify > inspect > search > inspect > modify; modify > inspect > modify > inspect > search > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 15], ['modify', 'inspect', 13], ['search', 'inspect', 7], ['inspect', 'search', 7], ['modify', 'search', 3], ['search', 'create', 2]]

### B002

execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute > modify > execute; execute > inspect > execute > inspect > execute > inspect > modify > execute; modify > execute > inspect > execute > inspect > execute; modify > execute > inspect > execute > inspect

常见转移：[['execute', 'inspect', 11], ['inspect', 'execute', 8], ['modify', 'execute', 6], ['inspect', 'modify', 2], ['execute', 'modify', 1]]

### B003

create > inspect > modify > execute > create > inspect > modify > execute > create > inspect > modify > inspect; create > modify > execute > create > inspect > modify > execute > inspect > create > inspect > modify > inspect > modify > inspect; execute > inspect > execute > create > inspect > create > inspect > modify > inspect > modify > inspect > modify > create; modify > inspect > modify > inspect > modify > execute > create > inspect > create > inspect > modify > inspect > modify > execute > create > execute > modify > execute

常见转移：[['inspect', 'modify', 13], ['create', 'inspect', 9], ['modify', 'inspect', 8], ['modify', 'execute', 7], ['execute', 'create', 6], ['inspect', 'create', 3]]

### B004

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create

常见转移：[['plan', 'create', 12], ['create', 'plan', 11], ['inspect', 'create', 3], ['create', 'modify', 3], ['create', 'inspect', 2], ['modify', 'plan', 2]]

### B005

execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 7], ['inspect', 'search', 6], ['search', 'inspect', 6], ['execute', 'inspect', 4], ['modify', 'execute', 3], ['modify', 'search', 2]]

### B006

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; execute > inspect > execute > inspect > execute > inspect > modify > execute > inspect > modify > tool > execute; execute > modify > create > modify > execute > inspect > execute > inspect > execute > modify > execute > inspect

常见转移：[['execute', 'inspect', 10], ['inspect', 'execute', 8], ['execute', 'modify', 3], ['modify', 'execute', 3], ['tool', 'inspect', 2], ['inspect', 'modify', 2]]

### B007

modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; execute > create > modify > execute > modify > execute > tool > execute > modify

常见转移：[['modify', 'execute', 7], ['execute', 'modify', 4], ['execute', 'create', 3], ['inspect', 'modify', 3], ['create', 'modify', 3], ['inspect', 'execute', 2]]

### B008

search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create

常见转移：[['search', 'inspect', 6], ['inspect', 'search', 5], ['inspect', 'plan', 1], ['plan', 'inspect', 1], ['inspect', 'create', 1], ['search', 'execute', 1]]

### B009

execute > create > execute > create > execute > inspect > execute; inspect > execute > create > execute > inspect > create > execute; inspect > execute > create > execute > inspect > modify

常见转移：[['create', 'execute', 5], ['execute', 'create', 4], ['execute', 'inspect', 3], ['inspect', 'execute', 3], ['inspect', 'create', 1], ['inspect', 'modify', 1]]

### B010

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; inspect > modify > inspect > modify > create > execute

常见转移：[['inspect', 'modify', 4], ['modify', 'create', 2], ['create', 'execute', 2], ['modify', 'inspect', 2], ['execute', 'modify', 1], ['execute', 'inspect', 1]]

### B011

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; search > execute > search > inspect > modify > search > inspect > create > modify > inspect

常见转移：[['search', 'inspect', 5], ['inspect', 'modify', 3], ['modify', 'search', 3], ['search', 'execute', 2], ['execute', 'search', 2], ['inspect', 'search', 2]]

### B012

inspect > search > inspect > search > plan > create > plan > modify > plan > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 4], ['search', 'inspect', 2], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B013

search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute

常见转移：[['create', 'execute', 6], ['execute', 'create', 5], ['execute', 'plan', 2], ['plan', 'create', 2], ['search', 'plan', 1], ['plan', 'execute', 1]]

### B014

inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > execute > inspect > execute > inspect > execute > create > modify > inspect > modify > inspect > modify > create > execute > create

常见转移：[['inspect', 'execute', 7], ['execute', 'inspect', 5], ['execute', 'create', 3], ['create', 'execute', 2], ['modify', 'inspect', 2], ['inspect', 'modify', 2]]

### B015

execute > inspect > create > inspect > modify > execute; execute > inspect > modify > execute

常见转移：[['execute', 'inspect', 2], ['inspect', 'modify', 2], ['modify', 'execute', 2], ['inspect', 'create', 1], ['create', 'inspect', 1]]

### B016

inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 4], ['inspect', 'modify', 3], ['plan', 'execute', 2], ['modify', 'inspect', 2], ['modify', 'execute', 2]]

### B017

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect

常见转移：[['inspect', 'execute', 5], ['execute', 'inspect', 4], ['plan', 'execute', 4], ['execute', 'plan', 3], ['create', 'plan', 2], ['search', 'inspect', 2]]

### B018

inspect > modify > inspect > execute > inspect > modify; modify > search > modify > inspect > execute > inspect > modify > inspect > modify > execute > inspect > execute

常见转移：[['inspect', 'modify', 4], ['modify', 'inspect', 3], ['inspect', 'execute', 3], ['execute', 'inspect', 3], ['modify', 'search', 1], ['search', 'modify', 1]]

### B019

search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute

常见转移：[['execute', 'create', 4], ['create', 'execute', 4], ['search', 'inspect', 2], ['inspect', 'search', 1], ['search', 'execute', 1], ['modify', 'execute', 1]]

### B020

; tool

常见转移：[]

### B021

modify > search > modify > execute > plan > modify > inspect > modify > inspect > modify > execute > modify; modify > inspect > modify > inspect > modify > execute > modify > inspect > create > modify > execute > modify

常见转移：[['modify', 'inspect', 5], ['modify', 'execute', 4], ['inspect', 'modify', 4], ['execute', 'modify', 3], ['modify', 'search', 1], ['search', 'modify', 1]]

### B022

inspect > create > modify > execute > modify > create > modify > execute > modify; create > modify > execute > modify > create > modify > search > inspect > modify > create > modify > execute > tool

常见转移：[['create', 'modify', 5], ['modify', 'execute', 4], ['execute', 'modify', 3], ['modify', 'create', 3], ['inspect', 'create', 1], ['modify', 'search', 1]]

### B023

create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create; execute > search > execute > inspect > create > execute > inspect > execute > create > modify > execute > modify > execute

常见转移：[['inspect', 'create', 3], ['execute', 'inspect', 3], ['create', 'execute', 2], ['execute', 'search', 2], ['search', 'execute', 2], ['inspect', 'execute', 2]]

### B024

execute > modify > execute > inspect > create > execute > create > execute; execute > create > execute > inspect > modify > inspect > create > execute

常见转移：[['create', 'execute', 4], ['execute', 'inspect', 2], ['inspect', 'create', 2], ['execute', 'create', 2], ['execute', 'modify', 1], ['modify', 'execute', 1]]

### B025

inspect > create > execute > create > search > tool > execute > create; execute > create > search > tool > execute > create > execute > modify > inspect > modify > create > inspect > modify

常见转移：[['execute', 'create', 4], ['create', 'execute', 2], ['create', 'search', 2], ['search', 'tool', 2], ['tool', 'execute', 2], ['inspect', 'modify', 2]]

### B026

create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search; create > plan > execute > plan > execute > create > inspect > execute > search > plan > execute > create > plan > create > plan > create

常见转移：[['plan', 'execute', 6], ['create', 'plan', 5], ['execute', 'plan', 3], ['plan', 'create', 3], ['execute', 'create', 3], ['create', 'inspect', 2]]

### B027

execute > search > tool > execute > tool > execute > inspect > execute > search > tool; tool > execute > inspect > execute > search > tool > execute > inspect > execute > inspect > execute > inspect > execute

常见转移：[['execute', 'inspect', 5], ['inspect', 'execute', 5], ['tool', 'execute', 4], ['execute', 'search', 3], ['search', 'tool', 3], ['execute', 'tool', 1]]

### B028

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify

常见转移：[['plan', 'modify', 2], ['plan', 'create', 2], ['create', 'plan', 2], ['modify', 'execute', 2], ['execute', 'modify', 2], ['modify', 'create', 1]]

### B029

modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify

常见转移：[['modify', 'search', 4], ['search', 'modify', 3], ['search', 'execute', 2], ['execute', 'search', 2], ['search', 'inspect', 1], ['inspect', 'modify', 1]]

### B030

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute

常见转移：[['execute', 'search', 2], ['inspect', 'execute', 1], ['search', 'tool', 1], ['tool', 'create', 1], ['create', 'execute', 1], ['search', 'execute', 1]]

### B031

execute > inspect > search > inspect > modify > tool > execute

常见转移：[['execute', 'inspect', 1], ['inspect', 'search', 1], ['search', 'inspect', 1], ['inspect', 'modify', 1], ['modify', 'tool', 1], ['tool', 'execute', 1]]

### B032

modify > plan > search > modify > execute > modify

常见转移：[['modify', 'plan', 1], ['plan', 'search', 1], ['search', 'modify', 1], ['modify', 'execute', 1], ['execute', 'modify', 1]]

### B033

modify > inspect > modify > create > inspect > plan > modify > inspect > modify

常见转移：[['modify', 'inspect', 2], ['inspect', 'modify', 2], ['modify', 'create', 1], ['create', 'inspect', 1], ['inspect', 'plan', 1], ['plan', 'modify', 1]]

### B034

create

常见转移：[]

### B035

modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify

常见转移：[['inspect', 'modify', 3], ['modify', 'inspect', 2], ['modify', 'execute', 2], ['plan', 'create', 2], ['execute', 'inspect', 1], ['execute', 'tool', 1]]

### B036

tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B037

search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 7], ['modify', 'inspect', 5], ['search', 'inspect', 1], ['modify', 'execute', 1], ['execute', 'inspect', 1], ['inspect', 'search', 1]]

### B038

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect

常见转移：[['modify', 'execute', 1], ['execute', 'plan', 1], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'tool', 1], ['tool', 'search', 1]]

### B039

execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify

常见转移：[['inspect', 'create', 3], ['plan', 'search', 2], ['search', 'inspect', 2], ['create', 'inspect', 2], ['execute', 'tool', 1], ['tool', 'plan', 1]]

### B040

inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect

常见转移：[['create', 'plan', 5], ['plan', 'create', 4], ['plan', 'execute', 2], ['execute', 'create', 2], ['inspect', 'tool', 1], ['tool', 'search', 1]]

### B041

create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['create', 'inspect', 3], ['inspect', 'create', 3], ['create', 'plan', 2], ['plan', 'create', 2], ['execute', 'inspect', 2], ['inspect', 'execute', 1]]

### B042

inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan

常见转移：[['modify', 'plan', 5], ['plan', 'modify', 3], ['inspect', 'modify', 2], ['plan', 'execute', 2], ['execute', 'plan', 2], ['plan', 'create', 1]]

### B043

tool > inspect > execute > modify > execute

常见转移：[['tool', 'inspect', 1], ['inspect', 'execute', 1], ['execute', 'modify', 1], ['modify', 'execute', 1]]

### B044

search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['create', 'plan', 3], ['search', 'inspect', 2], ['plan', 'create', 2], ['inspect', 'plan', 1], ['plan', 'search', 1], ['inspect', 'create', 1]]

### B045

modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute

常见转移：[['modify', 'execute', 2], ['execute', 'modify', 1], ['execute', 'plan', 1], ['plan', 'execute', 1], ['execute', 'search', 1], ['search', 'inspect', 1]]

### B046

modify > inspect > modify > execute > inspect > execute

常见转移：[['modify', 'inspect', 1], ['inspect', 'modify', 1], ['modify', 'execute', 1], ['execute', 'inspect', 1], ['inspect', 'execute', 1]]

### B047

execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create

常见转移：[['plan', 'execute', 2], ['create', 'inspect', 2], ['plan', 'create', 2], ['execute', 'modify', 1], ['modify', 'execute', 1], ['execute', 'tool', 1]]

### B048

inspect > create > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1]]

### B049

create > plan > create > modify > create > plan > execute

常见转移：[['create', 'plan', 2], ['plan', 'create', 1], ['create', 'modify', 1], ['modify', 'create', 1], ['plan', 'execute', 1]]

### B050

tool > inspect

常见转移：[['tool', 'inspect', 1]]

### B051

modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 3], ['inspect', 'modify', 2], ['tool', 'inspect', 2], ['search', 'inspect', 1], ['search', 'modify', 1], ['modify', 'inspect', 1]]

### B052

create > execute > create > modify > execute

常见转移：[['create', 'execute', 1], ['execute', 'create', 1], ['create', 'modify', 1], ['modify', 'execute', 1]]

### B053

create > modify > execute > search > tool > execute > modify > create > execute > tool

常见转移：[['create', 'modify', 1], ['modify', 'execute', 1], ['execute', 'search', 1], ['search', 'tool', 1], ['tool', 'execute', 1], ['execute', 'modify', 1]]

### B054

search > tool > execute

常见转移：[['search', 'tool', 1], ['tool', 'execute', 1]]

### B055

modify > search > inspect > modify > inspect > search > execute > inspect > modify

常见转移：[['inspect', 'modify', 2], ['modify', 'search', 1], ['search', 'inspect', 1], ['modify', 'inspect', 1], ['inspect', 'search', 1], ['search', 'execute', 1]]

### B056

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

