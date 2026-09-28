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
