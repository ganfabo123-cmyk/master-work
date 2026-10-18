# -*- coding: utf-8 -*-
"""
签名层示例：Aho-Corasick 精确签名路由（纯标准库，无依赖）

三层结构演示：
  1) 存储：SKILL_TRIGGERS 表 = 将来写在每个 SKILL.md frontmatter `triggers:` 的内容
  2) 索引：程序启动时把所有签名构建为一个 Aho-Corasick 自动机（一次构建）
  3) 查询：对 user input 做一次线性扫描 O(|text|)，与语料规模 N 无关
"""
from collections import deque

# ---------------------------------------------------------------------------
# 1) 存储结构：将来对应 SKILL.md 的 frontmatter
#    ---
#    name: windows-lnk1105-error1224-file-locked
#    description: ...
#    triggers:
#      - "LNK1105"
#      - "error code 1224"
#      - "cannot close file"
#    ---
SKILL_TRIGGERS = {
    "windows-lnk1105-error1224-file-locked": [
        "LNK1105", "error code 1224", "cannot close file",
    ],
    "windows-lnk1107-corrupt-binary": [
        "LNK1107", "invalid or corrupt file",
    ],
    "powershell-command-not-found-windows": [
        "is not recognized as a name of a cmdlet",
        "无法将",  # 中文报错前缀
        "wsl: failed to translate",
    ],
    "file-write-conflict-external-modifier": [
        "file has been modified since read",
        "file has not been read yet",
    ],
    "http-404-endpoint-first": [
        "404", "not found",
    ],
    "repeated-command-no-expected-output": [
        # 行为模式型：没有稳定字面签名 → frontmatter 里标注走语义兜底
    ],
    "user-repeats-same-bug-report": [],
    "same-error-three-times-escalate": [],
    "session-resume-after-interruption": [],
    "project-build-entry-and-env-probe": [],
}

# ---------------------------------------------------------------------------
# 2) 索引结构：Aho-Corasick 自动机（trie + 失配指针）
class AhoCorasick:
    def __init__(self):
        self.goto = [{}]      # 状态 -> {字符: 状态}
        self.fail = [0]       # 失配指针
        self.out = [set()]    # 状态 -> {(skill, 签名原文)}

    def add(self, pattern: str, skill: str) -> None:
        state = 0
        for ch in pattern:
            nxt = self.goto[state].get(ch)
            if nxt is None:
                self.goto.append({})
                self.fail.append(0)
                self.out.append(set())
                nxt = len(self.goto) - 1
                self.goto[state][ch] = nxt
            state = nxt
        self.out[state].add((skill, pattern))

    def build(self) -> None:
        queue = deque()
        for s in self.goto[0].values():
            self.fail[s] = 0
            queue.append(s)
        while queue:
            r = queue.popleft()
            for ch, s in self.goto[r].items():
                queue.append(s)
                f = self.fail[r]
                while f and ch not in self.goto[f]:
                    f = self.fail[f]
                self.fail[s] = self.goto[f].get(ch, 0)
                if self.fail[s] == s:
                    self.fail[s] = 0
                self.out[s] |= self.out[self.fail[s]]

    def scan(self, text: str) -> list[tuple[str, str, int]]:
        """一次线性扫描，返回 [(skill, 签名, 结束位置)]，复杂度 O(len(text))。"""
        state, hits = 0, []
        for i, ch in enumerate(text):
            while state and ch not in self.goto[state]:
                state = self.fail[state]
            state = self.goto[state].get(ch, 0)
            for skill, pat in self.out[state]:
                hits.append((skill, pat, i - len(pat) + 1))
        return hits


# ---------------------------------------------------------------------------
# 3) 构建索引：所有签名小写化做大小写无关匹配
ac = AhoCorasick()
for skill, patterns in SKILL_TRIGGERS.items():
    for p in patterns:
        ac.add(p.casefold(), skill)
ac.build()

# ---------------------------------------------------------------------------
# 测试输入：真实 trace 原文 / 易混淆家族 / 改写型 / 无关
TEST_INPUTS = [
    ("a20a4070 的真实 tool_result 片段",
     "LINK : fatal error LNK1105: cannot close file 'D:\\DMLS\\build\\dmls.exe'; error code 1224"),
    ("易混淆家族：LNK1107 vs LNK1105",
     "报 LNK1107 invalid or corrupt file:怎么办"),
    ("PowerShell 假故障（09d9abe9 原文）",
     "The term 'tail' is not recognized as a name of a cmdlet, function, script file, or executable program."),
    ("改写型输入：不含任何原文签名",
     "链接器说文件关不上，好像是权限问题"),
    ("无关输入",
     "帮我写一个快速排序"),
]

for label, text in TEST_INPUTS:
    hits = ac.scan(text.casefold())
    print(f"\n输入[{label}]: {text[:60]}{'...' if len(text) > 60 else ''}")
    if not hits:
        print("  -> 无签名命中 => 走语义兜底（embedding 层）")
        continue
    by_skill = {}
    for skill, pat, pos in hits:
        by_skill.setdefault(skill, []).append((pat, pos))
    print(f"  -> 签名命中 {len(hits)} 处，路由到 {len(by_skill)} 个 skill（跳过 embedding RTT）:")
    for skill, pats in by_skill.items():
        shown = ", ".join(f"'{p}'@{i}" for p, i in pats)
        print(f"     {skill:42s} <= {shown}")
