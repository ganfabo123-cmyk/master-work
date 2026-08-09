"""Compare native tool history with compressed textual tool history.

Run after installing the project and configuring DEEPSEEK_API_KEY (or PRO_API):

    python tests/compare_tool_contexts.py

The default executes 10 attempts per mode. It makes real model calls and writes
canonical per-attempt traces plus a summary under tests/tool_context_benchmark_results/.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from time import perf_counter
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from codeharness.llm import OpenAICompatibleClient
from codeharness.models import Message, ToolCall
from codeharness.tools import ToolRegistry


RELEASE_REF = "rel-2026.08.05.17"
MAX_MODEL_TURNS = 6


class ReleaseSnapshot(BaseModel):
    release_id: str
    service: str
    deployed_at: str
    changed_components: list[str]
    baseline_5xx_percent: float


class ServiceSignals(BaseModel):
    release_id: str
    service: str
    current_5xx_percent: float
    sustained_minutes: int
    release_causality: Literal["confirmed", "uncertain"]
    error_budget_remaining_percent: float
    affected_endpoints: list[str]
    evidence: list[str]


class RollbackGate(BaseModel):
    release_id: str
    decision: Literal["rollback_now", "hold_and_investigate"]
    required_pre_actions: list[str]
    follow_up: str


tools = ToolRegistry()


@tools.register
def get_release_snapshot(
    release_ref: Annotated[
        str,
        Field(description="需要分析的发布标识，例如 rel-2026.08.05.17。"),
    ],
) -> ReleaseSnapshot:
    """读取发布快照，返回服务、发布时间、变更组件和发布前错误率基线。"""
    if release_ref != RELEASE_REF:
        raise ValueError(f"release not found: {release_ref}")
    return ReleaseSnapshot(
        release_id=RELEASE_REF,
        service="checkout-api",
        deployed_at="2026-08-05T18:40:00+08:00",
        changed_components=["payment-routing", "retry-policy"],
        baseline_5xx_percent=0.4,
    )


@tools.register
def analyze_service_signals(
    release_id: Annotated[str, Field(description="必须使用发布快照返回的 release_id。")],
    service: Annotated[str, Field(description="必须使用发布快照返回的 service 名称。")],
    lookback_minutes: Annotated[int, Field(description="需要分析的最近监控分钟数，取值范围 1 到 15。", ge=1, le=15)],
) -> ServiceSignals:
    """分析指定发布和服务的错误率、持续时间、因果证据与错误预算。"""
    if release_id != RELEASE_REF or service != "checkout-api":
        raise ValueError("release_id and service must come from get_release_snapshot")
    return ServiceSignals(
        release_id=release_id,
        service=service,
        current_5xx_percent=4.2,
        sustained_minutes=min(lookback_minutes, 3),
        release_causality="confirmed",
        error_budget_remaining_percent=71.0,
        affected_endpoints=["POST /v1/checkout", "POST /v1/payment-intents"],
        evidence=[
            "5xx rose from 0.4% to 4.2% within one minute of deployment",
            "rollback canary restored successful payment routing in one zone",
        ],
    )


@tools.register
def evaluate_rollback_gate(
    release_id: Annotated[str, Field(description="必须使用信号分析返回的 release_id。")],
    observed_5xx_percent: Annotated[float, Field(description="信号分析得到的当前 5xx 百分比。", ge=0)],
    sustained_minutes: Annotated[int, Field(description="信号分析得到的异常持续分钟数。", ge=0)],
    release_causality: Annotated[Literal["confirmed", "uncertain"], Field(description="信号分析对发布因果关系的结论。")],
    error_budget_remaining_percent: Annotated[float, Field(description="信号分析得到的剩余错误预算百分比。", ge=0, le=100)],
) -> RollbackGate:
    """依据错误阈值、持续时间、因果证据和错误预算生成受控的回滚决策。"""
    if release_id != RELEASE_REF:
        raise ValueError("release_id must come from analyze_service_signals")
    can_rollback = observed_5xx_percent > 3 and sustained_minutes >= 2 and release_causality == "confirmed"
    return RollbackGate(
        release_id=release_id,
        decision="rollback_now" if can_rollback else "hold_and_investigate",
        required_pre_actions=[
            "record release_id, current error rate, affected endpoints, and evidence",
            "notify the on-call release owner before executing the recorded rollback",
        ],
        follow_up=(
            "Observe checkout-api for five minutes after rollback; escalate if 5xx remains above 1%."
            if can_rollback
            else "Collect additional request samples and application logs before deciding."
        ),
    )


BUSINESS_TOOLS = (get_release_snapshot, analyze_service_signals, evaluate_rollback_gate)
EXPECTED_SEQUENCE = tuple(tool.__name__ for tool in BUSINESS_TOOLS)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare native and compressed tool-call contexts.")
    parser.add_argument("--runs", type=int, default=10, help="Attempts per mode (default: 10).")
    parser.add_argument("--model", default="deepseek-v4-flash", help="Model name passed to the configured endpoint.")
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")

    output_dir = Path("tests/tool_context_benchmark_results") / datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir.mkdir(parents=True, exist_ok=False)
    client = OpenAICompatibleClient.from_environment()
    attempts: list[dict[str, Any]] = []

    for mode in ("native", "compressed"):
        for index in range(1, args.runs + 1):
            print(f"[{mode} {index}/{args.runs}] running")
            attempt = run_attempt(client, args.model, mode)
            attempt["mode"] = mode
            attempt["attempt"] = index
            attempts.append(attempt)
            (output_dir / f"{mode}_{index:02d}.jsonl").write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in attempt.pop("trace")) + "\n",
                encoding="utf-8",
            )

    (output_dir / "attempts.json").write_text(json.dumps(attempts, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = build_summary(attempts, args.model)
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Results: {output_dir}")


def run_attempt(client: OpenAICompatibleClient, model: str, mode: Literal["native", "compressed"]) -> dict[str, Any]:
    system = Message(
        "developer",
        """You are a production release risk analyst. Answer in Chinese.

You must complete this workflow in order and use the exact values returned by each prior tool:
1. Call get_release_snapshot with the release reference from the user request.
2. Call analyze_service_signals using the release_id and service returned by the snapshot, with lookback_minutes=3.
3. Call evaluate_rollback_gate using the metrics and evidence conclusion returned by signal analysis.

Do not skip, reorder, parallelize, or invent any step. After all three tools have succeeded, return a direct final response.""",
    )
    user = Message(
        "user",
        f"Assess release {RELEASE_REF}. Decide whether checkout-api should be rolled back now and provide the immediate operator actions.",
    )
    canonical_messages: list[Message] = [system, user]
    compressed_messages: list[Message] = [system, user]
    trace: list[dict[str, Any]] = []
    tool_sequence: list[str] = []
    input_tokens = output_tokens = total_tokens = 0
    started = perf_counter()

    schemas = tools.schemas_for(BUSINESS_TOOLS)
    for model_turn in range(1, MAX_MODEL_TURNS + 1):
        request_messages = canonical_messages if mode == "native" else compressed_messages
        result = client.generate(model=model, messages=request_messages, tools=schemas)
        input_tokens += result.input_tokens or 0
        output_tokens += result.output_tokens or 0
        total_tokens += result.total_tokens or 0
        trace.append(
            {
                "event_type": "assistant",
                "model_turn": model_turn,
                "request_messages": [message.as_dict() for message in request_messages],
                "content": result.parsed_content,
                "tool_calls": [tool_call_as_dict(call) for call in result.tool_calls],
                "input_tokens": result.input_tokens,
                "output_tokens": result.output_tokens,
                "total_tokens": result.total_tokens,
                "duration_ms": result.duration_ms,
                "finish_reason": result.finish_reason,
                "parse_error": result.parse_error,
            }
        )
        if result.parse_error:
            return attempt_result("parse_error", tool_sequence, trace, input_tokens, output_tokens, total_tokens, started, error=result.parse_error)

        if not result.tool_calls:
            canonical_messages.append(Message("assistant", result.parsed_content or ""))
            return attempt_result(
                "plain_text_final",
                tool_sequence,
                trace,
                input_tokens,
                output_tokens,
                total_tokens,
                started,
                final_text=result.parsed_content,
            )

        expected = EXPECTED_SEQUENCE[len(tool_sequence)] if len(tool_sequence) < len(EXPECTED_SEQUENCE) else None
        if len(result.tool_calls) != 1 or result.tool_calls[0].name != expected:
            return attempt_result(
                "tool_protocol_violation",
                tool_sequence,
                trace,
                input_tokens,
                output_tokens,
                total_tokens,
                started,
                error=f"expected exactly {expected!r}, received {[call.name for call in result.tool_calls]!r}",
            )

        call = result.tool_calls[0]
        assistant_message = Message(
            "assistant",
            result.parsed_content or "",
            tool_calls=(ToolCall(call.id, call.name, json.dumps(call.arguments, ensure_ascii=False)),),
        )
        canonical_messages.append(assistant_message)
        try:
            value = tools.invoke(call.name, call.arguments)
            success = True
        except Exception as error:
            value = str(error)
            success = False
        tool_message = Message("tool", tool_result_text(value), name=call.name, tool_call_id=call.id)
        canonical_messages.append(tool_message)
        tool_sequence.append(call.name)
        trace.append(
            {
                "event_type": "tool",
                "tool_call_id": call.id,
                "tool": call.name,
                "arguments": call.arguments,
                "success": success,
                "result": json.loads(tool_message.content),
            }
        )
        if not success:
            return attempt_result("tool_error", tool_sequence, trace, input_tokens, output_tokens, total_tokens, started, error=tool_message.content)

        if mode == "compressed":
            compressed_messages.append(Message("user", compressed_tool_context(call, value)))

    return attempt_result("max_turns", tool_sequence, trace, input_tokens, output_tokens, total_tokens, started)


def compressed_tool_context(call: ToolCall, value: Any) -> str:
    """The proposed textual replacement for one native assistant/tool exchange."""
    return (
        f"我刚才调用了 {call.name} 工具。\n"
        f"输入参数为：{json.dumps(call.arguments, ensure_ascii=False)}\n"
        f"工具结果为：{tool_result_text(value)}"
    )


def tool_result_text(value: Any) -> str:
    if isinstance(value, BaseModel):
        return value.model_dump_json()
    return json.dumps(value, ensure_ascii=False)


def tool_call_as_dict(call: ToolCall) -> dict[str, Any]:
    return {"id": call.id, "name": call.name, "arguments": call.arguments}


def attempt_result(
    outcome: str,
    tool_sequence: list[str],
    trace: list[dict[str, Any]],
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    started: float,
    **extra: Any,
) -> dict[str, Any]:
    return {
        "outcome": outcome,
        "tool_sequence": tool_sequence,
        "completed_three_tool_rounds": tool_sequence == list(EXPECTED_SEQUENCE),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "duration_ms": round((perf_counter() - started) * 1000, 2),
        "trace": trace,
        **extra,
    }


def build_summary(attempts: list[dict[str, Any]], model: str) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for attempt in attempts:
        grouped[attempt["mode"]].append(attempt)

    summary: dict[str, Any] = {
        "model": model,
        "task": f"Release rollback assessment for {RELEASE_REF}",
        "expected_tool_sequence": list(EXPECTED_SEQUENCE),
        "comparison_note": "Compressed mode replaces completed native tool exchanges with textual summaries.",
        "modes": {},
    }
    for mode, rows in grouped.items():
        count = len(rows)
        summary["modes"][mode] = {
            "attempts": count,
            "three_tool_round_successes": sum(row["completed_three_tool_rounds"] for row in rows),
            "outcomes": {outcome: sum(row["outcome"] == outcome for row in rows) for outcome in sorted({row["outcome"] for row in rows})},
            "average_input_tokens": round(sum(row["input_tokens"] for row in rows) / count, 2),
            "average_output_tokens": round(sum(row["output_tokens"] for row in rows) / count, 2),
            "average_total_tokens": round(sum(row["total_tokens"] for row in rows) / count, 2),
            "average_duration_ms": round(sum(row["duration_ms"] for row in rows) / count, 2),
        }
    return summary


if __name__ == "__main__":
    main()
