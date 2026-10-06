#!/bin/bash
# n8n 团队协作启动脚本
# 用法: ./start-n8n.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export N8N_USER_FOLDER="$SCRIPT_DIR/n8n-data"
export N8N_LISTEN_ADDRESS="0.0.0.0"
export N8N_PORT="5678"
export N8N_SECURE_COOKIE="false"
export N8N_DEFAULT_LOCALE="zh-CN"
export NODE_FUNCTION_ALLOW_BUILTIN="https,child_process,http,url,querystring"
export GENERIC_TIMEZONE="Asia/Shanghai"

# 获取本机 IP
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print $2}')

echo "========================================="
echo "  n8n 团队协作模式启动"
echo "========================================="
echo "  本机访问: http://localhost:5678"
echo "  团队访问: http://${LOCAL_IP}:5678"
echo "========================================="

n8n start
