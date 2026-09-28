from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings
from app.schemas.dify import DifyWorkflowResult


class DifyClient(ABC):
    @abstractmethod
    def run(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        raise NotImplementedError


class MockDifyClient(DifyClient):
    def run(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        content = str(inputs.get("content", ""))
        if any(keyword in content for keyword in ("吃饭", "聚餐", "约饭")):
            outputs = {
                "intent": "create_dinner",
                "activity_title": "周末聚餐",
                "suggested_time": None,
                "deadline": None,
                "missing_fields": ["口味", "预算", "人数"],
                "reply": "收到，我来帮大家组织聚餐。请告诉我口味、预算和人数。",
            }
        else:
            outputs = {
                "intent": "unknown",
                "activity_title": None,
                "suggested_time": None,
                "deadline": None,
                "missing_fields": [],
                "reply": "请告诉我聚餐的时间、人数、口味和预算。",
            }
        return DifyWorkflowResult(success=True, outputs=outputs)


def get_dify_client() -> DifyClient:
    settings = get_settings()
    if settings.dify_client_mode == "mock":
        return MockDifyClient()

    raise RuntimeError("Real Dify client is not implemented yet.")
