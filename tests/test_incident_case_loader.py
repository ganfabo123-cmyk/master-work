from __future__ import annotations

from pathlib import Path

from codeharness.apps.incident_consultation.case_loader import load_rcaeval_case


def write_case(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "inject_time.txt").write_text("1000", encoding="utf-8")
    (root / "metrics.csv").write_text(
        "time,checkoutservice_cpu,redis_mem\n"
        "900,1,10\n950,1,10\n1000,8,40\n1050,9,42\n",
        encoding="utf-8",
    )
    (root / "logs.csv").write_text(
        "time,timestamp,container_name,message,level,error,cluster_id,log_template\n"
        "00:16,950000000000,checkoutservice,normal,info,,1,normal\n"
        "00:17,1001000000000,checkoutservice,timeout,error,deadline,2,timeout\n",
        encoding="utf-8",
    )
    (root / "traces.csv").write_text(
        "time,traceID,spanID,serviceName,methodName,operationName,startTimeMillis,startTime,duration,statusCode,parentSpanID\n"
        "00:16,t1,s1,checkoutservice,PlaceOrder,PlaceOrder,950000,0,10,0,\n"
        "00:17,t2,s2,redis,Get,Get,1001000,0,900,2,s1\n",
        encoding="utf-8",
    )
    return root


def test_loader_builds_bounded_source_addressable_evidence(tmp_path: Path) -> None:
    case = load_rcaeval_case(write_case(tmp_path / "case"))

    assert case.case_id == "rcaeval-multi-source-sample"
    assert case.injection_time == 1000
    assert set(case.evidence) == {"metrics", "logs", "traces"}
    assert all(0 < len(items) <= 8 for items in case.evidence.values())
    assert {item.source_file for items in case.evidence.values() for item in items} == {"metrics.csv", "logs.csv", "traces.csv"}
    assert len({item.evidence_id for items in case.evidence.values() for item in items}) == sum(len(items) for items in case.evidence.values())
