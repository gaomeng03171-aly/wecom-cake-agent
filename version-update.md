本文件用于记录每次修改&更新后的不同，以便定位bug或者后续优化。同时列出原项目和最终项目的架构对比。

# Version Update

## 0.22 - 2026-10-03

### 版本说明

本版本进入企业微信真实环境联调，按小步骤推进，先强化回调接收边界，避免真实消息格式导致接口报错和被企微重试。

### 当前完成内容

1. 回调消息兼容事件与非文本类型
   - 企业微信回调中的 event 消息直接确认，不进入 Dify
   - 图片、语音等非文本消息直接确认，不进入业务状态机
   - 只有 text 消息继续走消息幂等、Dify 和聚餐流程

2. 增加自建应用发送调试脚本
   - token：获取并脱敏显示 access_token
   - send：向群聊或单聊发送测试消息
   - 群聊 target 使用 chat_id
   - 单聊 target 使用 direct-{user_id}

3. 增加公网 HTTPS 隧道启动脚本
   - 优先使用 cloudflared
   - 其次使用 ngrok
   - 用于本地真实回调联调

### 本次主要变化

- 修改 services/wecom_callback.py
- 修改 api/wecom_callback.py
- 修改 clients/wecom.py
- 新增 scripts/debug_wecom_sender.py
- 新增 scripts/start_wecom_tunnel.ps1
- 扩展 tests/test_wecom_callback.py

### 后续计划

1. 完善自建应用发送调试与状态检查
2. 增加公网 HTTPS 隧道联调脚本
3. 使用真实企业微信环境完成端到端联调
4. 记录真实联调结果

## 0.2 - 2026-09-28

### 版本说明

这是重新从零搭建的第二版，因此版本号从 0.2 开始记录。项目定位为企业微信群聊聚餐组织 Agent，目标是学习 Agent 项目开发，同时保留企业项目的工程边界。

### 当前完成内容

1. 初始化项目骨架
   - 创建 Git 仓库并配置 GitHub 远端
   - 添加 README、.gitignore、.env.example

2. FastAPI 基础服务
   - 使用 FastAPI 创建应用入口
   - 增加 /health 健康检查
   - 使用 pydantic-settings 管理环境配置
   - 使用 pytest 添加基础测试

3. Mock 企业微信消息接入
   - 增加 POST /wecom/messages 消息接收接口
   - 定义企微消息请求和响应结构
   - 使用 SQLAlchemy 将消息持久化到 SQLite
   - 按 wecom_msg_id 实现消息幂等去重
   - 对并发写入导致的唯一约束冲突做回滚处理

### 当前技术栈

- Python 3.14
- FastAPI
- Pydantic v2
- pydantic-settings
- SQLAlchemy 2
- SQLite
- pytest
- uvicorn

### 当前架构

```text
HTTP 请求
  -> API 路由层
  -> Pydantic 校验层
  -> Service 业务层
  -> SQLAlchemy Model 层
  -> SQLite 数据库
```

```text
src/app/
├── main.py
├── config.py
├── db.py
├── models.py
├── api/
│   └── wecom.py
├── schemas/
│   └── wecom.py
└── services/
    └── inbound.py
```

### 当前请求链路

```text
POST /wecom/messages
  -> schemas/wecom.py 校验请求
  -> services/inbound.py 查询 wecom_msg_id
  -> 不存在则写入 inbound_messages
  -> 已存在则返回 duplicate=true
```

### 关键设计决策

- 当前使用 SQLite 和单进程服务，适合本地开发与 mock 演示。
- 后续进入 Outbox、真实企微接入或并发写入阶段时，再切换到 PostgreSQL。
- Dify 负责意图识别、信息抽取和方案生成，FastAPI 负责状态机和数据持久化。
- 当前只做一个垂直场景：单群、单活动、文本消息的聚餐组织。
- 原项目 wecom-mind 仅作为工程边界和模块设计的参考答案，不直接复制。

### 原项目与最终项目架构对比

| 模块 | wecom-mind 原项目 | 本项目的预期最终版本 |
| --- | --- | --- |
| 消息入口 | 企微长连接 + MCP 历史补漏 | 企微官方回调或长连接 + mock 适配器 |
| 消息处理 | 标准化、幂等、任务触发 | 标准化、幂等、意图路由、活动状态机 |
| 数据库 | SQLAlchemy 业务数据库 | PostgreSQL + SQLAlchemy 2 + Alembic |
| Agent 编排 | Dify 知识问答与分析 | Dify Workflow，支持真实和 mock 模式 |
| 输出校验 | Pydantic 校验 Dify 返回结果 | Pydantic Schema + 领域状态校验 |
| 发送链路 | Outbox + 发送状态与回执 | Outbox + pending/sent/failed + 重试 |
| 会话记忆 | 会话切分、用户画像 | 活动上下文 + 参与者偏好缓存 |
| 管理后台 | React 管理后台 | React + TypeScript + Ant Design |

### 后续计划

1. 增加 Dify mock 适配层
2. 校验 Dify 返回的结构化 JSON
3. 实现聚餐活动状态机
4. 增加参与者偏好和候选方案
5. 实现投票和最终方案确认
6. 增加 Outbox 发送链路
7. 增加活动提醒
8. 增加简单的管理查询或后台

## 0.3 - 2026-09-28

### 当前完成内容

1. 增加 Dify 客户端边界
   - 定义 DifyClient 抽象接口
   - 实现 MockDifyClient
   - 根据配置选择 mock 或真实客户端

2. 增加 Dify 结构化输出
   - 定义 DifyWorkflowResult
   - 定义 DinnerDifyOutput
   - 对 Dify 返回结果进行 Pydantic 校验

3. 接入消息处理流程
   - 消息首次入库后调用 Dify 分析
   - 重复消息不重复调用 Dify
   - Dify 解析失败时返回 dify_error

### 本次主要变化

- API 响应增加 analysis 和 dify_error 字段
- 新增 clients/dify.py
- 新增 schemas/dify.py
- 新增 services/dify.py
- 新增 services/processing.py

### 当前请求链路

```text
POST /wecom/messages
  -> 幂等入库
  -> 首次消息调用 Dify mock
  -> Pydantic 校验 Dify 输出
  -> 返回 analysis 或 dify_error
```

### 后续计划

1. 实现真实 Dify HTTP 客户端
2. 实现聚餐活动状态机
3. 增加参与者偏好和候选方案
4. 实现投票和最终方案确认

## 0.4 - 2026-09-28

### 当前完成内容

1. 增加聚餐活动模型
   - 新增 DinnerActivity 数据表
   - 记录群组、发起人、标题、状态、时间等信息
   - 支持 updated_at 自动更新

2. 增加活动状态机
   - collecting -> proposing -> voting -> confirmed -> completed
   - 支持取消状态
   - 非法状态流转返回 409

3. 接入消息创建活动
   - create_dinner 识别结果会创建活动
   - 同一群组只保留一个进行中的活动
   - 消息响应增加 activity 字段

4. 增加活动接口
   - GET /activities/{group_id}/active
   - POST /activities/{activity_id}/transition

### 本次主要变化

- 新增 models.DinnerActivity
- 新增 schemas/activity.py
- 新增 services/activities.py
- 新增 api/activities.py
- 消息处理流程增加活动创建

### 后续计划

1. 增加参与者模型和加入退出功能
2. 收集参与者偏好
3. 生成候选方案
4. 实现投票与最终方案确认
5. 增加 Outbox 发送链路

## 0.5 - 2026-09-28

### 当前完成内容

1. 增加参与者模型
   - 新增 ActivityParticipant 数据表
   - 同一活动内用户唯一
   - 支持加入时间和退出时间

2. 活动创建时自动加入发起人
   - 发起人作为首个参与者写入
   - 活动与参与者保持关联

3. 增加参与者接口
   - POST /activities/{activity_id}/participants
   - GET /activities/{activity_id}/participants
   - PUT /activities/{activity_id}/participants/{user_id}
   - POST /activities/{activity_id}/participants/{user_id}/leave

4. 支持参与者偏好
   - 可记录可参加时间
   - 可记录口味偏好
   - 可记录预算上限
   - 可记录备注

### 本次主要变化

- 新增 models.ActivityParticipant
- 新增 services/participants.py
- 新增 api/participants.py
- 活动创建逻辑增加发起人写入

### 后续计划

1. 从自然语言消息中自动抽取参与者偏好
2. 生成候选方案
3. 实现投票与最终方案确认
4. 增加 Outbox 发送链路
5. 增加活动提醒

## 0.6 - 2026-09-29

### 当前完成内容

1. 扩展 Dify mock 意图识别
   - 支持 create_dinner
   - 支持 provide_preference
   - 支持 unknown

2. 增加自然语言偏好抽取
   - 抽取可参加时间
   - 抽取口味偏好
   - 抽取预算上限
   - 抽取忌口备注

3. 偏好自动更新参与者
   - 有活动进行中时，按 sender_id 更新对应参与者
   - 参与者不存在时自动加入
   - 消息响应增加 participant 字段

### 本次主要变化

- 扩展 clients/dify.py
- 扩展 schemas/dify.py
- 新增 services/participants.apply_preferences_from_message
- 消息处理流程增加偏好分支

### 后续计划

1. 生成候选方案
2. 实现投票与最终方案确认
3. 增加 Outbox 发送链路
4. 增加活动提醒
5. 增加真实 Dify HTTP 客户端

## 0.7 - 2026-09-29

### 当前完成内容

1. 增加候选方案模型
   - 新增 DinnerProposal 数据表
   - 根据参与者时间、口味和预算生成方案
   - 默认生成三个候选方案

2. 增加投票模型
   - 新增 Vote 数据表
   - 同一用户在同一活动内只能保留一条投票
   - 重复投票会更新原选择

3. 扩展 Dify mock
   - 支持 generate_proposals
   - 支持 vote
   - 支持从“我选 2”中抽取方案编号

4. 增加方案与投票接口
   - POST /activities/{activity_id}/generate-proposals
   - GET /activities/{activity_id}/proposals
   - POST /activities/{activity_id}/start-voting
   - POST /activities/{activity_id}/votes
   - POST /activities/{activity_id}/confirm

5. 接入自然语言流程
   - “生成方案”自动生成候选方案
   - “我选 1”自动记录投票
   - 确认接口根据票数选择最终方案

### 本次主要变化

- 新增 models.DinnerProposal
- 新增 models.Vote
- 新增 services/proposals.py
- 新增 api/proposals.py
- 扩展 Dify mock 和消息处理流程

### 后续计划

1. 增加 Outbox 发送与回复
2. 增加活动提醒
3. 增加真实 Dify HTTP 客户端
4. 增加管理查询或后台
5. PostgreSQL + Alembic + Docker Compose

## 0.8 - 2026-09-30

### 当前完成内容

1. 增加 Outbox 模型
   - 新增 OutboxMessage 数据表
   - 支持 pending、sent、failed 状态
   - 记录重试次数、错误信息、发送时间和 provider 消息 ID

2. 增加企微发送客户端
   - 定义 WeComSender 抽象接口
   - 实现 MockWeComSender
   - 根据 wecom_sender_mode 选择发送客户端

3. 接入机器人回复
   - 消息处理成功后自动创建 Outbox 记录
   - 重复消息不会重复创建回复
   - 业务错误会回复固定提示

4. 增加 Outbox 管理接口
   - POST /outbox
   - GET /outbox
   - POST /outbox/{message_id}/dispatch
   - POST /outbox/dispatch-pending
   - POST /outbox/{message_id}/retry

### 本次主要变化

- 新增 models.OutboxMessage
- 新增 clients/wecom.py
- 新增 services/outbox.py
- 新增 api/outbox.py
- 消息响应增加 outbox 字段

### 后续计划

1. 增加活动提醒
2. 增加真实企微发送客户端
3. 增加真实 Dify HTTP 客户端
4. 增加管理查询或后台
5. PostgreSQL + Alembic + Docker Compose

## 0.9 - 2026-09-30

### 当前完成内容

1. 增加提醒模型
   - 新增 Reminder 数据表
   - 支持 pending、sent、failed、cancelled 状态
   - 记录提醒类型、计划时间、发送时间和错误

2. 增加 APScheduler 调度器
   - 开发环境按固定间隔扫描到期提醒
   - 测试环境不启动后台线程
   - 应用退出时停止调度器

3. 提醒通过 Outbox 发送
   - 到期提醒创建 Outbox 记录
   - 复用发送、失败和重试机制
   - 提醒发送结果回写 Reminder

4. 增加默认提醒计划
   - 投票截止前提醒
   - 活动开始前提醒

5. 增加提醒接口
   - POST /activities/{activity_id}/reminders
   - GET /activities/{activity_id}/reminders
   - POST /activities/{activity_id}/schedule-reminders
   - POST /reminders/dispatch-due
   - POST /reminders/{reminder_id}/cancel

### 本次主要变化

- 新增 models.Reminder
- 新增 services/reminders.py
- 新增 scheduler.py
- 新增 api/reminders.py
- 配置增加 reminder_scheduler_enabled 和 reminder_poll_seconds

### 后续计划

1. 增加真实 Dify HTTP 客户端
2. 增加真实企微发送客户端
3. 增加管理查询或后台
4. PostgreSQL + Alembic + Docker Compose

## 0.10 - 2026-09-30

### 当前完成内容

1. 增加真实 Dify 客户端
   - 实现 HttpDifyClient
   - 调用 Dify Workflow blocking API
   - 解析 data.outputs

2. 增加客户端模式切换
   - mock 模式继续使用 MockDifyClient
   - real 或 http 模式使用 HttpDifyClient
   - 缺少 API 地址或 Key 时给出明确错误

3. 增加配置项
   - DIFY_USER
   - DIFY_TIMEOUT_SECONDS

4. 增加 HTTP 客户端测试
   - 成功返回结构化 outputs
   - HTTP 失败时返回错误结果

### 本次主要变化

- 扩展 clients/dify.py
- 扩展 config.py 和 .env.example
- 新增 tests/test_dify_http.py
- README 增加真实 Dify 接入说明

### 后续计划

1. 增加真实企微发送客户端
2. 增加管理查询或后台
3. PostgreSQL + Alembic + Docker Compose
4. 增加端到端演示脚本

## 0.11 - 2026-09-30

### 当前完成内容

1. 增加企业微信 Webhook 发送客户端
   - 实现 WebhookWeComSender
   - 发送 text 类型群消息
   - 解析企业微信 errcode 和 errmsg

2. 增加发送模式切换
   - mock 模式使用 MockWeComSender
   - webhook 或 real 模式使用 WebhookWeComSender
   - 缺少 Webhook URL 时给出明确错误

3. 增加配置项
   - WECOM_WEBHOOK_URL
   - WECOM_SENDER_TIMEOUT_SECONDS

4. 增加 Webhook 测试
   - 校验 POST 请求体和地址
   - 校验企业微信错误码处理

### 本次主要变化

- 扩展 clients/wecom.py
- 扩展 config.py 和 .env.example
- 新增 tests/test_wecom_webhook.py
- README 增加企业微信发送接入说明

### 后续计划

1. 增加管理查询或后台
2. PostgreSQL + Alembic + Docker Compose
3. 增加端到端演示脚本
4. 接入企业微信智能机器人或自建应用回调

## 0.12 - 2026-09-30

### 当前完成内容

1. 增加管理总览
   - 活动总数和进行中活动数
   - 消息、参与者、方案和投票数量
   - Outbox 和提醒状态数量

2. 增加活动详情聚合
   - 活动基本信息
   - 参与者和偏好
   - 候选方案和投票
   - Outbox 消息
   - 提醒计划

3. 增加消息查询
   - 按群组过滤
   - 支持分页

4. 增加管理鉴权
   - 默认本地开放
   - 配置 ADMIN_API_KEY 后要求 X-Admin-Key

5. 增加管理接口
   - GET /admin/overview
   - GET /admin/activities
   - GET /admin/activities/{activity_id}
   - GET /admin/messages

### 本次主要变化

- 新增 services/admin.py
- 新增 api/admin.py
- 扩展 Outbox 查询支持 activity_id
- 配置增加 admin_api_key

### 后续计划

1. PostgreSQL + Alembic + Docker Compose
2. 增加端到端演示脚本
3. 接入企业微信智能机器人或自建应用回调
4. 增加简单管理前端

## 0.13 - 2026-09-30

### 当前完成内容

1. 接入 PostgreSQL
   - 增加 psycopg 驱动
   - 支持 postgresql+psycopg 连接串
   - 本地仍默认使用 SQLite

2. 接入 Alembic
   - 增加 alembic.ini
   - 增加 migrations/env.py
   - 生成初始数据库迁移
   - 验证 alembic upgrade head 可独立建表

3. 增加数据库初始化开关
   - AUTO_CREATE_TABLES=true 时保持本地自动建表
   - 容器环境设置为 false，由 Alembic 管理结构

4. 增加 Docker 部署
   - Dockerfile
   - docker-compose.yml
   - PostgreSQL healthcheck
   - 应用启动前执行数据库迁移
   - .dockerignore

### 本次主要变化

- pyproject.toml 增加 alembic 和 psycopg
- 新增 migrations 目录和初始迁移
- 新增 Dockerfile 和 docker-compose.yml
- README 增加数据库迁移和 Docker 使用说明

### 后续计划

1. 增加端到端演示脚本
2. 接入企业微信智能机器人或自建应用回调
3. 增加简单管理前端
4. 增加部署配置示例和运行文档

## 0.14 - 2026-09-30

### 当前完成内容

1. 增加端到端演示脚本
   - 健康检查
   - 创建活动
   - 收集偏好
   - 生成方案
   - 开始投票
   - 成员投票
   - 确认最终方案
   - 创建并发送提醒
   - 查询管理详情

2. 修复投票序号映射
   - “我选 1”不再直接当作全局 proposal_id
   - 按当前活动的方案顺序映射真实 proposal_id
   - 增加历史数据场景测试

3. 增加演示输出
   - 打印候选方案
   - 打印最终方案
   - 打印 Outbox 状态
   - 打印提醒状态

### 本次主要变化

- 新增 scripts/demo_dinner_flow.py
- 扩展 tests/test_proposals.py
- README 增加端到端演示说明

### 后续计划

1. 接入企业微信智能机器人或自建应用回调
2. 增加简单管理前端
3. 增加部署配置示例和运行文档
4. 增加真实环境联调检查清单

## 0.15 - 2026-09-30

### 当前完成内容

1. 增加企业微信回调加密模块
   - SHA1 签名校验
   - AES-256-CBC 解密
   - AES-256-CBC 加密
   - EncodingAESKey 和 corp_id 校验

2. 增加企业微信回调接口
   - GET /wecom/callback 验证 URL
   - POST /wecom/callback 接收消息
   - 解析 text 消息 XML
   - 复用现有消息处理和 Outbox 链路

3. 增加回调配置
   - WECOM_CORP_ID
   - WECOM_CALLBACK_TOKEN
   - WECOM_ENCODING_AES_KEY

4. 增加回调测试
   - 加解密往返测试
   - URL 验证测试
   - 加密消息创建活动测试

### 本次主要变化

- 新增 clients/wecom_crypto.py
- 新增 services/wecom_callback.py
- 新增 api/wecom_callback.py
- 新增 tests/test_wecom_callback.py
- 依赖增加 cryptography

### 当前边界

- 回调接收已实现，群机器人 Webhook 发送已实现。
- 自建应用回调后的应用消息发送仍需后续实现。
- 回调地址需要公网可访问的 HTTPS 地址。

### 后续计划

1. 增加自建应用消息发送客户端
2. 增加简单管理前端
3. 增加真实环境联调检查清单
4. 增加生产部署和反向代理说明

## 0.16 - 2026-09-30

### 当前完成内容

1. 增加企业微信自建应用发送客户端
   - 获取并缓存 access_token
   - appchat/send 发送群聊消息
   - message/send 发送单聊消息
   - 解析 errcode、errmsg 和 msgid

2. 增加发送模式
   - mock
   - webhook
   - app 或 real

3. 增加应用发送配置
   - WECOM_API_BASE
   - WECOM_CORP_ID
   - WECOM_AGENT_ID
   - WECOM_APP_SECRET
   - WECOM_SENDER_TIMEOUT_SECONDS

4. 增加应用发送测试
   - 群聊 appchat/send
   - 单聊 message/send
   - access_token 错误处理

### 本次主要变化

- 扩展 clients/wecom.py
- 扩展 config.py、.env.example 和 docker-compose.yml
- 新增 tests/test_wecom_app.py
- README 增加自建应用发送说明

### 后续计划

1. 增加简单管理前端
2. 增加真实环境联调检查清单
3. 增加生产部署和反向代理说明
4. 增加本地回调调试工具

## 0.17 - 2026-09-30

### 当前完成内容

1. 增加联调状态接口
   - GET /admin/integration-status
   - 检查企微发送配置
   - 检查企微回调配置
   - 检查 Dify 配置
   - 返回数据库类型
   - 不返回任何密钥内容

2. 增加回调调试脚本
   - roundtrip：本地加解密验证
   - verify：模拟企业微信 URL 验证
   - post：模拟加密消息回调
   - 支持 --base-url、--content、--group-id 等参数

3. 增加联调检查清单
   - 企业微信后台所需配置
   - 本地回调验证步骤
   - 常见错误排查
   - 安全检查

### 本次主要变化

- 新增 services/integration_status.py
- 扩展 api/admin.py
- 新增 scripts/debug_wecom_callback.py
- 新增 docs/wecom-integration-checklist.md

### 后续计划

1. 增加简单管理前端
2. 增加生产部署和反向代理说明
3. 增加真实环境联调执行记录
4. 增加回调消息幂等和重放保护说明

## 0.18 - 2026-09-30

### 当前完成内容

1. 增加 React 管理前端
   - React + TypeScript + Vite
   - Lucide 图标
   - 响应式管理台布局

2. 增加总览页面
   - 活动、消息、参与者、方案和投票统计
   - Outbox 和提醒状态统计

3. 增加活动页面
   - 按群组和状态筛选
   - 活动详情聚合
   - 参与者偏好、候选方案、投票、Outbox 和提醒

4. 增加消息和联调状态页面
   - 查看入站消息
   - 查看企微发送、回调、Dify 和数据库状态
   - 支持配置浏览器会话级管理密钥

### 本次主要变化

- 新增 apps/admin-web
- 增加 Vite 到 FastAPI 的 /api 代理
- README 增加前端启动说明
- 前端生产构建验证通过

### 后续计划

1. 增加生产部署和反向代理说明
2. 增加真实环境联调执行记录
3. 增加前端 API Key 失效提示和自动刷新
4. 增加活动操作按钮和确认流程

## 0.19 - 2026-10-01

### 当前完成内容

1. 改进事务 Outbox
   - 关键业务写入支持暂不提交
   - 业务数据和 Outbox 在同一事务中提交
   - 提交成功后再执行网络发送
   - 发送失败保留 Outbox 状态用于重试

2. 增加回调时间窗口
   - 校验回调 timestamp
   - 超过允许时间窗口返回 400
   - 新增 WECOM_CALLBACK_MAX_AGE_SECONDS

3. 增加提醒防重复派发
   - 增加 processing 中间状态
   - 使用条件更新原子认领提醒
   - 已被其他调度器认领的提醒不会重复发送

4. 增加请求 ID
   - 每个 HTTP 响应返回 X-Request-ID
   - 为后续日志追踪提供统一标识

5. 增加可靠性测试
   - 重复消息不创建重复 Outbox
   - 提醒只派发一次
   - 过期回调时间戳被拒绝

### 本次主要变化

- 修改 services/processing.py 和关键业务服务
- 修改 services/reminders.py
- 修改 api/wecom_callback.py
- 修改 main.py
- 扩展可靠性测试

### 后续计划

1. 增加真实 Dify Workflow DSL 和质量评估
2. 增加生产部署和反向代理说明
3. 增加真实环境联调执行记录
4. 增加管理台写入操作

## 0.20 - 2026-10-02

### 当前完成内容

1. 增加 Dify Workflow 测试集
   - 14 条固定输入
   - 覆盖 create_dinner
   - 覆盖 provide_preference
   - 覆盖 generate_proposals
   - 覆盖 vote
   - 覆盖 unknown

2. 增加真实 Dify 评测脚本
   - 支持完整运行
   - 支持 --only 单条运行
   - 支持 --fail-fast
   - 比较核心结构化字段
   - 校验 reply 关键词

3. 完成云 Dify 联调
   - 真实模式配置验证通过
   - 投票多 JSON 解析问题已修复
   - 饮食限制与口味字段区分已修复
   - missing_fields 时间字段规则已修复
   - 最终 14/14 全部通过

### 本次主要变化

- 新增 docs/dify-workflow-test-cases.json
- 新增 scripts/evaluate_dify_cases.py
- README 增加 Dify 评测说明

### 后续计划

1. 生产部署：前端容器、Nginx、HTTPS 和反向代理
2. 真实企业微信联调
3. 管理台写入操作
4. 增加监控和日志收集

## 0.21 - 2026-10-02

### 当前完成内容

1. 增加管理前端生产镜像
   - 多阶段 Node 构建
   - Nginx 静态服务
   - 排除 node_modules 和 dist

2. 增加 Nginx 反向代理
   - /api/ 转发到 FastAPI
   - /wecom/ 转发到 FastAPI
   - /health 转发到 FastAPI
   - 静态资源缓存
   - gzip 压缩

3. 增加 HTTPS 部署
   - TLS 证书挂载
   - HTTP 到 HTTPS 跳转
   - docker-compose.https.yml

4. 增加部署配置
   - APP_DOMAIN
   - TLS_CERT_PATH
   - TLS_KEY_PATH
   - deploy/nginx/README.md

### 本次主要变化

- 新增 apps/admin-web/Dockerfile
- 新增 deploy/nginx/default.conf.template
- 新增 deploy/nginx/https.conf.template
- 新增 docker-compose.https.yml
- 更新 docker-compose.yml

### 后续计划

1. 企业微信真实环境联调
2. 管理台写入操作
3. 增加监控和日志收集
4. 增加生产环境启动检查脚本
