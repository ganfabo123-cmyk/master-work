# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：13
- 相似度阈值：0.1
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：20
- 跨 session 行为簇数：12

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 19 | 13 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | edit, read, write, search, list | .css, .c, .odin, .tsx, .ts |
| B002 | 15 | 7 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, search, edit, list, run:adb | .odin, .md, .cpp, .ts, .png |
| B003 | 13 | 7 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | read, edit, search, run:python, list | .java, .yml, .py, .md, .log |
| B004 | 12 | 8 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | write, edit, read, list, search | .c, .h, .sh, .ts, makefile |
| B005 | 9 | 6 | execute > inspect > search > inspect > modify > tool > execute | read, edit, search, write, list | .odin, .c, .sh, .md, .h |
| B006 | 7 | 6 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, read, edit, run:python, list | .py, .cfml, .ts, .cpp, .tsx |
| B007 | 6 | 5 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .cpp, .c, .md, .exe |
| B008 | 4 | 2 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | edit, search, read, write, list | .ts, .json, .html, .js, .scss |
| B009 | 4 | 3 | search > plan > execute > plan > create > execute > create > execute > create | write, run:yggdrasil.exe, edit, read, build:make | .jsx, .js, .cpp, .ps1, .h |
| B010 | 3 | 3 | inspect > create > execute | list, read, create, git:other, copy | .svelte, .ts, .py |
| B011 | 2 | 2 | create | write, read, edit, build:make, run:yggdrasil.exe | .cpp, .jsx, .js, .tsx, .ps1 |
| B012 | 2 | 2 |  |  |  |
| B013 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; modify > inspect > modify > create > inspect > plan > modify > inspect > modify; modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify

常见转移：[['inspect', 'modify', 54], ['modify', 'inspect', 41], ['modify', 'execute', 15], ['create', 'inspect', 11], ['execute', 'inspect', 10], ['search', 'inspect', 10]]

### B002

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect; execute > inspect > execute > inspect > modify > execute

常见转移：[['execute', 'inspect', 37], ['inspect', 'execute', 33], ['modify', 'execute', 12], ['inspect', 'modify', 10], ['execute', 'modify', 5], ['modify', 'inspect', 5]]

### B003

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify; modify > plan > search > modify > execute > modify; modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; execute > create > modify > execute > modify > execute > tool > execute > modify

常见转移：[['modify', 'execute', 21], ['execute', 'modify', 13], ['create', 'modify', 10], ['modify', 'create', 6], ['inspect', 'modify', 6], ['execute', 'create', 5]]

### B004

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute; search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute; execute > create > execute > create > execute > inspect > execute; inspect > execute > create > execute > inspect > create > execute

常见转移：[['create', 'execute', 18], ['execute', 'create', 17], ['inspect', 'create', 8], ['execute', 'inspect', 8], ['inspect', 'execute', 6], ['execute', 'search', 5]]

### B005

execute > inspect > search > inspect > modify > tool > execute; inspect > search > inspect > search > plan > create > plan > modify > plan > create; execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search

常见转移：[['inspect', 'search', 16], ['search', 'inspect', 15], ['inspect', 'modify', 8], ['execute', 'inspect', 5], ['modify', 'execute', 3], ['execute', 'create', 3]]

### B006

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create; execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify; inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect

常见转移：[['create', 'plan', 22], ['plan', 'create', 20], ['inspect', 'create', 10], ['create', 'inspect', 8], ['search', 'inspect', 6], ['create', 'modify', 4]]

### B007

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect; inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan; execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create; create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search

常见转移：[['plan', 'execute', 14], ['execute', 'plan', 9], ['create', 'plan', 9], ['inspect', 'execute', 7], ['plan', 'create', 7], ['execute', 'create', 5]]

### B008

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify; search > execute > search > inspect > modify > search > inspect > create > modify > inspect; modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 10], ['search', 'inspect', 7], ['inspect', 'modify', 6], ['search', 'execute', 4], ['execute', 'search', 4], ['search', 'modify', 4]]

### B009

search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute; modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect; create > plan > create > modify > create > plan > execute

常见转移：[['create', 'execute', 6], ['execute', 'create', 5], ['plan', 'create', 4], ['execute', 'plan', 3], ['plan', 'execute', 2], ['modify', 'create', 2]]

### B010

inspect > create > execute; tool > inspect; search > tool > execute

常见转移：[['inspect', 'create', 1], ['create', 'execute', 1], ['tool', 'inspect', 1], ['search', 'tool', 1], ['tool', 'execute', 1]]

### B011

create; tool > search > plan > execute > create

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1]]

### B012

; tool

常见转移：[]

### B013

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

