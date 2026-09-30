# wecom-dinner-agent

一个面向企业微信群的聚餐组织 Agent，用来学习和实践 Agent 项目开发。

## 目标场景

群成员在企业微信群里发起约饭，机器人负责收集时间、人数、口味和预算，生成候选方案，组织投票，并在最终方案确认后发送提醒。

## 设计原则

- 消息接入与幂等入库
- Dify 负责意图识别、结构化抽取和方案生成
- FastAPI 负责业务状态机和数据持久化
- 发送结果可追踪、失败可重试
- 支持 mock 模式，便于无外部账号时开发与演示

## 当前状态

第一阶段：FastAPI 项目骨架与健康检查已实现。

第二阶段：mock 企业微信消息入口已实现，支持消息标准化与 `msg_id` 幂等去重。

第三阶段：Dify mock 适配层已实现，消息入库后返回结构化分析结果。

第四阶段：聚餐活动状态机已实现，支持活动创建和合法状态流转。

第五阶段：参与者模型已实现，支持加入、退出和偏好更新。

第六阶段：Dify mock 已支持从自然语言消息中抽取聚餐偏好并自动更新参与者。

第七阶段：候选方案生成、投票和最终方案确认已实现。

第八阶段：Outbox 发送链路已实现，支持 pending、sent、failed 和重试。

第九阶段：活动提醒已实现，支持 APScheduler 调度、投票截止提醒和活动开始提醒。

第十阶段：真实 Dify Workflow HTTP 客户端已实现，可通过环境变量切换 mock 和真实模式。

第十一阶段：企业微信群机器人 Webhook 发送客户端已实现，可通过环境变量切换 mock 和真实发送。

第十二阶段：只读管理查询接口已实现，可查看总览、活动详情、消息、Outbox 和提醒。

## 本地启动

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir src --reload
```

健康检查：`http://127.0.0.1:8000/health`

Mock 企业微信消息接收：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/wecom/messages `
  -ContentType "application/json" `
  -Body '{"msg_id":"wecom-msg-001","group_id":"group-001","group_name":"周末聚餐群","sender_id":"user-001","sender_name":"张三","msg_type":"text","content":"周六晚上一起吃饭吗？"}'
```

## 接入真实 Dify

在 Dify 中创建一个 Workflow 应用，并将 `.env` 配置为：

```text
DIFY_CLIENT_MODE=real
DIFY_API_BASE=https://api.dify.ai/v1
DIFY_API_KEY=your-dify-app-api-key
```

Workflow 的最终输出需要包含以下字段，后端会用 Pydantic 校验：

```text
intent
activity_title
suggested_time
deadline
available_time
cuisine_preference
budget_max
notes
proposal_choice
missing_fields
reply
```

只需要 Dify 应用 API Key 和应用地址，不需要在项目里配置 Dify 登录账号或密码。

## 接入企业微信发送

在群机器人设置中获取 Webhook 地址，并配置：

```text
WECOM_SENDER_MODE=webhook
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key
WECOM_SENDER_TIMEOUT_SECONDS=10
```

当前实现使用企业微信官方群机器人 Webhook，适合验证消息发送和 Outbox 状态。完整接收群消息仍需要后续接入企业微信智能机器人或自建应用回调。

## 管理查询接口

本地开发默认不要求管理密钥。部署到共享环境前，建议设置：

```text
ADMIN_API_KEY=your-admin-key
```

设置后请求需要携带：

```text
X-Admin-Key: your-admin-key
```

可用接口：

```text
GET /admin/overview
GET /admin/activities
GET /admin/activities/{activity_id}
GET /admin/messages
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 计划中的 MVP

1. 初始化 FastAPI 后端与健康检查
2. 接入 mock 企微消息并实现幂等入库
3. 接入 Dify mock 并校验结构化输出
4. 实现聚餐活动状态机
5. 实现候选方案生成与投票
6. 增加活动提醒和管理查询

## 许可

本项目计划使用 MIT License。
