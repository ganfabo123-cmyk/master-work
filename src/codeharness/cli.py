"""Interactive terminal entry point for CodeHarness."""

from __future__ import annotations

import argparse
from pathlib import Path
from .models import Task
from .orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(prefix_chars="-/")
    parser.add_argument("/resume", "--resume", dest="resume", metavar="SESSION_ID", help="Resume an existing trace session.")
    args = parser.parse_args()
    orchestrator = Orchestrator.from_environment(traces_root=Path("traces"))
    session_id = args.resume

    print("CodeHarness")
    print("输入问题开始对话；输入 exit 或 quit 退出。")
    try:
        while True:
            try:
                content = input("\nYou › ").strip()
            except EOFError:
                break
            if not content:
                continue
            if content.lower() in {"exit", "quit"}:
                break

            try:
                result = orchestrator.run(task=Task(content), session_id=session_id)
            except Exception as error:
                print(f"\nError: {error}")
                continue

            session_id = result.session_id
            if result.status == "failed":
                print(f"\nError: {result.error}")
                continue
            answer = str(result.content.content if result.content is not None else "")
            print(f"\nCodeHarness › {answer}")
    except KeyboardInterrupt:
        print()
    finally:
        if session_id is not None:
            print(f"Trace: traces/{session_id}")
