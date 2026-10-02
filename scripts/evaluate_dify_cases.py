import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.clients.dify import get_dify_client
from app.schemas.dify import DinnerDifyOutput

COMPARABLE_FIELDS = (
    "intent",
    "activity_title",
    "suggested_time",
    "deadline",
    "available_time",
    "cuisine_preference",
    "budget_max",
    "notes",
    "proposal_choice",
    "missing_fields",
)


def normalize(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(value)
    return value


def compare_case(
    case: dict[str, Any],
    outputs: dict[str, Any],
) -> list[str]:
    failures: list[str] = []
    expected = case["expected"]
    ignored_fields = set(case.get("ignore_fields", []))

    for field in COMPARABLE_FIELDS:
        if field not in expected or field in ignored_fields:
            continue
        actual_value = outputs.get(field)
        expected_value = expected[field]
        if normalize(actual_value) != normalize(expected_value):
            failures.append(
                f"{field}: expected={expected_value!r}, actual={actual_value!r}"
            )

    for field in case.get("required_non_null_fields", []):
        if outputs.get(field) in (None, "", []):
            failures.append(f"{field}: expected a non-null value")

    reply = str(outputs.get("reply", ""))
    for keyword in case.get("reply_contains", []):
        if keyword not in reply:
            failures.append(f"reply missing keyword: {keyword!r}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate real Dify workflow cases.")
    parser.add_argument(
        "--cases",
        default="docs/dify-workflow-test-cases.json",
        help="Path to the JSON test case file.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop after the first failed case.",
    )
    parser.add_argument(
        "--only",
        default="",
        help="Only run cases whose name contains this value.",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    if args.only:
        cases = [
            case for case in cases if args.only in case["name"]
        ]
    if not cases:
        print("No matching test cases.")
        return 1
    client = get_dify_client()

    passed = 0
    failed = 0

    for index, case in enumerate(cases, start=1):
        result = client.run({"content": case["input"]})
        failures: list[str] = []

        if not result.success:
            failures.append(f"workflow error: {result.error}")
            outputs: dict[str, Any] = {}
        else:
            try:
                validated = DinnerDifyOutput.model_validate(result.outputs)
                outputs = validated.model_dump()
                failures.extend(compare_case(case, outputs))
            except ValidationError as exc:
                outputs = result.outputs
                failures.append(f"schema validation failed: {exc}")

        if failures:
            failed += 1
            print(f"FAIL {index:02d} {case['name']} | {case['input']}")
            for failure in failures:
                print(f"  - {failure}")
            print(f"  actual={json.dumps(outputs, ensure_ascii=False)}")
            if args.fail_fast:
                break
        else:
            passed += 1
            print(f"PASS {index:02d} {case['name']}")

    total = passed + failed
    rate = (passed / total * 100) if total else 0.0
    print(f"\nSummary: passed={passed}, failed={failed}, total={total}, rate={rate:.1f}%")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
