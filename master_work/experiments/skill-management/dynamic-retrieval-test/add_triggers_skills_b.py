# -*- coding: utf-8 -*-
"""给 skills_b 的 35 个 SKILL.md 补写结构化触发签名（frontmatter `triggers:` 字段）。

设计依据：DESIGN_retrieval_architecture.md §4.2（签名层存储格式与选择标准）。

- 签名只收机器生成的模板文本：错误码（LNKxxxx/TSxxxx）、NTSTATUS（0xC0000135、
  -1073741571 等十六进制/十进制双形态）、errno（EPERM/ENOTEMPTY/ECONNRESET）、
  编译器与词法器诊断原句、脚手架交互提示语；
- 近重复族（LNK1105 三件套、栈溢出五件套、测试宏四件套、lexer dot 四件套、
  LNK2019 头文件全局三件套……）共享族签名是有意为之：同问题多变体共同命中，
  由下游 description 相似度排序决定注入谁；
- 每个 trigger 必须能在对应 SKILL.md 全文中找到出处（校验强制），防止凭空造签名；
- 幂等：frontmatter 已含 triggers 的文件跳过不覆盖。

用法：
    python add_triggers_skills_b.py
"""

from __future__ import annotations

from pathlib import Path

SKILLS_ROOT = Path(__file__).resolve().parent / "skills_b"

# name -> triggers（策划记录：每条都能在正文/证据引文中找到原文）
TRIGGERS: dict[str, list[str]] = {
    "avoid-odin-large-struct-stack-frames": [
        "may cause a stack overflow due to its type",
    ],
    "capture-arena-refs-before-allocating": [
        "EXPECT_EQ(ctx.deref",
        "ctx.deref(x) == ctx.atom(",
    ],
    "capture-counter-once-for-test-macros": [
        "redefinition of '_reg___LINE__'",
        "redefinition of '_reg___COUNTER__'",
        "use of undeclared identifier '_test_body_",
    ],
    "clear-locked-react-router-typegen-dirs": [
        "EPERM: operation not permitted, scandir",
        "ENOTEMPTY",
        ".react-router/types",
        "typesDirectory(ctx)",
    ],
    "diagnose-windows-0xc0000135-missing-dll": [
        "0xC0000135",
        "-1073741515",
    ],
    "fix-concatenated-clause-strings-missing-separator": [
        "expected '.', got operator '.'",
        "parse error after",
    ],
    "fix-interleaved-key-index-two-pass-build": [
        "idx_clause_slots",
        "idx_start",
        "idx_count",
    ],
    "fix-lexer-dot-after-concatenated-literals": [
        "expected '.', got operator '.'",
        "TOK_DOT",
    ],
    "fix-lexer-dot-followed-by-nonspace": [
        "expected '.', got operator '.'",
    ],
    "fix-lnk1107-odin-dll-import-lib": [
        "LNK1107",
        "invalid or corrupt file",
        "llvm-dlltool",
    ],
    "fix-lnk1120-unresolved-global-in-test-links": [
        "LNK2019",
        "LNK1120",
        "unresolved external symbol",
        "unresolved externals",
    ],
    "fix-lnk2019-header-global-with-inline-variable": [
        "LNK2019",
        "unresolved external symbol",
    ],
    "fix-lnk2019-header-inline-global": [
        "LNK2019",
        "LNK1120",
        "unresolved external symbol",
    ],
    "fix-odin-c-abi-callback-context": [
        "'context' has not been defined within this scope",
        "runtime.default_context()",
    ],
    "fix-react19-useref-ts2554-no-default": [
        "TS2554",
        "Expected 1 arguments, but got 0",
        "useRef",
    ],
    "fix-stack-overflow-large-test-fixtures": [
        "-1073741571",
        "STATUS_STACK_OVERFLOW",
    ],
    "fix-test-macro-token-paste-counter": [
        "redefinition of '_reg___LINE__'",
        "redefinition of '_reg___COUNTER__'",
        "use of undeclared identifier '_test_body_",
    ],
    "fix-test-macro-token-pasting-ids": [
        "redefinition of '_reg___LINE__'",
        "use of undeclared identifier '_test_body_",
    ],
    "fix-test-macro-unique-name-pasting": [
        "redefinition of '_reg___LINE__'",
        "redefinition of '_reg___COUNTER__'",
        "use of undeclared identifier '_test_body_",
    ],
    "fix-test-stack-overflow-large-fixtures": [
        "-1073741571",
        "0xC00000FD",
        "STATUS_STACK_OVERFLOW",
    ],
    "fix-ts1484-type-only-imports": [
        "TS1484",
        "must be imported using a type-only import",
        "verbatimModuleSyntax",
    ],
    "fix-ts2554-useref-tsc-batch": [
        "TS2554",
        "Expected 1 arguments, but got 0",
        "TS6133",
        "TS1484",
    ],
    "fix-ts6133-unused-and-related-tsc-errors": [
        "TS6133",
        "noUnusedLocals",
        "TS1484",
        "TS2554",
    ],
    "fix-windows-0xc00000fd-stack-overflow": [
        "-1073741571",
        "0xC00000FD",
    ],
    "fix-windows-lnk1105-locked-output-exe": [
        "LNK1105",
        "error code 1224",
        "exit code 1105",
        "cannot close file",
    ],
    "fix-windows-stack-overflow-in-large-local-fixtures": [
        "-1073741571",
        "0xC00000FD",
        "STATUS_STACK_OVERFLOW",
    ],
    "handle-locked-or-stale-test-binaries": [
        "LNK1105",
        "cannot close file",
        "LastWriteTime",
    ],
    "keep-large-test-fixtures-off-windows-stack": [
        "-1073741571",
        "0xC00000FD",
    ],
    "preserve-separator-space-in-concatenated-prolog-fixture-strings": [
        "expected '.', got operator '.'",
        "TOK_DOT",
    ],
    "resolve-lnk1105-locked-output-on-windows": [
        "LNK1105",
        "error code 1224",
        "cannot close file",
    ],
    "scaffold-solidjs-vite-non-interactive": [
        "create-solid",
        "npm create solid",
        "What type of project would you like to create?",
    ],
    "scaffold-solidjs-vite-noninteractive": [
        "create-solid",
        "npm create solid",
    ],
    "unblock-react-router-typegen-enotempty": [
        "ENOTEMPTY: directory not empty, rmdir",
        "EPERM",
        ".react-router/types",
        "typesDirectory(ctx)",
    ],
    "verify-windows-hybrid-shell-commands": [
        "NativeCommandError",
        "Select-Object -First",
        "(PowerShell completed with no output)",
    ],
    "wait-webview-devtools-ready-after-relaunch": [
        "ECONNRESET",
        "socket hang up",
        "webview_devtools_remote",
        "adb forward tcp:9222",
    ],
}

# 路由冒烟测试：真实 trace 文本 -> 期望命中的 skill（族命中/族分离对照）
ROUTE_TESTS = [
    (
        "LINK : fatal error LNK1105: cannot close file 'bin\\yggdrasil.exe'; error code 1224",
        {"fix-windows-lnk1105-locked-output-exe", "resolve-lnk1105-locked-output-on-windows", "handle-locked-or-stale-test-binaries"},
    ),
    (
        "src/routes/jobs/index.tsx(44,23): error TS2554: Expected 1 arguments, but got 0.",
        {"fix-react19-useref-ts2554-no-default", "fix-ts2554-useref-tsc-batch", "fix-ts6133-unused-and-related-tsc-errors"},
    ),
    (
        "exit: -1073741571",
        {"fix-stack-overflow-large-test-fixtures", "fix-test-stack-overflow-large-fixtures", "fix-windows-0xc00000fd-stack-overflow", "fix-windows-stack-overflow-in-large-local-fixtures", "keep-large-test-fixtures-off-windows-stack"},
    ),
    (
        "d:\\dmls\\engine\\epilog\\epilog.dll : fatal error LNK1107: invalid or corrupt file: cannot read at 0x2F8",
        {"fix-lnk1107-odin-dll-import-lib"},
    ),
]


def _split_frontmatter(content: str) -> tuple[list[str], int]:
    """返回 frontmatter 行列表与闭合行的下标。"""
    lines = content.splitlines()
    assert lines and lines[0].strip() == "---", "缺少 frontmatter 开头"
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], i
    raise AssertionError("frontmatter 未闭合")


def _insert_triggers(content: str, triggers: list[str]) -> str:
    """在 frontmatter 闭合 --- 前插入 triggers 块，返回新全文。"""
    fm, closing = _split_frontmatter(content)
    block = ["triggers:"] + [f'  - "{t}"' for t in triggers]
    lines = content.splitlines()
    return "\n".join(lines[:closing] + block + lines[closing:]) + "\n"


def _parse_triggers(content: str) -> list[str]:
    """从 frontmatter 解析回 triggers（极简 YAML 列表读取）。"""
    fm, _ = _split_frontmatter(content)
    values: list[str] = []
    on = False
    for line in fm:
        stripped = line.strip()
        if stripped == "triggers:":
            on = True
            continue
        if on:
            if stripped.startswith("- "):
                values.append(stripped[2:].strip().strip('"'))
            else:
                break
    return values


def _route(text: str) -> dict[str, list[str]]:
    folded = text.casefold()
    hits: dict[str, list[str]] = {}
    for name, triggers in TRIGGERS.items():
        matched = [t for t in triggers if t.casefold() in folded]
        if matched:
            hits[name] = matched
    return hits


def main() -> None:
    dirs = sorted(p.name for p in SKILLS_ROOT.iterdir() if p.is_dir())
    missing = set(dirs) ^ set(TRIGGERS)
    if missing:
        raise SystemExit(f"TRIGGERS 与 skills_b 目录不一致，检查拼写：{sorted(missing)}")

    updated, skipped = 0, 0
    for name, triggers in TRIGGERS.items():
        path = SKILLS_ROOT / name / "SKILL.md"
        content = path.read_text(encoding="utf-8")

        if "triggers:" in _split_frontmatter(content)[0]:
            print(f"跳过（已有 triggers）：{name}")
            skipped += 1
            continue

        # 出处校验：每条签名必须能在 skill 全文中找到
        folded = content.casefold()
        untraceable = [t for t in triggers if t.casefold() not in folded]
        if untraceable:
            raise SystemExit(f"{name} 中签名在正文/证据里找不到出处：{untraceable}")

        path.write_text(_insert_triggers(content, triggers), encoding="utf-8")
        updated += 1

    # 回读校验：写入后逐文件解析回来，与策划记录一致
    for name, triggers in TRIGGERS.items():
        parsed = _parse_triggers((SKILLS_ROOT / name / "SKILL.md").read_text(encoding="utf-8"))
        assert parsed == triggers, f"{name} 回读不一致：{parsed}"

    # 跨 skill 共享签名报告（近重复族共命中是有意行为，列出供设计参考）
    shared: dict[str, list[str]] = {}
    for name, triggers in TRIGGERS.items():
        for t in triggers:
            shared.setdefault(t, []).append(name)
    multi = {t: names for t, names in shared.items() if len(names) > 1}

    print(f"\n已补写 {updated} 个，跳过 {skipped} 个；触发签名总数 {sum(len(v) for v in TRIGGERS.values())}")
    print(f"被多个 skill 共享的签名 {len(multi)} 条（族共命中）：")
    for t, names in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        print(f"  [{len(names)}] {t!r} -> {', '.join(sorted(names))}")

    # 路由冒烟测试：casefold 子串扫描等价于 Aho-Corasick 自动机的命中集合
    print("\n路由冒烟测试（签名快路径）：")
    failures = 0
    for text, expected in ROUTE_TESTS:
        hits = set(_route(text))
        ok = hits == expected
        failures += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {text[:60]!r}")
        print(f"      命中 {len(hits)}: {', '.join(sorted(hits))}")
        if not ok:
            print(f"      期望 {len(expected)}: {', '.join(sorted(expected))}")
            print(f"      多出: {sorted(hits - expected)} / 缺少: {sorted(expected - hits)}")
    if failures:
        raise SystemExit(f"{failures} 个路由冒烟测试未通过")


if __name__ == "__main__":
    main()
