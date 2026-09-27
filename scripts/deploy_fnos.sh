#!/usr/bin/env bash
# ==============================================================================
# EasyExam (易考宝) - 私有云一键安装与更新自动化脚本
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${SCRIPT_DIR}"

echo "========================================================"
echo "🚀 正在为私有云 NAS (fnOS) 部署 EasyExam (易考宝) 题库系统..."
echo "========================================================"

# 1. 确保数据持久化目录存在
DATA_DIR="${SCRIPT_DIR}/data"
if [ ! -d "${DATA_DIR}" ]; then
    echo "📁 创建持久化数据目录: ${DATA_DIR}"
    mkdir -p "${DATA_DIR}"
fi
chmod 755 "${DATA_DIR}" || true

# 2. 确保持久化密钥配置 (.env)
ENV_FILE="${SCRIPT_DIR}/.env"
if [ -f "${ENV_FILE}" ]; then
    echo "🔑 加载已存在的 .env 配置..."
    set -a
    . "${ENV_FILE}"
    set +a
fi

if [ -z "${EASYEXAM_SECRET_KEY:-}" ]; then
    echo "🔑 正在为首次部署生成持久化主密钥 (${ENV_FILE})..."
    GENERATED_KEY=""
    if command -v python3 >/dev/null 2>&1; then
        GENERATED_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || true)
    fi
    if [ -z "$GENERATED_KEY" ] && command -v openssl >/dev/null 2>&1; then
        GENERATED_KEY=$(openssl rand -hex 32 2>/dev/null || true)
    fi
    if [ -z "$GENERATED_KEY" ] && [ -r /dev/urandom ]; then
        if command -v od >/dev/null 2>&1; then
            GENERATED_KEY=$(od -vN 32 -An -tx1 /dev/urandom 2>/dev/null | tr -d ' \n' || true)
        elif command -v xxd >/dev/null 2>&1; then
            GENERATED_KEY=$(head -c 32 /dev/urandom 2>/dev/null | xxd -p -c 32 || true)
        fi
    fi
    if [ -z "$GENERATED_KEY" ] || [ "${#GENERATED_KEY}" -lt 64 ]; then
        echo "❌ 错误: 无法生成密码学安全密钥，密码学随机源不可用！" >&2
        exit 1
    fi
    echo "EASYEXAM_SECRET_KEY=${GENERATED_KEY}" >> "${ENV_FILE}"
    chmod 600 "${ENV_FILE}" || true
    export EASYEXAM_SECRET_KEY="${GENERATED_KEY}"
    echo "⚠️ 已在 .env 中生成并保存主密钥。容器更新或重建时请务必保持此密钥不变！"
fi

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
echo "🔄 启动/更新 EasyExam 容器..."
# 清理可能存在的旧项目容器 (fn-exam) 以防端口 3000 冲突
docker stop fn-exam 2>/dev/null || true
docker rm fn-exam 2>/dev/null || true
${COMPOSE_CMD} down --remove-orphans || true
${COMPOSE_CMD} up -d --build

# 5. 等待服务就绪与健康检查
echo "⏳ 等待应用容器启动与健康检查 (/api/v1/health)..."
MAX_ATTEMPTS=30
ATTEMPT=0
HEALTH_URL="http://127.0.0.1:3000/api/v1/health"

while [ ${ATTEMPT} -lt ${MAX_ATTEMPTS} ]; do
    if curl -s -f "${HEALTH_URL}" &> /dev/null; then
        echo "✅ EasyExam 健康检查通过！"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    sleep 1
done

if [ ${ATTEMPT} -ge ${MAX_ATTEMPTS} ]; then
    echo "⚠️ 容器已启动，但在 30 秒内未能通过健康检查，请检查容器日志:"
    ${COMPOSE_CMD} logs --tail=50 easy-exam
    exit 1
fi

# 6. 获取并打印本地 NAS IP
NAS_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

echo "========================================================"
echo "🎉 EasyExam (易考宝) 已成功部署并运行！"
echo "🌐 访问地址: http://${NAS_IP}:3000"
echo "💾 数据持久化路径: ${DATA_DIR}"
echo "📝 查看日志: ${COMPOSE_CMD} logs -f easy-exam"
echo "========================================================"
