"""Probe the configured Chat Completions endpoint with one small request.

No trace data is sent. The API key is used only in the Authorization header.
An optional --user-agent allows an explicit HTTP-client compatibility comparison.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from error_skill_extraction import HERE, WORKSPACE, endpoint, load_config, now, request_headers, save, usage_record


def redact(value, api_key):
    if isinstance(value, dict):
        return {k: redact(v, api_key) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, api_key) for v in value]
    if isinstance(value, str):
        if api_key:
            value = value.replace(api_key, "[REDACTED]")
        return re.sub(r"(?i)(bearer\s+)[^\s\"'<>]+", r"\1[REDACTED]", value)
    return value


def probe(config, user_agent="skill-extraction-probe/1.0", list_models=False):
    session_id = str(uuid.uuid4()) if config.get("sessionHeader") else None
    request_config = dict(config)
    if session_id:
        request_config["_session_id"] = session_id
    headers = request_headers(request_config)
    if user_agent:
        if "\n" in user_agent or "\r" in user_agent:
            raise ValueError("Invalid User-Agent")
        headers["User-Agent"] = user_agent
    payload = {"model": config["model"], "messages": [{"role": "user", "content": "Reply exactly OK."}],
               "stream": False}
    url = endpoint(config["base_url"])
    if list_models:
        url = url.removesuffix("/chat/completions") + "/models"
    report = {"endpoint": url, "model": config["model"], "started_at": now(),
              "session_header": config.get("sessionHeader") or None, "session_id": session_id,
              "user_agent": headers["User-Agent"], "request": None if list_models else payload,
              "operation": "list_models" if list_models else "chat_completion",
              "status": "failed", "http_status": None, "usage": usage_record({}),
              "note": "One API request; no trace files sent. Missing usage is unknown, not zero."}
    request = urllib.request.Request(report["endpoint"],
        data=None if list_models else json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="GET" if list_models else "POST")
    clock = time.perf_counter()
    try:
        with urllib.request.urlopen(request) as response:
            report["http_status"] = response.status
            report["response_headers"] = {k: response.headers.get(k) for k in
                ("Content-Type", "Server", "CF-Ray", "X-Request-ID") if response.headers.get(k)}
            text = response.read().decode("utf-8", errors="replace")
            try:
                body = json.loads(text)
                report["usage"] = usage_record(body)
                choices = body.get("choices") or []
                report["status"] = "responded" if (isinstance(body.get("data"), list) if list_models else choices) else "unexpected_response"
                report["response"] = body
            except (ValueError, TypeError, AttributeError):
                report["status"] = "unexpected_response"
                report["response_text"] = text
    except urllib.error.HTTPError as failure:
        report["http_status"] = failure.code
        report["response_headers"] = {k: failure.headers.get(k) for k in
            ("Content-Type", "Server", "CF-Ray", "X-Request-ID") if failure.headers.get(k)}
        report["error_body"] = failure.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as failure:
        report["error"] = str(failure)
    report["finished_at"] = now()
    report["seconds"] = time.perf_counter() - clock
    # Redact both normal and error responses before storing or printing anything.
    return redact(report, config["api_key"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=HERE / "error_skill_extraction.local.json")
    parser.add_argument("--user-agent", default="skill-extraction-probe/1.0")
    parser.add_argument("--list-models", action="store_true", help="GET /models; does not generate model tokens")
    stamp = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
    parser.add_argument("--output", type=Path, default=WORKSPACE / "skill-runs" / ("api-probe-" + stamp + ".json"))
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new --output")
    try:
        config = load_config(args.config)
        report = probe(config, args.user_agent, args.list_models)
        save(args.output, report)
    except (ValueError, OSError) as failure:
        parser.error(str(failure))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("Report: " + str(args.output.resolve()))
    if report["status"] != "responded":
        sys.exit(1)


if __name__ == "__main__":
    main()
