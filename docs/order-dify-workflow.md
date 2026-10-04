# 订单 Dify Workflow

订单 Agent 默认使用自动模式：

```text
ORDER_DIFY_MODE=auto
```

`auto` 会优先使用 `DIFY_ORDER_API_KEY`，没有时复用 `DIFY_API_KEY`；两者都没有时退回本地规则解析。也可以显式设置为 `mock` 或 `real`。

真实订单 Workflow 不应与聚餐意图 Workflow 混用，因为输出字段不同。

## 环境变量

```text
ORDER_DIFY_MODE=real
DIFY_ORDER_API_BASE=https://api.dify.ai/v1
DIFY_ORDER_API_KEY=你的订单工作流APIKey
DIFY_ORDER_USER=wecom-order-agent
DIFY_ORDER_TIMEOUT_SECONDS=30
```

如果订单 Workflow 已配置为通用 `DIFY_API_KEY`，保持 `ORDER_DIFY_MODE=auto` 即可。

## Workflow 输入

```text
content
```

## Workflow 输出

必须只输出一个 JSON 对象，字段如下：

```json
{
  "intent": "create_order",
  "scenario": "cake",
  "order_title": "蛋糕订单",
  "customer_name": null,
  "phone": null,
  "product_name": "蛋糕",
  "quantity": 1,
  "size": "8寸",
  "flavor": "草莓",
  "message_on_cake": "生日快乐",
  "pickup_time": "明天下午三点",
  "delivery_time": null,
  "delivery_address": null,
  "budget_max": 200,
  "notes": null,
  "extra_requirements": {},
  "missing_fields": [],
  "reply": "收到订单需求"
}
```

允许的 `intent`：

- `create_order`
- `provide_requirement`
- `update_requirement`
- `confirm_order`
- `cancel_order`
- `unknown`

本地业务层会根据字段重新检查缺失项，因此 Dify 的 `missing_fields` 只作为参考。

## 提示词

```text
你是面向小微商户的企业微信订单接待助手。

当前场景：蛋糕店订单确认。

分析客户消息，只输出一个 JSON 对象。
不要输出 Markdown 代码块。
不要输出解释文字。
不要输出多个 JSON 对象。

允许的 intent：
- create_order：客户准备下单或描述订单
- provide_requirement：补充商品、数量、尺寸、口味、时间、地址等
- update_requirement：修改已有要求
- confirm_order：确认下单
- cancel_order：取消订单
- unknown：无法判断

字段规则：
- scenario 固定优先返回 cake
- quantity 必须是整数
- budget_max 必须是整数
- 没有提供的字段使用 null
- extra_requirements 使用对象
- missing_fields 使用数组

输出字段：
{
  "intent": "create_order",
  "scenario": "cake",
  "order_title": "蛋糕订单",
  "customer_name": null,
  "phone": null,
  "product_name": "蛋糕",
  "quantity": 1,
  "size": "8寸",
  "flavor": "草莓",
  "message_on_cake": "生日快乐",
  "pickup_time": "明天下午三点",
  "delivery_time": null,
  "delivery_address": null,
  "budget_max": 200,
  "notes": null,
  "extra_requirements": {},
  "missing_fields": [],
  "reply": "收到订单需求"
}

客户消息：
{{content}}
```

## 推荐测试输入

```text
我想订一个8寸草莓蛋糕，明天下午三点取，预算200，写着生日快乐
```

```text
把口味改成巧克力
```

```text
确认下单
```

```text
取消订单
```

## 评测

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_order_dify_cases.py
```

脚本会打印实际运行模式和客户端类型。真实 Dify 成功时应显示：

```text
Client: HttpDifyClient
```

当前订单评测集包含 7 条用例，覆盖完整订单、缺字段追问、补充时间、修改口味、确认、取消和 unknown。
