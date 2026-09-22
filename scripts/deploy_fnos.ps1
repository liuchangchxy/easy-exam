<#
.SYNOPSIS
    FnExam (飞牛刷题系统) - Windows / 本地测试与部署脚本
#>

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "🚀 正在部署 FnExam 极简题库系统..." -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. 确保数据持久化目录存在
$dataDir = Join-Path $projectRoot "data"
if (-not (Test-Path $dataDir)) {
    Write-Host "📁 创建持久化数据目录: $dataDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}

# 2. 检查 Docker 运行环境
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Error "❌ 错误: 未检测到 Docker，请先安装 Docker Desktop 并启动！"
    exit 1
}

# 3. 停止旧容器并构建/拉取最新服务
Write-Host "🔄 启动/更新 FnExam 容器..." -ForegroundColor Yellow
try {
    docker compose down --remove-orphans
} catch {
    # 忽略初次部署 down 的错误
}

docker compose up -d --build

# 4. 等待服务就绪与健康检查
Write-Host "⏳ 等待应用容器启动与健康检查 (/api/health)..." -ForegroundColor Yellow
$maxAttempts = 30
$attempt = 0
$healthy = $false
$healthUrl = "http://127.0.0.1:3000/api/health"

while ($attempt -lt $maxAttempts) {
    try {
        $response = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 2 -ErrorAction Stop
        if ($response.status -eq "ok") {
            $healthy = $true
            break
        }
    } catch {
        # 服务启动中，继续等待
    }
    $attempt++
    Start-Sleep -Seconds 1
}

if (-not $healthy) {
    Write-Host "⚠️ 容器已启动，但在 30 秒内未能通过健康检查，请检查容器日志:" -ForegroundColor Red
    docker compose logs --tail=50 fn-exam
    exit 1
}

Write-Host "========================================================" -ForegroundColor Green
Write-Host "🎉 FnExam 已成功部署并运行！" -ForegroundColor Green
Write-Host "🌐 访问地址: http://localhost:3000" -ForegroundColor Green
Write-Host "💾 数据持久化路径: $dataDir" -ForegroundColor Green
Write-Host "📝 查看日志: docker compose logs -f fn-exam" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Green
