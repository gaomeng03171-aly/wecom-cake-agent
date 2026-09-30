本文件用于记录每次修改&更新后的不同，以便定位bug或者后续优化。同时列出原项目和最终项目的架构对比。

# Version Update

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
