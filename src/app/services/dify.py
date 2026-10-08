from pydantic import ValidationError

from app.clients.dify import get_dify_client, get_order_dify_client
from app.schemas.dify import DinnerDifyOutput, OrderDifyOutput
from app.services.order_requirements import (
    annotate_relative_times,
    build_order_requirements,
    extract_customer_note,
    extract_order_reference,
    format_order_confirmation,
    format_order_follow_up,
    missing_order_fields,
)


class DifyServiceError(RuntimeError):
    pass


def analyze_dinner_message(content: str) -> DinnerDifyOutput:
    client = get_dify_client()
    result = client.run({"content": content})

    if not result.success:
        raise DifyServiceError(result.error or "Dify workflow failed")

    try:
        return DinnerDifyOutput.model_validate(result.outputs)
    except ValidationError as exc:
        raise DifyServiceError(f"invalid Dify output: {exc}") from exc


def analyze_order_message(content: str) -> OrderDifyOutput:
    client = get_order_dify_client()
    result = client.run({"content": content, "scene": "order"})

    if not result.success:
        raise DifyServiceError(result.error or "Dify workflow failed")

    try:
        analysis = OrderDifyOutput.model_validate(result.outputs)
    except ValidationError as exc:
        raise DifyServiceError(f"invalid Dify output: {exc}") from exc

    requirements = build_order_requirements(analysis)
    requirements = annotate_relative_times(requirements)
    if analysis.intent == "unknown" and _has_substantive_requirements(
        requirements
    ):
        analysis = analysis.model_copy(update={"intent": "provide_requirement"})
    missing_fields = missing_order_fields(requirements, analysis.scenario)
    confirmation_text = None
    reply = analysis.reply

    if analysis.intent in {
        "create_order",
        "provide_requirement",
        "update_requirement",
    }:
        if missing_fields:
            reply = format_order_follow_up(
                missing_fields,
                requirements,
                analysis.scenario,
            )
        else:
            confirmation_text = format_order_confirmation(
                requirements,
                analysis.scenario,
            )
            reply = confirmation_text

    return analysis.model_copy(
        update={
            "order_reference": (
                analysis.order_reference
                or extract_order_reference(content)
            ),
            "customer_note": (
                analysis.customer_note
                or extract_customer_note(content)
            ),
            "customer_expected_price": (
                analysis.customer_expected_price
                if analysis.customer_expected_price is not None
                else analysis.budget_max
            ),
            "customer_expected_price_text": (
                analysis.customer_expected_price_text
                or (
                    f"{analysis.budget_max}元"
                    if analysis.budget_max is not None
                    else None
                )
            ),
            "product_name": requirements.get(
                "product_name",
                analysis.product_name,
            ),
            "pickup_time": requirements.get(
                "pickup_time",
                analysis.pickup_time,
            ),
            "delivery_time": requirements.get(
                "delivery_time",
                analysis.delivery_time,
            ),
            "requirements": requirements,
            "missing_fields": missing_fields,
            "confirmation_text": confirmation_text,
            "reply": reply,
        }
    )


def _has_substantive_requirements(requirements: dict) -> bool:
    return any(
        key != "notes" and value not in (None, "", [], {})
        for key, value in requirements.items()
    )
