#!/bin/bash
# ============================================================
# 📱 微信测试号 - 一键启动脚本
# ============================================================
# 使用方法：
#   1. 先开通测试号：https://mp.weixin.qq.com/debug/cgi-bin/sandbox
#   2. 扫码登录获取 appID 和 appsecret
#   3. 运行: bash launch_wechat_test.sh
#   4. 输入 appID, appsecret, token
#   5. 启用 ngrok，把公网 URL 填回测试号后台
#   6. 用微信关注测试号，开始聊天
# ============================================================

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PYTHON="/Users/chenweile/Desktop/anaconda/anaconda3/bin/python"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║     📱  微信测试号 Bot                         ║"
echo "║         对接基金助手                          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ====== 配置输入 ======

read -p "请输入 appID (从测试号页面复制): " APP_ID
read -p "请输入 appsecret (从测试号页面复制): " APP_SECRET
read -p "请输入 Token (自定义, 如 fundagent): " TOKEN
TOKEN=${TOKEN:-fundagent123}
read -p "请输入端口号 [9000]: " PORT
PORT=${PORT:-9000}

echo ""
echo "========================================"
echo "配置确认："
echo "  appID:     ${APP_ID:0:5}******"
echo "  appsecret: ${APP_SECRET:0:5}******"
echo "  Token:     $TOKEN"
echo "  端口:      $PORT"
echo "========================================"
echo ""

# ====== 启动服务 ======

echo "🚀 正在启动..."
echo ""

export WX_APP_ID="$APP_ID"
export WX_APP_SECRET="$APP_SECRET"
export WX_TOKEN="$TOKEN"

$PYTHON -c "
import sys, os
sys.path.insert(0, '$PROJECT_DIR')
from wechat_test_account import WeChatTestBot, run_with_agent
from core.agent import FundAgent
import yaml

# 加载配置
config_path = os.path.join('$PROJECT_DIR', 'config.yaml')
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}
else:
    config = {}

# 注入微信测试号配置
config['wechat_test'] = {
    'app_id': '$APP_ID',
    'app_secret': '$APP_SECRET',
    'token': '$TOKEN',
    'port': $PORT,
}

# 创建 Agent 并启动
agent = FundAgent(config)
run_with_agent(agent, config)
" 2>&1
