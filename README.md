# wecom-cake-agent

当前定位：面向小微商户的企业微信订单接待 Agent，第一个落地场景是蛋糕店订单确认。原聚餐组织流程保留为兼容场景。

## 目标场景

客户通过企业微信描述订单需求，机器人负责收集商品、数量、尺寸、口味、取货时间和备注，字段完整后生成订单确认文本；客户确认后写入订单，并通过 Outbox 通知店主。

订单 Dify 可以先使用本地规则模式；需要真实大模型抽取时，按 [docs/order-dify-workflow.md](docs/order-dify-workflow.md) 配置独立 Workflow。

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

第十三阶段：PostgreSQL、Alembic 和 Docker Compose 已接入，支持正式数据库迁移与容器部署。

第十四阶段：端到端演示脚本已实现，并修复了投票方案序号在历史数据下的映射问题。

第十五阶段：企业微信官方回调入口已实现，支持签名校验、AES 解密、XML 解析和消息处理。

第十六阶段：企业微信自建应用消息发送客户端已实现，群聊和单聊均可通过应用 API 回复。

第十七阶段：联调状态接口和企业微信回调调试工具已实现，并补充完整联调检查清单。

第十八阶段：React + TypeScript + Vite 管理前端已实现，支持总览、活动详情、消息和联调状态查看。

第十九阶段：事务 Outbox、回调时间窗口和提醒防重复派发已实现。

第二十阶段：Dify Workflow 测试集、真实云 Dify 评测脚本和输出契约验证已完成。

第二十一阶段：前端生产镜像、Nginx 反向代理、HTTP 与 HTTPS Compose 部署已实现。

当前 0.23：项目定位调整为面向小微商户的企业微信订单接待 Agent。已完成订单领域模型、Alembic 迁移、订单状态机、蛋糕订单 Dify 意图与字段抽取、订单会话流程、店主 Outbox 通知、企业微信长连接 worker 接入，以及订单列表和详情管理台。

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

## 订单 Agent

默认场景为蛋糕订单确认：

```text
AGENT_SCENARIO=order
WECOM_OWNER_USER_ID=店主的企业微信userid
ORDER_NOTIFICATION_CHANNEL=auto
```

订单字段完整后，机器人会生成确认文本；客户确认后写入 `orders` 和 `order_confirmations`，并创建一条发送给店主的 Outbox 消息。

店主通知通道：

- `auto`：优先自建应用 API，其次群 Webhook，最后智能机器人主动单聊
- `app`：自建应用 `message/send`
- `webhook`：群机器人 Webhook
- `active`：智能机器人主动 `send_message`

订单 Dify 支持三种模式：

```text
ORDER_DIFY_MODE=auto
```

- `auto`：有 `DIFY_ORDER_API_KEY` 时优先使用，否则复用 `DIFY_API_KEY`
- `mock`：使用本地规则解析，适合无 Dify 开发
- `real`：使用订单专用 Dify 配置

订单 Workflow 的提示词、输出字段和测试输入见 [docs/order-dify-workflow.md](docs/order-dify-workflow.md)。

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

订单场景使用独立的输出契约和评测：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_order_dify_cases.py
```

评测集位于 [docs/order-dify-test-cases.json](docs/order-dify-test-cases.json)。

## 接入企业微信发送

在群机器人设置中获取 Webhook 地址，并配置：

```text
WECOM_SENDER_MODE=webhook
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your-key
WECOM_SENDER_TIMEOUT_SECONDS=10
```

当前实现使用企业微信官方群机器人 Webhook，适合验证消息发送和 Outbox 状态。群机器人 Webhook 只能发送，不能读取群聊消息；完整接收普通群聊消息仍需要企业微信智能机器人长连接或会话内容存档能力。

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
GET /admin/orders
GET /admin/orders/{order_id}
GET /admin/activities
GET /admin/activities/{activity_id}
GET /admin/messages
```

运行测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## 数据库迁移

本地 SQLite 模式仍可使用 `AUTO_CREATE_TABLES=true` 自动建表。需要迁移管理时运行：

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

切换 PostgreSQL 时配置：

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@127.0.0.1:5432/wecom_cake
AUTO_CREATE_TABLES=false
```

## Docker Compose

Compose 会启动 PostgreSQL 和应用，并在应用启动前执行 `alembic upgrade head`：

```powershell
docker compose up --build
```

启用企业微信智能机器人长连接 worker：

```powershell
docker compose --profile aibot up -d --build aibot-worker
```

可在项目根目录的 `.env` 中覆盖 `POSTGRES_DB`、`POSTGRES_USER`、`POSTGRES_PASSWORD` 以及外部服务配置。

## 端到端演示

使用 mock Dify 和 mock 企微发送器，启动服务后运行：

```powershell
.\.venv\Scripts\python.exe scripts\demo_dinner_flow.py
```

脚本会依次执行：

```text
健康检查
创建聚餐活动
收集参与者偏好
生成候选方案
开始投票
成员投票
确认最终方案
创建并发送提醒
查询管理详情
```

## 企业微信回调

企业微信后台的回调地址配置为：

```text
https://your-domain.example/wecom/callback
```

本地 `.env` 需要配置：

```text
WECOM_CORP_ID=your-corp-id
WECOM_CALLBACK_TOKEN=your-callback-token
WECOM_ENCODING_AES_KEY=your-43-character-aes-key
WECOM_CALLBACK_MAX_AGE_SECONDS=300
```

当前回调实现会校验签名、解密消息、解析 text 消息，并复用现有业务处理与 Outbox 链路。

回调请求超过允许时间窗口时会被拒绝，用来降低重放风险；消息本身的幂等仍由 `wecom_msg_id` 保证。

真实部署时回调地址必须是企业微信可访问的 HTTPS 地址。当前已同时实现群机器人 Webhook 和自建应用 API 发送，可通过 `WECOM_SENDER_MODE` 切换。

### 自建应用发送

如果使用自建应用回调，可以将发送模式切换为应用 API：

```text
WECOM_SENDER_MODE=app
WECOM_CORP_ID=your-corp-id
WECOM_AGENT_ID=your-agent-id
WECOM_APP_SECRET=your-app-secret
WECOM_API_BASE=https://qyapi.weixin.qq.com
```

发送器会自动获取并缓存 `access_token`：

```text
普通 chat_id：调用 appchat/send
direct-{user_id}：调用 message/send
```

当前回调解析器会把没有 `ChatId` 的消息标记为 `direct-{sender_id}`，用于单聊回复。

需要注意：自建应用回调可以接收成员发给应用的单聊消息，但普通企业微信群聊消息不会默认推送进来。若要让机器人读取普通群聊消息，需要接入企业微信智能机器人长连接或会话内容存档；现阶段更稳妥的模式是“单聊接收指令 + 群机器人 Webhook 广播结果”。

智能机器人长连接配置和启动方式见 [docs/wecom-aibot-long-connection.md](docs/wecom-aibot-long-connection.md)。

## 联调工具

查询当前配置是否满足企业微信和 Dify 联调要求：

```text
GET /admin/integration-status
```

接口不会返回密钥，只返回当前模式、缺失配置项和数据库类型。

调试企业微信回调：

```powershell
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py roundtrip
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py verify
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py post
```

调试企业微信自建应用发送：

```powershell
.\.venv\Scripts\python.exe scripts\debug_wecom_sender.py token
.\.venv\Scripts\python.exe scripts\debug_wecom_sender.py send --target chat-id
.\.venv\Scripts\python.exe scripts\debug_wecom_sender.py send --target direct-user-id
```

创建应用群聊并发送首条测试消息：

```powershell
.\.venv\Scripts\python.exe scripts\create_wecom_group.py --name "蛋糕订单群" --userids user-a,user-b
```

准备公网 HTTPS 回调地址：

```powershell
.\scripts\start_wecom_tunnel.ps1 -Port 8000
```

脚本会优先使用 `cloudflared`，其次使用 `ngrok`。启动后把打印出来的 HTTPS 地址作为企业微信回调域名，回调路径保持 `/wecom/callback`。

完整步骤和常见错误见 [docs/wecom-integration-checklist.md](docs/wecom-integration-checklist.md)。

## Dify Workflow 评测

真实 Dify 评测：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_dify_cases.py
```

只运行单条用例：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_dify_cases.py --only create_simple
```

测试集位于 [docs/dify-workflow-test-cases.json](docs/dify-workflow-test-cases.json)，当前 14 条用例全部通过。

## 生产部署

HTTP 模式：

```powershell
docker compose up --build
```

管理前端地址：`http://localhost:8080`

HTTPS 模式：

```powershell
$env:APP_DOMAIN = "your-domain.example"
$env:TLS_CERT_PATH = "./certs/fullchain.pem"
$env:TLS_KEY_PATH = "./certs/privkey.pem"
docker compose -f docker-compose.yml -f docker-compose.https.yml up --build
```

Nginx 配置说明见 [deploy/nginx/README.md](deploy/nginx/README.md)。

## 管理前端

先启动后端 `127.0.0.1:8000`，再运行：

```powershell
cd apps/admin-web
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

前端开发服务器会把 `/api` 代理到 FastAPI。若配置了 `ADMIN_API_KEY`，可在左侧输入管理密钥，密钥只保存在浏览器 `sessionStorage`。

## 0.23 已完成范围

1. 订单领域模型、Alembic 迁移和订单状态机
2. `create_order`、`provide_requirement`、`update_requirement`、`confirm_order`、`cancel_order` 意图
3. 订单字段抽取、缺失字段追问和订单确认文本
4. 客户确认后写入订单、保存确认记录并创建店主通知 Outbox
5. 企业微信智能机器人长连接订单模式
6. React 管理台订单列表、详情、状态和确认记录
7. 真实订单 Dify 评测脚本，当前 7/7 用例通过

## 许可

本项目计划使用 MIT License。
