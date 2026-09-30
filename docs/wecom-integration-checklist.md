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

## 5. 常见问题

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

### appchat/send 返回错误

常见原因：

- `chatid` 不存在
- 应用没有群聊权限
- 当前消息不是来自应用可见的群聊

## 6. 安全检查

- 不提交 `.env`
- 不在日志中打印 Secret、Token 或 EncodingAESKey
- `ADMIN_API_KEY` 在公开部署时必须配置
- PostgreSQL 不直接暴露到公网
- 反向代理只开放 HTTPS 和必要端口
