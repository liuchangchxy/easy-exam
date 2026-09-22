#!/usr/bin/env bash
# ==============================================================================
# FnExam (飞牛刷题系统) - fnOS 一键安装与更新自动化脚本
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}"

echo "========================================================"
echo "🚀 正在为飞牛 NAS (fnOS) 部署 FnExam 极简题库系统..."
echo "========================================================"

# 1. 确保数据持久化目录存在
DATA_DIR="${SCRIPT_DIR}/data"
if [ ! -d "${DATA_DIR}" ]; then
    echo "📁 创建持久化数据目录: ${DATA_DIR}"
    mkdir -p "${DATA_DIR}"
fi
chmod 755 "${DATA_DIR}" || true

# 2. 检查 Docker 运行环境
if ! command -v docker &> /dev/null; then
    echo "❌ 错误: 未检测到 Docker 命令，请先在飞牛应用中心安装 Docker 服务！"
    exit 1
fi

# 3. 确定 compose 命令
if docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo "❌ 错误: 未检测到 docker compose 或 docker-compose 插件！"
    exit 1
fi

echo "📦 使用 Docker 编排命令: ${COMPOSE_CMD}"

# 4. 停止旧容器并构建/拉取最新服务
echo "🔄 启动/更新 FnExam 容器..."
${COMPOSE_CMD} down --remove-orphans || true
${COMPOSE_CMD} up -d --build

# 5. 等待服务就绪与健康检查
echo "⏳ 等待应用容器启动与健康检查 (/api/health)..."
MAX_ATTEMPTS=30
ATTEMPT=0
HEALTH_URL="http://127.0.0.1:3000/api/health"

while [ ${ATTEMPT} -lt ${MAX_ATTEMPTS} ]; do
    if curl -s -f "${HEALTH_URL}" &> /dev/null; then
        echo "✅ FnExam 健康检查通过！"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep 1
done

if [ ${ATTEMPT} -ge ${MAX_ATTEMPTS} ]; then
    echo "⚠️ 容器已启动，但在 30 秒内未能通过健康检查，请检查容器日志:"
    ${COMPOSE_CMD} logs --tail=50 fn-exam
    exit 1
fi

# 6. 获取并打印本地 NAS IP
NAS_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo "========================================================"
echo "🎉 FnExam 已成功部署并运行在飞牛 NAS！"
echo "🌐 访问地址: http://${NAS_IP}:3000"
echo "💾 数据持久化路径: ${DATA_DIR}"
echo "📝 查看日志: ${COMPOSE_CMD} logs -f fn-exam"
echo "========================================================"
