from __future__ import annotations

import argparse
from pathlib import Path
import sys


REQUIRED_HEADINGS = (
    "## 1. Product goal",
    "## 2. Source index",
    "## 3. Confirmed domain facts",
    "## 4. Participants",
    "## 5. Domain information and visibility",
    "## 6. Domain workflow",
    "## 7. Architecture blueprint",
    "## 8. ROOM and event projection",
    "## 9. Acceptance scenarios",
    "## 10. Assumptions and unresolved decisions",
    "## 11. Approval",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Perform structural checks on APP_DESIGN.md.")
    parser.add_argument("design", type=Path)
    parser.add_argument("--approved", action="store_true")
    args = parser.parse_args()
    text = args.design.read_text(encoding="utf-8")
    errors = [f"missing heading: {heading}" for heading in REQUIRED_HEADINGS if heading not in text]
    if "NOT_DESIGNED" in text:
        errors.append("architecture still contains NOT_DESIGNED")
    if args.approved:
        for marker in ("design_status: APPROVED", "review_status: PASS", "requirements_confirmed: true", "blueprint_approved: true"):
            if marker not in text:
                errors.append(f"missing approval marker: {marker}")
        if "approved_revision: null" in text:
            errors.append("approved_revision is null")
    if errors:
        print("APP_DESIGN validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("APP_DESIGN structural validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
