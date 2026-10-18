# 全局切片行为聚类 v1

本实验直接对唯一 slice profile 聚类，不读取领域簇、领域 assignments 或领域名称。

- 输入 slice 数：97
- 行为簇数：16
- 相似度阈值：0.12
- 原始 session 数：30
- 被拆成多个行为簇的 session 数：19
- 跨 session 行为簇数：15

## 行为簇概览

| 行为簇 | slice 数 | session 数 | 代表动作序列 | 常见操作 | 文件类型 |
|---|---:|---:|---|---|---|
| B001 | 15 | 7 | inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify | read, edit, search, list, run:adb | .odin, .java, .md, .cpp, .png |
| B002 | 14 | 10 | search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect | edit, read, write, search, list | .css, .c, .tsx, .ts, .odin |
| B003 | 9 | 6 | inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute | write, edit, read, list, run:wsl.exe | .c, .h, .sh, makefile, .ts |
| B004 | 9 | 5 | modify > plan > search > modify > execute > modify | read, edit, search, run:python, list | .java, .md, .tsx, .json, .groovy |
| B005 | 6 | 5 | search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify | write, edit, read, run:python, list | .py, .cfml, .ts, .tsx, .cpp |
| B006 | 6 | 6 | execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan | read, write, edit, list, search | .ts, .js, .odin, .tsx, .css |
| B007 | 6 | 5 | execute > inspect > search > inspect > modify > tool > execute | read, edit, write, run:wsl, search | .c, .sh, .js, .md, .h |
| B008 | 6 | 5 | execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute | read, edit, write, search, list | .odin, .cpp, .c, .md, .exe |
| B009 | 5 | 4 | inspect > search > inspect > search > plan > create > plan > modify > plan > create | edit, read, search, list, write | .odin, .1, .c, .hpp, .h |
| B010 | 4 | 3 | plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify | write, edit, run:yggdrasil.exe, read, build:make | .jsx, .js, .py, .ps1, .cpp |
| B011 | 4 | 2 | inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search | edit, search, read, write, list | .ts, .json, .html, .js, .scss |
| B012 | 3 | 3 | create | write, read, edit, build:make, list | .cpp, .jsx, .js, .tsx, .ps1 |
| B013 | 3 | 3 |  | read | .py |
| B014 | 3 | 2 | modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect | read, edit, write, search, run:powershell.exe | .cpp, .c, .h, makefile, .ps1 |
| B015 | 3 | 2 | create > modify > execute > search > tool > execute > modify > create > execute > tool | read, search, list, remove, create | .yml, .log, .md, .txt, .sh |
| B016 | 1 | 1 | tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect | read, search, list | .py, .md |

## 解释

行为簇只根据规范化动作序列、动作转移、操作类型、文件类型和轨迹规模形成。它不使用领域 token，也不使用已有 D001～D008 标签。

`split_session_count` 用于观察一个完整 session 是否被切分成多个行为阶段；`cross_session_cluster_count` 用于观察相同行为是否跨 session 重复出现。两者同时较高时，切片对行为模式发现更有支持。

## 代表动作序列

### B001

inspect > search > tool > inspect > execute > inspect > execute > inspect > execute > inspect > tool > inspect > execute > modify; inspect > execute > inspect > execute > create > execute > inspect > execute > inspect > execute; inspect > modify > execute > modify > execute > inspect > execute > inspect > modify > create > modify > execute; inspect > execute > inspect > execute > inspect > execute > search > plan > execute > modify > inspect > modify > execute; create > modify > plan > create > plan > execute > inspect > execute > inspect > modify > inspect > modify > execute > inspect

常见转移：[['execute', 'inspect', 38], ['inspect', 'execute', 32], ['modify', 'execute', 16], ['inspect', 'modify', 12], ['execute', 'modify', 6], ['modify', 'inspect', 5]]

### B002

search > inspect > search > inspect > search > inspect > modify > inspect > search > create > modify > search > inspect > modify > inspect; inspect > search > modify > inspect > modify > inspect > modify > inspect > search > modify > search > create > modify; modify > inspect > modify > create > inspect > plan > modify > inspect > modify; modify > inspect > modify > execute > inspect > modify > execute > tool > inspect > create > search > plan > create > plan > create > modify > inspect > modify; search > inspect > modify > execute > inspect > search > create > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify > inspect > modify

常见转移：[['inspect', 'modify', 44], ['modify', 'inspect', 35], ['modify', 'execute', 14], ['create', 'inspect', 11], ['search', 'inspect', 8], ['inspect', 'search', 8]]

### B003

inspect > execute > search > tool > create > execute > search > execute > create > inspect > modify > execute; search > inspect > search > execute > create > execute > create; modify > execute > create > execute > create > execute > search > inspect > create > execute; execute > create > execute > create > execute > inspect > execute; create > search > inspect > create > execute > search > execute > inspect > execute > create > inspect > create

常见转移：[['execute', 'create', 14], ['create', 'execute', 13], ['inspect', 'create', 6], ['execute', 'search', 5], ['modify', 'execute', 5], ['execute', 'inspect', 5]]

### B004

modify > plan > search > modify > execute > modify; modify > execute > create > inspect > modify > inspect > execute > create > modify > execute > modify; execute > create > modify > execute > modify > execute > tool > execute > modify; execute > inspect > create > inspect > modify > execute; inspect > create > modify > execute > modify > create > modify > execute > modify

常见转移：[['modify', 'execute', 13], ['execute', 'modify', 8], ['create', 'modify', 8], ['execute', 'create', 4], ['inspect', 'modify', 4], ['modify', 'create', 3]]

### B005

search > create > inspect > create > plan > execute > create > plan > create > plan > create > plan > create > modify; inspect > search > plan > create > plan > modify > plan > create > plan > create > modify > plan > create > plan > create > inspect > create > plan > create; inspect > plan > inspect > create > plan > create > plan > create > plan > create > modify > create; inspect > tool > search > inspect > search > plan > create > plan > execute > create > plan > create > plan > execute > create > plan > create > plan > create > inspect; create > plan > create > plan > create > inspect > create > inspect > execute > inspect > create > search > execute > inspect > create > inspect > search > inspect

常见转移：[['create', 'plan', 20], ['plan', 'create', 19], ['create', 'inspect', 6], ['inspect', 'create', 6], ['plan', 'execute', 4], ['create', 'modify', 4]]

### B006

execute > modify > create > execute > inspect > modify > inspect > modify > search > inspect > plan; inspect > modify > inspect > modify > create > execute; inspect > execute > create > execute > inspect > create > execute; execute > create > execute > inspect > modify > inspect > create > execute; inspect > execute > create > execute > inspect > modify

常见转移：[['create', 'execute', 8], ['inspect', 'modify', 8], ['execute', 'inspect', 6], ['modify', 'inspect', 5], ['inspect', 'execute', 5], ['execute', 'create', 5]]

### B007

execute > inspect > search > inspect > modify > tool > execute; execute > inspect > modify > execute > inspect > search > inspect > modify > execute > inspect > search > inspect > create; inspect > modify > inspect > execute > inspect > modify; execute > inspect > search > inspect > modify > search > inspect > modify > inspect > modify > execute > create; inspect > search > inspect > search > inspect > modify > inspect > modify > search > execute > create > inspect > search > modify

常见转移：[['inspect', 'modify', 12], ['inspect', 'search', 8], ['search', 'inspect', 8], ['execute', 'inspect', 7], ['modify', 'inspect', 4], ['modify', 'execute', 3]]

### B008

execute > inspect > execute > inspect > execute > plan > execute > plan > create > plan > execute; inspect > execute > inspect > execute > inspect > execute > search > inspect > search > inspect > search > plan > execute > plan > execute > create > plan > inspect; inspect > modify > plan > execute > plan > modify > plan > modify > plan > create > plan > modify > plan > inspect > modify > plan > execute > plan; execute > modify > execute > tool > search > plan > execute > plan > execute > create > inspect > create > inspect > plan > create > plan > create; create > modify > create > plan > execute > plan > create > plan > execute > plan > execute > create > inspect > execute > search

常见转移：[['plan', 'execute', 14], ['execute', 'plan', 9], ['create', 'plan', 9], ['inspect', 'execute', 7], ['plan', 'create', 7], ['execute', 'create', 5]]

### B009

inspect > search > inspect > search > plan > create > plan > modify > plan > create; search > inspect > search > inspect > plan > inspect > create; search > inspect > search > inspect > search; search > inspect > search > inspect > search > execute > create; inspect > tool > inspect > search > inspect > search > plan > modify > plan

常见转移：[['inspect', 'search', 9], ['search', 'inspect', 8], ['search', 'plan', 2], ['plan', 'create', 2], ['plan', 'modify', 2], ['modify', 'plan', 2]]

### B010

plan > modify > create > execute > plan > create > plan > create > plan > modify > execute > modify > execute > modify; search > plan > execute > plan > create > execute > create > execute > create; modify > create > inspect > execute > plan > create > execute > create > execute > modify > execute > create > execute > create > execute; modify > execute > modify > execute > plan > execute > search > inspect > execute > create > execute

常见转移：[['create', 'execute', 8], ['execute', 'create', 6], ['modify', 'execute', 5], ['execute', 'plan', 4], ['plan', 'create', 4], ['execute', 'modify', 4]]

### B011

inspect > modify > create > inspect > modify > search > execute > search > inspect > search > inspect > create > modify > search > inspect > search; modify > search > modify > search > modify > search > modify > search > execute > search > execute > search > inspect > modify; search > execute > search > inspect > modify > search > inspect > create > modify > inspect; modify > search > inspect > modify > search > modify > inspect > execute > create > inspect > modify > search > tool > inspect > create > modify > tool > inspect > search > create

常见转移：[['modify', 'search', 10], ['search', 'inspect', 7], ['inspect', 'modify', 6], ['search', 'execute', 4], ['execute', 'search', 4], ['search', 'modify', 4]]

### B012

create; tool > search > plan > execute > create; inspect > create > execute

常见转移：[['tool', 'search', 1], ['search', 'plan', 1], ['plan', 'execute', 1], ['execute', 'create', 1], ['inspect', 'create', 1], ['create', 'execute', 1]]

### B013

; tool > inspect; tool

常见转移：[['tool', 'inspect', 1]]

### B014

modify > execute > plan > create > modify > tool > search > execute > tool > plan > search > inspect; execute > tool > plan > search > inspect > search > create > modify > inspect > create > plan > search > inspect > create > inspect > create > inspect > modify; search > inspect > plan > create > plan > search > inspect > create > plan > create > plan > modify > inspect > modify > plan

常见转移：[['search', 'inspect', 5], ['plan', 'search', 4], ['inspect', 'create', 4], ['create', 'plan', 4], ['plan', 'create', 3], ['create', 'modify', 2]]

### B015

create > modify > execute > search > tool > execute > modify > create > execute > tool; execute > search > tool > execute > tool > execute > inspect > execute > search > tool; search > tool > execute

常见转移：[['search', 'tool', 4], ['tool', 'execute', 4], ['execute', 'search', 3], ['execute', 'tool', 2], ['create', 'modify', 1], ['modify', 'execute', 1]]

### B016

tool > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect > search > inspect

常见转移：[['search', 'inspect', 11], ['inspect', 'search', 10], ['tool', 'search', 1]]

