# 企业微信智能机器人长连接

当前 HTTP 回调适合单聊和事件确认，但不能稳定接收普通群聊消息。要在群里实时接收消息，需要使用企业微信智能机器人长连接。

## 配置

在企业微信管理后台准备智能机器人的：

- `WECOM_AIBOT_ID`
- `WECOM_AIBOT_SECRET`

写入 `.env`：

```text
WECOM_SENDER_MODE=aibot_ws
AGENT_SCENARIO=order
WECOM_AIBOT_ID=your-bot-id
WECOM_AIBOT_SECRET=your-bot-secret
WECOM_AIBOT_WS_URL=
WECOM_AIBOT_NAME=订单助手
WECOM_AIBOT_REQUIRE_MENTION=true
WECOM_OWNER_USER_ID=店主的企业微信userid
```

`WECOM_AIBOT_WS_URL` 留空时使用 SDK 默认地址。

默认只处理 @ 机器人的消息，避免普通群聊讨论触发回复。联调期间需要让机器人处理所有文本时，可以设置为 `false`。

`AGENT_SCENARIO=order` 时，长连接消息进入订单接待流程；设置为 `dinner` 可切回原聚餐流程。

## Docker 启动

重建并启动长连接 worker：

```powershell
docker compose --profile aibot up -d --build aibot-worker
```

查看连接日志：

```powershell
docker compose logs -f aibot-worker
```

停止 worker：

```powershell
docker compose --profile aibot stop aibot-worker
```

worker 通过 WebSocket 接收 `message.text` 和 `message.mixed` 帧，转换成现有消息模型后复用 Dify、订单、活动、投票和 Outbox 流程，并用同一个回调 frame 回复。订单确认后，worker 还会向 `WECOM_OWNER_USER_ID` 对应的店主发送订单通知。

## 本地启动

如果后端也在本机运行，可以直接启动 worker：

```powershell
$env:DATABASE_URL = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/wecom_cake"
.\.venv\Scripts\python.exe scripts\run_wecom_aibot_worker.py
```

注意：本地 worker 和 Docker app 必须连到同一个数据库，否则管理台仍然看不到消息。

## 使用边界

- 一个机器人同一时间只应该有一个长连接 worker，重复连接会被企业微信断开旧连接。
- 群聊入口优先使用长连接；HTTP 回调不要再承担同一群消息的主处理职责。
- 当前先支持文本和图文混排中的文本内容，图片、语音和文件暂时忽略。
- 长连接回复依赖原始 frame 的 `req_id`，不要只保存消息文本而丢掉原始 frame。

## 排查

### Authentication failed

检查 `WECOM_AIBOT_ID` 和 `WECOM_AIBOT_SECRET` 是否来自同一个智能机器人。

### disconnected_event

说明同一机器人已有另一条新长连接建立。停止重复的 worker，保留一个。

### 能连接但收不到群消息

确认机器人已经被加入目标群，并且机器人拥有群消息接收权限。长连接只负责传输，群权限仍由企业微信后台控制。
