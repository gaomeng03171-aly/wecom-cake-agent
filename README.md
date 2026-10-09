# WeCom Cake Agent

面向小微烘焙商户的企业微信订单接待 Agent。

项目通过企业微信智能机器人接待客户，使用 Dify 完成自然语言意图识别和字段抽取，
由 FastAPI 管理订单状态、报价、定金和履约流程，并提供 React 管理台供店主处理订单。
项目内置 mock 模式，可以在没有企业微信或 Dify 账号的情况下完成本地开发和演示。

## 主要能力

- 企业微信群聊、单聊消息接入
- 客户自然语言下单和字段追问
- 客户资料、商品、尺寸、口味、时间、地址和备注收集
- 店主报价、接受客户预期价、客户确认或拒绝报价
- 报价历史、客户反馈和重新报价
- 订单定金计算和线下收款确认
- 订单制作、可取货、已完成等履约状态
- 四位营业日订单号，例如 `10.09-0001`
- 取消订单后恢复、修改和店主留言
- 菜单咨询、无意义商品和无意义配送拦截
- Outbox 可靠发送和失败重试
- React 管理台今日工作台、订单列表、订单详情、月历和操作面板
- SQLite 本地开发与 PostgreSQL 生产部署
- Docker Compose、Alembic 和 Nginx 部署支持

## 适用场景

当前首先面向蛋糕和烘焙类商户，但订单模型使用通用的 `scenario` 和
`requirements` 结构，可以继续扩展到花店、维修店、打印店等订单确认场景。

典型业务流程：

```text
客户咨询或下单
  -> Bot 收集订单字段
  -> 客户确认订单信息
  -> 店主报价
  -> 客户确认报价
  -> 按规则收取定金
  -> 店主制作并确认可取货
  -> 客户取货，订单完成
```

## 技术架构

```text
企业微信智能机器人 / 自建应用 / 回调
                  |
                  v
              FastAPI
                  |
        +---------+----------+
        |                    |
        v                    v
      Dify              业务服务层
  意图与字段抽取      订单、报价、定金、履约
        |                    |
        +---------+----------+
                  |
                  v
       SQLAlchemy + Alembic
                  |
                  v
              PostgreSQL
                  |
                  v
              Outbox
      客户回复 / 店主通知 / 重试

React 管理台
  -> 今日工作台
  -> 订单详情与操作
  -> 月历和订单筛选
```

技术栈：

| 模块 | 技术 |
| --- | --- |
| 后端 API | FastAPI、Pydantic |
| 业务持久化 | SQLAlchemy、Alembic |
| 数据库 | SQLite、PostgreSQL |
| Agent 工作流 | Dify Workflow，支持 mock 和 HTTP 模式 |
| 企业微信接入 | 智能机器人长连接、自建应用 API、Webhook、官方回调 |
| 异步发送 | 事务 Outbox、失败重试 |
| 管理台 | React、TypeScript、Vite、Lucide |
| 部署 | Docker Compose、Nginx、HTTP/HTTPS |

## 订单状态

```text
collecting
  -> pending_confirmation
  -> confirmed
  -> preparing
  -> ready
  -> completed
```

订单可以被取消。取消后支持店主留言，也支持客户按订单号恢复订单或重新打开修改。

报价状态独立于履约状态：

```text
pending_owner
pending_customer
approved
rejected
superseded
```

定金规则：

```text
取货日期距离下单日期超过 5 个自然日
且最终确认报价 > 200 元
定金 = 最终报价 x 20%
```

金额使用 `Decimal`，不强制取整。

## 环境要求

- Python 3.11+
- Node.js 20+
- Docker Desktop
- 可选：Dify 账号和企业微信企业账号

## 本地启动

### 1. 创建 Python 环境

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

### 2. 准备配置

```powershell
Copy-Item .env.example .env
```

本地默认使用 SQLite、mock Dify 和 mock 企业微信发送器，可以直接启动。

### 3. 启动后端

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir src --reload
```

健康检查：

```text
http://127.0.0.1:8000/health
```

### 4. 启动管理台

```powershell
cd apps/admin-web
npm install
npm run dev
```

管理台地址：

```text
http://127.0.0.1:5173
```

如果配置了 `ADMIN_API_KEY`，在管理台左侧输入管理密钥。密钥只保存在浏览器
`sessionStorage`。

## Docker 部署

HTTP 模式：

```powershell
docker compose up --build
```

服务地址：

```text
后端 API: http://localhost:8000
管理台:   http://localhost:8080
```

启用企业微信智能机器人长连接 worker：

```powershell
docker compose --profile aibot up -d --build aibot-worker
```

HTTPS 模式：

```powershell
$env:APP_DOMAIN = "your-domain.example"
$env:TLS_CERT_PATH = "./certs/fullchain.pem"
$env:TLS_KEY_PATH = "./certs/privkey.pem"
docker compose -f docker-compose.yml -f docker-compose.https.yml up --build
```

如果重新创建了 `app` 容器，建议同时重建 `web`，让 Nginx 重新解析后端地址：

```powershell
docker compose up -d --force-recreate app web
```

## 企业微信接入

项目支持以下发送和接收方式：

- 企业微信智能机器人长连接
- 自建应用消息发送
- 群机器人 Webhook
- 企业微信官方回调

订单通知通道：

```text
ORDER_NOTIFICATION_CHANNEL=auto
```

可选值：

| 值 | 说明 |
| --- | --- |
| `auto` | 优先自建应用，其次 Webhook，最后智能机器人主动发送 |
| `app` | 使用自建应用 `message/send` |
| `webhook` | 使用群机器人 Webhook |
| `active` | 使用智能机器人主动 `send_message` |

智能机器人长连接配置：

```text
WECOM_AIBOT_ID=your-aibot-id
WECOM_AIBOT_SECRET=your-aibot-secret
WECOM_AIBOT_NAME=your-aibot-name
WECOM_AIBOT_REQUIRE_MENTION=true
WECOM_OWNER_USER_ID=owner-userid
```

更多说明：

- [智能机器人长连接](docs/wecom-aibot-long-connection.md)
- [企业微信联调检查清单](docs/wecom-integration-checklist.md)

## Dify Workflow

订单场景默认使用：

```text
ORDER_DIFY_MODE=auto
```

模式说明：

| 模式 | 说明 |
| --- | --- |
| `mock` | 使用本地规则解析，适合开发和测试 |
| `auto` | 优先订单专用 API Key，否则复用通用 Dify Key |
| `real` | 使用订单专用 Dify Workflow |

订单 Workflow 的输入、输出字段和提示词见：

[订单 Dify Workflow](docs/order-dify-workflow.md)

运行订单评测：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_order_dify_cases.py
```

## 管理台

管理台当前包含：

- 今日工作台：待店主报价、待客户确认价格、待收定金、制作中、可取货、今日完成
- 订单列表和订单详情
- 报价输入、接受预期价、已收定金、已做好、已取货
- 报价历史和确认记录
- 取消订单留言
- 订单月历
- 入站消息查看
- 企业微信、Dify、数据库联调状态

## 管理 API

如果设置了 `ADMIN_API_KEY`，请求需要携带：

```text
X-Admin-Key: your-admin-key
```

主要接口：

```text
GET  /admin/overview
GET  /admin/orders
GET  /admin/orders/{order_id}
POST /admin/orders/{order_id}/quote
POST /admin/orders/{order_id}/deposit-paid
POST /admin/orders/{order_id}/ready
POST /admin/orders/{order_id}/completed
POST /admin/orders/{order_id}/message
GET  /admin/messages
GET  /admin/integration-status
```

## 数据库迁移

本地 SQLite 可以使用：

```text
AUTO_CREATE_TABLES=true
```

生产环境建议使用 Alembic：

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
```

PostgreSQL 示例：

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@db:5432/wecom_cake
AUTO_CREATE_TABLES=false
```

## 测试

后端测试：

```powershell
.\.venv\Scripts\python.exe -m pytest
```

前端类型检查和生产构建：

```powershell
cd apps/admin-web
npm run build
```

订单 Dify mock 评测：

```powershell
.\.venv\Scripts\python.exe scripts\evaluate_order_dify_cases.py
```

## 维护脚本

回填有明确取货日期但缺少 `scheduled_at` 的历史订单：

```powershell
docker exec wecom-cake-agent-app-1 python scripts/backfill_scheduled_at.py
docker exec wecom-cake-agent-app-1 python scripts/backfill_scheduled_at.py --execute
```

清理旧业务和不完整订单：

```powershell
docker exec wecom-cake-agent-app-1 python scripts/cleanup_legacy_data.py
docker exec wecom-cake-agent-app-1 python scripts/cleanup_legacy_data.py --execute
```

两个脚本默认都是 dry-run，只有传入 `--execute` 才会写入数据库。

## 项目结构

```text
apps/admin-web/                  React 管理台
deploy/nginx/                    Nginx 和 HTTPS 配置
docs/                            Dify、企业微信和联调文档
migrations/                      Alembic 迁移
scripts/                         调试、评测、回填和维护脚本
src/app/api/                     FastAPI 路由
src/app/clients/                 Dify、企业微信客户端
src/app/schemas/                 Pydantic 数据结构
src/app/services/                订单、报价、Outbox 和业务服务
tests/                           后端测试
```

## 安全建议

- 不要把 `.env`、企业微信密钥、Dify API Key 或数据库密码提交到仓库
- 生产环境必须设置 `ADMIN_API_KEY`
- 企业微信回调必须使用公开可访问的 HTTPS 地址
- 回调请求使用时间窗口校验，业务消息使用 `wecom_msg_id` 保证幂等
- 生产环境建议使用 PostgreSQL，不要继续使用本地 SQLite

## 参与贡献

1. Fork 仓库并创建功能分支
2. 保持改动范围清晰
3. 为新行为补充测试
4. 提交前运行后端测试和前端构建
5. 提交 Pull Request，并说明行为变化和验证方式

## 许可

当前仓库尚未附带独立许可证文件。对外分发或商用前，请先明确许可证和授权范围。
