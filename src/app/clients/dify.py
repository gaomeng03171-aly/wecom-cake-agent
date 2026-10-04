import re
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.config import get_settings
from app.schemas.dify import DifyWorkflowResult


class DifyClient(ABC):
    @abstractmethod
    def run(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        raise NotImplementedError


class MockDifyClient(DifyClient):
    def run(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        if str(inputs.get("scene") or "dinner") == "order":
            return self._run_order(inputs)

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
        elif any(keyword in content for keyword in ("生成方案", "推荐方案", "有什么方案")):
            outputs = {
                "intent": "generate_proposals",
                "activity_title": None,
                "suggested_time": None,
                "deadline": None,
                "missing_fields": [],
                "reply": "我来根据大家的偏好生成聚餐方案。",
            }
        elif self._extract_vote_choice(content) is not None:
            outputs = {
                "intent": "vote",
                "activity_title": None,
                "suggested_time": None,
                "deadline": None,
                "proposal_choice": self._extract_vote_choice(content),
                "missing_fields": [],
                "reply": "已记录你的投票。",
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

    def _run_order(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        content = str(inputs.get("content", ""))
        intent = self._order_intent(content)
        product_name = self._extract_order_product(content)
        quantity = self._extract_order_quantity(content)
        size = self._extract_order_size(content)
        flavor = self._extract_order_flavor(content)
        message_on_cake = self._extract_cake_message(content)
        pickup_time, delivery_time = self._extract_fulfillment_times(content)
        delivery_address = self._extract_delivery_address(content)
        phone = self._extract_phone(content)
        budget_max = self._extract_budget(content)
        notes = self._extract_order_notes(content)

        reply = (
            "请告诉我订单的商品、数量、尺寸、口味和取货时间。"
            if intent == "unknown"
            else "收到，订单信息已记录。"
        )
        return DifyWorkflowResult(
            success=True,
            outputs={
                "intent": intent,
                "scenario": "cake",
                "order_title": "蛋糕订单",
                "product_name": product_name,
                "quantity": quantity,
                "size": size,
                "flavor": flavor,
                "message_on_cake": message_on_cake,
                "pickup_time": pickup_time,
                "delivery_time": delivery_time,
                "delivery_address": delivery_address,
                "phone": phone,
                "budget_max": budget_max,
                "notes": notes,
                "missing_fields": [],
                "reply": reply,
            },
        )

    def _order_intent(self, content: str) -> str:
        if any(keyword in content for keyword in ("取消", "不要了", "算了")):
            return "cancel_order"
        if any(
            keyword in content
            for keyword in ("确认下单", "确认订单", "就这个", "可以下单")
        ):
            return "confirm_order"
        if any(keyword in content for keyword in ("改成", "修改", "换成")):
            return "update_requirement"
        if any(
            keyword in content
            for keyword in ("下单", "预订", "我想订", "订一个", "做个", "做一个")
        ):
            return "create_order"
        if any(
            keyword in content
            for keyword in (
                "寸",
                "口味",
                "奶油",
                "写着",
                "取货",
                "送到",
                "预算",
                "蛋糕",
            )
        ):
            return "provide_requirement"
        return "unknown"

    def _extract_order_product(self, content: str) -> str | None:
        if "蛋糕" in content:
            return "蛋糕"
        if "鲜花" in content or "花束" in content:
            return "鲜花"
        if "维修" in content:
            return "维修服务"
        return None

    def _extract_order_quantity(self, content: str) -> int | None:
        match = re.search(
            r"([一二两三四五六七八九十\d]+)\s*(?:个|份|盒|束|台|只)",
            content,
        )
        if match:
            return _parse_chinese_number(match.group(1))
        return None

    def _extract_order_size(self, content: str) -> str | None:
        match = re.search(r"(\d+)\s*(?:寸|英寸|厘米|cm)", content)
        if match:
            unit = match.group(0).replace(str(match.group(1)), "").strip()
            return f"{match.group(1)}{unit or '寸'}"
        return None

    def _extract_order_flavor(self, content: str) -> str | None:
        flavors = ("草莓", "巧克力", "芒果", "榴莲", "抹茶", "芋泥", "奶油")
        for flavor in flavors:
            if flavor in content:
                return flavor
        return None

    def _extract_cake_message(self, content: str) -> str | None:
        match = re.search(r"(?:写着|写上|写)[：:]?\s*([^，。,\n]+)", content)
        if match:
            return match.group(1).strip()
        return None

    def _extract_fulfillment_times(
        self,
        content: str,
    ) -> tuple[str | None, str | None]:
        time_match = re.search(
            r"((?:今天|明天|后天|周[一二三四五六日天]).{0,6}?"
            r"(?:上午|中午|下午|晚上)?\s*[一二两三四五六七八九十\d]{1,3}"
            r"(?:点|:\d{2})?)",
            content,
        )
        time_value = time_match.group(1).strip() if time_match else None
        if time_value and ("送" in content or "配送" in content):
            return None, time_value
        return time_value, None

    def _extract_delivery_address(self, content: str) -> str | None:
        match = re.search(r"(?:送到|地址[：:]?)\s*([^，。,\n]+)", content)
        if match:
            return match.group(1).strip()
        return None

    def _extract_phone(self, content: str) -> str | None:
        match = re.search(r"1[3-9]\d{9}", content)
        return match.group(0) if match else None

    def _extract_order_notes(self, content: str) -> str | None:
        for keyword in ("不要香菜", "不要辣", "少糖", "无糖", "不需要蜡烛"):
            if keyword in content:
                return keyword
        return None

    def _extract_vote_choice(self, content: str) -> int | None:
        match = re.search(r"(?:选|投|方案)\s*([1-9])", content)
        if match:
            return int(match.group(1))
        return None

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


class HttpDifyClient(DifyClient):
    def __init__(
        self,
        api_base: str,
        api_key: str,
        user: str,
        timeout_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._user = user
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def run(self, inputs: dict[str, Any]) -> DifyWorkflowResult:
        try:
            with httpx.Client(
                base_url=self._api_base,
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=self._timeout_seconds,
                transport=self._transport,
            ) as client:
                response = client.post(
                    "workflows/run",
                    json={
                        "inputs": inputs,
                        "response_mode": "blocking",
                        "user": self._user,
                    },
                )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            return DifyWorkflowResult(
                success=False,
                error=f"Dify request failed: {exc}",
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return DifyWorkflowResult(
                success=False,
                error=f"Dify returned invalid JSON: {exc}",
            )

        data = payload.get("data")
        if not isinstance(data, dict):
            return DifyWorkflowResult(
                success=False,
                error="Dify response is missing data",
            )

        status = data.get("status")
        if status not in (None, "succeeded"):
            return DifyWorkflowResult(
                success=False,
                error=str(data.get("error") or f"Dify workflow status: {status}"),
            )

        outputs = data.get("outputs")
        if not isinstance(outputs, dict):
            return DifyWorkflowResult(
                success=False,
                error="Dify response is missing outputs",
            )

        return DifyWorkflowResult(success=True, outputs=outputs)


def get_dify_client() -> DifyClient:
    settings = get_settings()
    if settings.dify_client_mode == "mock":
        return MockDifyClient()
    if settings.dify_client_mode in {"real", "http"}:
        if not settings.dify_api_base or not settings.dify_api_key:
            raise RuntimeError("DIFY_API_BASE and DIFY_API_KEY are required")
        return HttpDifyClient(
            api_base=settings.dify_api_base,
            api_key=settings.dify_api_key,
            user=settings.dify_user,
            timeout_seconds=settings.dify_timeout_seconds,
        )

    raise RuntimeError(f"Unsupported Dify client mode: {settings.dify_client_mode}")


def get_order_dify_client() -> DifyClient:
    settings = get_settings()
    if settings.order_dify_mode == "mock":
        return MockDifyClient()
    if settings.order_dify_mode in {"auto", "real", "http"}:
        api_base = settings.dify_order_api_base or settings.dify_api_base
        api_key = settings.dify_order_api_key or settings.dify_api_key
        user = settings.dify_order_user or settings.dify_user
        if settings.order_dify_mode == "auto" and not api_key:
            return MockDifyClient()
        if not api_base or not api_key:
            raise RuntimeError(
                "Order Dify requires API base and API key"
            )
        return HttpDifyClient(
            api_base=api_base,
            api_key=api_key,
            user=user,
            timeout_seconds=settings.dify_order_timeout_seconds,
        )
    raise RuntimeError(
        f"Unsupported order Dify client mode: {settings.order_dify_mode}"
    )


def _parse_chinese_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    numerals = {
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    if value == "十":
        return 10
    if value in numerals:
        return numerals[value]
    if value.startswith("十") and value[1:] in numerals:
        return 10 + numerals[value[1:]]
    if value.endswith("十") and value[:-1] in numerals:
        return numerals[value[:-1]] * 10
    if "十" in value:
        tens, ones = value.split("十", 1)
        if tens in numerals and ones in numerals:
            return numerals[tens] * 10 + numerals[ones]
    return None
