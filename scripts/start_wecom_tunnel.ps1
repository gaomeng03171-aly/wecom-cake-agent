param(
    [int]$Port = 8000
)

$cloudflared = Get-Command cloudflared -ErrorAction SilentlyContinue
$ngrok = Get-Command ngrok -ErrorAction SilentlyContinue

if ($cloudflared) {
    Write-Host "Starting cloudflared tunnel to http://127.0.0.1:$Port"
    Write-Host "Use the printed trycloudflare.com URL as the WeCom callback domain."
    & $cloudflared.Source tunnel --url "http://127.0.0.1:$Port"
    exit $LASTEXITCODE
}

if ($ngrok) {
    Write-Host "Starting ngrok tunnel to http://127.0.0.1:$Port"
    Write-Host "Use the printed ngrok URL as the WeCom callback domain."
    & $ngrok.Source http $Port
    exit $LASTEXITCODE
}

Write-Host "No public tunnel tool found."
Write-Host "Install cloudflared: winget install Cloudflare.cloudflared"
Write-Host "Then run: .\scripts\start_wecom_tunnel.ps1 -Port 8000"
exit 1
