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
