# 企业微信联调检查清单

## 1. 配置准备

需要从企业微信管理后台准备：

- `WECOM_CORP_ID`
- `WECOM_AGENT_ID`
- `WECOM_APP_SECRET`
- `WECOM_CALLBACK_TOKEN`
- `WECOM_ENCODING_AES_KEY`

发送模式：

```text
mock：本地开发
webhook：群机器人 Webhook
app：自建应用 API
```

## 2. 本地回调验证

启动服务：

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir src --host 127.0.0.1 --port 8000
```

执行加解密往返：

```powershell
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py roundtrip
```

执行 HTTP URL 验证：

```powershell
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py verify
```

模拟一条加密群消息：

```powershell
.\.venv\Scripts\python.exe scripts\debug_wecom_callback.py post
```

## 3. 检查配置状态

调用：

```text
GET /admin/integration-status
```

返回内容不会包含密钥，只会列出：

- 当前发送模式
- 缺失的发送配置
- 回调配置是否完整
- Dify 配置是否完整
- 当前数据库类型

## 4. 企业微信后台配置

回调 URL：

```text
https://your-domain.example/wecom/callback
```

要求：

- 公网可访问
- HTTPS
- Token 和 EncodingAESKey 与 `.env` 一致
- 域名和端口已正确转发

没有公网域名时，可以先用临时 HTTPS 隧道联调：

```powershell
.\scripts\start_wecom_tunnel.ps1 -Port 8000
```

脚本会优先启动 `cloudflared`，其次是 `ngrok`。把输出的 HTTPS 域名作为回调域名即可。临时隧道适合验证签名、加解密和消息链路，不建议长期生产使用。

## 5. 回调能力边界

当前项目使用的是企业微信自建应用回调：

- 可以接收成员发给应用的单聊消息
- 可以向应用可见成员发送单聊消息
- 可以通过 `appchat/create` 创建应用群聊并发送消息
- 普通企业微信群聊消息不会默认推送到自建应用回调

因此，不能把“群聊里发消息”直接等同于“应用回调收到消息”。如果需要让机器人实时读取普通群聊消息，需要接入企业微信智能机器人长连接、会话内容存档等能力，或改为：

- 单聊负责接收指令和偏好
- 群机器人 Webhook 负责把方案和结果广播到群
- 投票和报名通过管理台或网页完成

## 6. 常见问题

### invalid callback signature

常见原因：

- Token 不一致
- 请求参数被代理或网关修改
- 回调 URL 被额外编码

### callback corp_id mismatch

常见原因：

- `WECOM_CORP_ID` 填错
- 企业微信后台和 `.env` 不在同一个企业

### failed to get WeCom access token

常见原因：

- `WECOM_APP_SECRET` 填错
- 应用未启用
- 服务器出口 IP 不在企业可信 IP 范围

错误码 `60020` 表示当前出口 IP 未加入企业可信 IP。把这个 IP 加入企业微信应用设置中的“企业可信 IP”后再重试。

### appchat/send 返回错误

常见原因：

- `chatid` 不存在
- 应用没有群聊权限
- 当前消息不是来自应用可见的群聊

错误码 `86001` 表示 `chatid` 无效。回调里的普通群聊 ID 不一定能直接用于 `appchat/send`；应用群聊需要先通过 `appchat/create` 创建并拿到有效的 `chatid`。

## 7. 安全检查

- 不提交 `.env`
- 不在日志中打印 Secret、Token 或 EncodingAESKey
- `ADMIN_API_KEY` 在公开部署时必须配置
- PostgreSQL 不直接暴露到公网
- 反向代理只开放 HTTPS 和必要端口
