import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.clients.dify import get_order_dify_client
from app.config import get_settings
from app.services.dify import DifyServiceError, analyze_order_message


COMPARABLE_FIELDS = (
    "intent",
    "scenario",
    "order_title",
    "customer_name",
    "phone",
    "product_name",
    "quantity",
    "size",
    "flavor",
    "message_on_cake",
    "pickup_time",
    "delivery_time",
    "delivery_address",
    "budget_max",
    "notes",
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
    regex_fields = case.get("regex_fields", {})

    for field in COMPARABLE_FIELDS:
        if field not in expected or field in ignored_fields:
            continue
        if field in regex_fields:
            continue
        actual_value = outputs.get(field)
        expected_value = expected[field]
        if normalize(actual_value) != normalize(expected_value):
            failures.append(
                f"{field}: expected={expected_value!r}, actual={actual_value!r}"
            )

    for field, pattern in regex_fields.items():
        actual_value = str(outputs.get(field) or "")
        if not re.search(pattern, actual_value):
            failures.append(
                f"{field}: expected pattern={pattern!r}, "
                f"actual={actual_value!r}"
            )

    if "missing_fields" not in ignored_fields:
        expected_missing = expected.get("missing_fields")
        if expected_missing is not None:
            actual_missing = outputs.get("missing_fields", [])
            if normalize(actual_missing) != normalize(expected_missing):
                failures.append(
                    f"missing_fields: expected={expected_missing!r}, "
                    f"actual={actual_missing!r}"
                )

    reply = str(outputs.get("reply", ""))
    for keyword in case.get("reply_contains", []):
        if keyword not in reply:
            failures.append(f"reply missing keyword: {keyword!r}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate real order Dify workflow cases."
    )
    parser.add_argument(
        "--cases",
        default="docs/order-dify-test-cases.json",
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

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.only:
        cases = [case for case in cases if args.only in case["name"]]
    if not cases:
        print("No matching test cases.")
        return 1

    settings = get_settings()
    client = get_order_dify_client()
    api_base = settings.dify_order_api_base or settings.dify_api_base
    api_key_source = (
        "DIFY_ORDER_API_KEY"
        if settings.dify_order_api_key
        else "DIFY_API_KEY"
        if settings.dify_api_key
        else "(empty)"
    )
    print(
        f"Mode: {settings.order_dify_mode} | "
        f"Client: {type(client).__name__} | "
        f"API base: {api_base or '(empty)'} | "
        f"Key source: {api_key_source}"
    )

    passed = 0
    failed = 0

    for index, case in enumerate(cases, start=1):
        failures: list[str] = []
        outputs: dict[str, Any] = {}
        try:
            analysis = analyze_order_message(case["input"])
            outputs = analysis.model_dump()
            failures.extend(compare_case(case, outputs))
        except (DifyServiceError, ValidationError) as exc:
            failures.append(str(exc))

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
