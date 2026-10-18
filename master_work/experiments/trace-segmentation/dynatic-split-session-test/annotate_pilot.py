#!/usr/bin/env python3
"""Apply the first manually reviewed boundary labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


LABELS = {
    # Both algorithms proposed these boundaries.
    "claude_code:07b57159-218e-4330-a64e-0ec4b4355056:47": ("keep", "project specification ends and implementation begins"),
    "claude_code:07b57159-218e-4330-a64e-0ec4b4355056:548": ("keep", "completed implementation phase followed by a new build phase"),
    "claude_code:09d9abe9-0a02-4bd1-8129-3b864695079d:247": ("keep", "new user request changes the goal to local icon replacement"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:41": ("remove", "multiboot investigation and tool lookup are one continuous task"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:837": ("keep", "new user request starts documentation work after the prior feature"),
    "claude_code:39082932-131c-40a9-872d-1d3ac8ed1fd6:355": ("keep", "new build/test result starts a distinct debugging phase"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:589": ("remove", "typo fix continues directly into the edit"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:1012": ("remove", "interface removal and following edit are one refactor"),
    "claude_code:4222016d-1932-4abb-94b3-463203bd8876:400": ("remove", "build-script changes continue the same compilation fix"),
    "claude_code:4222016d-1932-4abb-94b3-463203bd8876:1059": ("keep", "explicit new UI requirements start a new task"),
    "claude_code:47d9fc04-420c-47bb-8ac0-85780af22632:115": ("remove", "directory creation and file writes are one implementation phase"),
    "claude_code:6a7964ed-6f92-4eee-ae5e-3f91a6445833:212": ("keep", "explicit Stage 2 request follows completed Stage 1"),
    "claude_code:6a7964ed-6f92-4eee-ae5e-3f91a6445833:516": ("remove", "accessor edits continue the same internal refactor"),
    "claude_code:7563bddf-c1a0-4c3e-86ee-062bf288e6d3:499": ("remove", "server verification and formatter repair are one task"),
    "claude_code:860618e1-0cf6-43c6-81cf-fe67123082ba:176": ("remove", "interrupted retry is not a new task boundary"),
    "claude_code:860618e1-0cf6-43c6-81cf-fe67123082ba:705": ("keep", "new contact-page requirement begins after the prior discussion"),
    "claude_code:92833a43-c30d-4b44-8447-c32ee17d6e6e:136": ("remove", "build and verification commands continue the same task"),
    "claude_code:a20a4070-6246-4e9e-adf6-f38b0c1dc3fa:571": ("remove", "dashboard rewrite continues directly into file writing"),
    "claude_code:ba1b4916-b581-4e05-9a5c-c1d8ffc9b50a:68": ("remove", "corpus analysis and script writing are one design task"),
    "claude_code:c84c0ad3-c368-40df-87b1-5ef9effe237a:310": ("remove", "backend diagnosis continues into reads"),
    # Best-first-only boundaries.
    "claude_code:07b57159-218e-4330-a64e-0ec4b4355056:449": ("remove", "version compatibility verification is still the same task"),
    "claude_code:07b57159-218e-4330-a64e-0ec4b4355056:495": ("remove", "reference-file move and README writing are one cleanup phase"),
    "claude_code:09d9abe9-0a02-4bd1-8129-3b864695079d:411": ("remove", "theme implementation continues into the next edit"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:167": ("keep", "user-provided build result starts a separate build/debug phase"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:208": ("remove", "environment diagnosis and code edit remain one task"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:315": ("keep", "explicit snake compatibility request begins a new task"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:356": ("keep", "explicit graphics request changes the sub-goal"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:413": ("keep", "explicit text/color requirements begin a new subtask"),
    "claude_code:39082932-131c-40a9-872d-1d3ac8ed1fd6:109": ("remove", "fixture writing continues into file writes"),
    "claude_code:39082932-131c-40a9-872d-1d3ac8ed1fd6:792": ("keep", "explicit Stage 2 request follows a completed stage"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:227": ("remove", "error-message implementation continues into writing"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:341": ("remove", "wrapper update and verification are one task"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:404": ("remove", "test summary and project bookkeeping are one phase"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:444": ("remove", "implementation files are being written in sequence"),
    "claude_code:4222016d-1932-4abb-94b3-463203bd8876:730": ("remove", "build diagnosis continues directly into the fix"),
    "claude_code:47d9fc04-420c-47bb-8ac0-85780af22632:740": ("remove", "file inspection continues into grep"),
    "claude_code:47d9fc04-420c-47bb-8ac0-85780af22632:1042": ("remove", "profile and build-script edits are one implementation"),
    "claude_code:6a7964ed-6f92-4eee-ae5e-3f91a6445833:402": ("remove", "text replacement continues into command execution"),
    "claude_code:7563bddf-c1a0-4c3e-86ee-062bf288e6d3:288": ("remove", "route diagnosis and route creation are one task"),
    "claude_code:7563bddf-c1a0-4c3e-86ee-062bf288e6d3:780": ("remove", "subreddit route changes are one continuous page refactor"),
    # Recall-first-only boundaries.
    "claude_code:07b57159-218e-4330-a64e-0ec4b4355056:83": ("remove", "reverse-mode edits are one continuous implementation"),
    "claude_code:09d9abe9-0a02-4bd1-8129-3b864695079d:207": ("keep", "explicit boot-screen question starts a new UI issue"),
    "claude_code:17c2cf98-e64a-43c6-932e-fa7efcade358:140": ("remove", "LSP diagnosis and Makefile edit remain one task"),
    "claude_code:39082932-131c-40a9-872d-1d3ac8ed1fd6:794": ("keep", "explicit Stage 2 request follows completed Stage 1"),
    "claude_code:39082932-131c-40a9-872d-1d3ac8ed1fd6:1197": ("move", "README work is a new deliverable but boundary should be after the final test result"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:61": ("remove", "initial inspection continues into reads and tests"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:631": ("remove", "test verification and fixture creation are one feature phase"),
    "claude_code:3be5ba0c-62b2-4645-8589-9216be0c10d8:1094": ("remove", "runtime requirement investigation continues into searches"),
    "claude_code:4222016d-1932-4abb-94b3-463203bd8876:290": ("move", "README is a new deliverable, but cut should follow the bridge smoke-test result"),
    "claude_code:4222016d-1932-4abb-94b3-463203bd8876:1151": ("keep", "explicit 80/20 layout request starts a new UI task"),
    "claude_code:47d9fc04-420c-47bb-8ac0-85780af22632:374": ("remove", "build wiring continues into inspection"),
    "claude_code:47d9fc04-420c-47bb-8ac0-85780af22632:1057": ("remove", "build command preparation continues into execution"),
    "claude_code:6a7964ed-6f92-4eee-ae5e-3f91a6445833:309": ("remove", "compiler workaround continues into grep"),
    "claude_code:860618e1-0cf6-43c6-81cf-fe67123082ba:127": ("remove", "locked-directory diagnosis and fix are one task"),
    "claude_code:860618e1-0cf6-43c6-81cf-fe67123082ba:461": ("remove", "CSS files are written as one implementation batch"),
    "claude_code:92833a43-c30d-4b44-8447-c32ee17d6e6e:72": ("remove", "library split continues into the C API edit"),
    "claude_code:c99032e9-377b-4ae9-a9a9-ec7752b059cd:154": ("remove", "term data structure implementation continues into writing"),
    "claude_code:c99032e9-377b-4ae9-a9a9-ec7752b059cd:820": ("remove", "remaining source files are written in one batch"),
    "claude_code:da5d32d6-547f-45ae-a5b5-4747ed06542f:59": ("remove", "transport implementation continues into wiring"),
    "claude_code:da5d32d6-547f-45ae-a5b5-4747ed06542f:572": ("remove", "relaunch and verification continue the same build task"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    selected = []
    for item in data["items"]:
        if item["annotation_id"] not in LABELS:
            continue
        label, reason = LABELS[item["annotation_id"]]
        reviewed = dict(item)
        reviewed["label"] = label
        reviewed["reason"] = reason
        selected.append(reviewed)
    result = {
        "schema_version": "boundary-review-pilot-v1",
        "source": str(args.input),
        "manual_reviewed_count": len(selected),
        "items": selected,
        "label_counts": {label: sum(item["label"] == label for item in selected) for label in ("keep", "move", "remove")},
        "note": "This is a manually reviewed pilot set, not a complete gold standard for all event positions.",
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"reviewed={len(selected)}")
    print(f"labels={result['label_counts']}")
    print(f"output={args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
