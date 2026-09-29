from abc import ABC, abstractmethod
import re
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
        if any(keyword in content for keyword in ("约饭", "聚餐", "吃饭吗")):
            outputs = {
                "intent": "create_dinner",
                "activity_title": "周末聚餐",
                "suggested_time": None,
                "deadline": None,
                "missing_fields": ["口味", "预算", "人数"],
                "reply": "收到，我来帮大家组织聚餐。请告诉我口味、预算和人数。",
            }
        elif any(
            keyword in content
            for keyword in ("想吃", "预算", "可以", "有空", "不要", "不吃", "不能吃")
        ):
            available_time = self._extract_available_time(content)
            cuisine = self._extract_cuisine(content)
            budget = self._extract_budget(content)
            notes = self._extract_notes(content)
            missing_fields = []
            if available_time is None:
                missing_fields.append("时间")
            if cuisine is None:
                missing_fields.append("口味")
            if budget is None:
                missing_fields.append("预算")

            outputs = {
                "intent": "provide_preference",
                "activity_title": None,
                "suggested_time": None,
                "deadline": None,
                "available_time": available_time,
                "cuisine_preference": cuisine,
                "budget_max": budget,
                "notes": notes,
                "missing_fields": missing_fields,
                "reply": "已记录你的偏好。",
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

    def _extract_available_time(self, content: str) -> str | None:
        keywords = ("周六", "周日", "周五", "周四", "周三", "周二", "周一", "晚上", "中午")
        for keyword in keywords:
            if keyword in content:
                return keyword
        return None

    def _extract_cuisine(self, content: str) -> str | None:
        cuisines = ("火锅", "川菜", "烧烤", "日料", "粤菜", "湘菜", "西餐")
        for cuisine in cuisines:
            if cuisine in content:
                return cuisine
        return None

    def _extract_budget(self, content: str) -> int | None:
        match = re.search(r"(\d+)\s*(?:元|块)", content)
        if match:
            return int(match.group(1))
        match = re.search(r"预算\s*(\d+)", content)
        if match:
            return int(match.group(1))
        return None

    def _extract_notes(self, content: str) -> str | None:
        if "不要香菜" in content:
            return "不要香菜"
        if "不要辣" in content:
            return "不要辣"
        if "不能吃辣" in content or "不吃辣" in content:
            return "不要辣"
        return None


def get_dify_client() -> DifyClient:
    settings = get_settings()
    if settings.dify_client_mode == "mock":
        return MockDifyClient()

    raise RuntimeError("Real Dify client is not implemented yet.")
