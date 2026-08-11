"""Interactive terminal entry point for CoWorker."""

from __future__ import annotations

import argparse

from .core.models import Task
from .infra.runtimes import SessionRuntime


def main() -> None:
    parser = argparse.ArgumentParser(prefix_chars="-/")
    parser.add_argument("/app", "--app", default="incident_consultation", metavar="APP_NAME", help="Select apps/<app_name> (default: incident_consultation).")
    parser.add_argument("/resume", "--resume", dest="resume", metavar="SESSION_ID", help="Resume an existing trace session.")
    parser.add_argument("/web", "--web", action="store_true", help="Start the local scenario-neutral ROOM web console.")
    args = parser.parse_args()
    if args.web:
        if args.resume:
            parser.error("/resume cannot be used with /web")
        from .app import serve_web

        serve_web(app_name=args.app)
        return

    from .app import create_environment

    environment = create_environment(args.app)
    runtime = SessionRuntime(trace=environment.session.trace)
    session_id = args.resume
    print("CoWorker")
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
                result = runtime.run(environment, task=Task(content), session_id=session_id)
            except Exception as error:
                print(f"\nError: {error}")
                continue
            session_id = result.session_id
            if result.status == "failed":
                print(f"\nError: {result.error}")
                continue
            answer = str(result.content.content if result.content is not None else "")
            print(f"\nCoWorker › {answer}")
    except KeyboardInterrupt:
        print()
    finally:
        if session_id is not None:
            print(f"Trace: traces/{session_id}")
