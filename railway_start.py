#!/usr/bin/env python3
"""
Railway 云部署专用启动脚本

将从环境变量读取配置，而非配置文件。
在 Railway 后台设置以下环境变量：
  - WX_APP_ID
  - WX_APP_SECRET
  - WX_TOKEN
  - LLM_API_KEY
  - LLM_API_BASE (可选)
  - LLM_MODEL (可选)
"""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

# 检查关键环境变量
required_vars = ["WX_APP_ID", "WX_APP_SECRET"]
missing = [v for v in required_vars if not os.getenv(v)]
if missing:
    print(f"❌ 缺少环境变量: {', '.join(missing)}")
    print()
    print("请在 Railway 后台设置以下环境变量：")
    print("  WX_APP_ID:     微信测试号 appID")
    print("  WX_APP_SECRET: 微信测试号 appsecret")
    print("  WX_TOKEN:      自定义 Token（可选，默认 fundagent123）")
    print("  LLM_API_KEY:   通义千问 API Key（可选，否则用代码中的默认值）")
    sys.exit(1)

# 构建配置
config = {
    "llm": {
        "api_key": os.getenv("LLM_API_KEY"),
        "api_base": os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"),
        "model": os.getenv("LLM_MODEL", "qwen-plus"),
        "temperature": 0.8,
    },
    "wechat_test": {
        "app_id": os.getenv("WX_APP_ID"),
        "app_secret": os.getenv("WX_APP_SECRET"),
        "token": os.getenv("WX_TOKEN", "fundagent123"),
        "port": int(os.getenv("PORT", 9000)),
    }
}

# 导入 agent 和 bot
from core.agent import FundAgent
from wechat_test_account import run_with_agent

agent = FundAgent(config)

print("🚀 基金助手 (Railway 部署) 启动中...")
print(f"   模型: {config['llm']['model']}")
print(f"   端口: {config['wechat_test']['port']}")

run_with_agent(agent, config)
