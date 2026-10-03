# Nginx 部署说明

HTTP 模式：

```powershell
docker compose up --build
```

管理前端：`http://localhost:8080`

HTTPS 模式需要准备证书：

```text
certs/fullchain.pem
certs/privkey.pem
```

启动：

```powershell
$env:APP_DOMAIN = "your-domain.example"
$env:TLS_CERT_PATH = "./certs/fullchain.pem"
$env:TLS_KEY_PATH = "./certs/privkey.pem"
docker compose -f docker-compose.yml -f docker-compose.https.yml up --build
```

Nginx 会：

- 提供管理前端静态文件
- 将 `/api/` 转发到 FastAPI
- 将 `/wecom/` 转发到 FastAPI
- 将 `/health` 转发到 FastAPI
