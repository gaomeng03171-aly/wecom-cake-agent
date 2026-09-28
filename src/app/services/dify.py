from pydantic import ValidationError

from app.clients.dify import get_dify_client
from app.schemas.dify import DinnerDifyOutput


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
