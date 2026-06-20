#!/usr/bin/env python3
"""
📱 微信测试号 - 一键启动

自动完成：
  1. 启动基金 Agent 服务
  2. 建立内网穿透（serveo）
  3. 指导填入微信测试号后台

使用方法：
  python run_wechat_bot.py
"""

import os
import sys
import time
import json
import subprocess
import threading
import signal

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import yaml


def print_banner():
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     📱  微信测试号 - 一键启动                 ║")
    print("╚══════════════════════════════════════════════╝")
    print()


def get_config():
    """获取或输入配置"""
    app_id = os.getenv("WX_APP_ID")
    app_secret = os.getenv("WX_APP_SECRET")
    token = os.getenv("WX_TOKEN", "fundagent123")

    if not app_id or not app_secret:
        print("请填写微信测试号信息：")
        print("（从 https://mp.weixin.qq.com/debug/cgi-bin/sandbox 获取）")
        print()
        app_id = input("appID: ").strip()
        app_secret = input("appsecret: ").strip()
        token = input("Token (回车默认 fundagent123): ").strip() or "fundagent123"
        print()

    return app_id, app_secret, token


def start_bot_service(app_id, app_secret, token, port=9000):
    """启动 Bot 服务"""
    from wechat_test_account import WeChatTestBot
    from core.agent import FundAgent

    config_path = os.path.join(PROJECT_ROOT, "config.yaml")
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f) or {}
    else:
        config = {}

    # 注入微信测试号配置
    if "wechat_test" not in config:
        config["wechat_test"] = {}
    config["wechat_test"].update({
        "app_id": app_id,
        "app_secret": app_secret,
        "token": token,
        "port": port,
    })

    agent = FundAgent(config)

    def handler(text, user_id):
        return agent.process_message(text, user_id)

    bot = WeChatTestBot(
        app_id=app_id,
        app_secret=app_secret,
        token=token,
        agent=handler,
        host="0.0.0.0",
        port=port,
    )

    # 在单独的线程中运行
    thread = threading.Thread(target=bot.start, daemon=True)
    thread.start()
    return bot, thread


def start_serveo_tunnel(port=9000):
    """启动 serveo 内网穿透，自动重连"""
    public_url = None

    while True:
        try:
            proc = subprocess.Popen(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ServerAliveInterval=30",
                 "-R", f"80:localhost:{port}",
                 "serveo.net"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in proc.stdout:
                line = line.strip()
                print(f"  {line}")
                if "Forwarding HTTP traffic from" in line:
                    # 提取公网 URL
                    url_part = line.split("from")[-1].strip()
                    if url_part != public_url:
                        public_url = url_part
                        on_tunnel_ready(public_url)

            proc.wait()
        except Exception as e:
            print(f"  ⚠️ 隧道断开: {e}")

        print("  🔄 10 秒后重连...")
        time.sleep(10)


def on_tunnel_ready(public_url):
    """隧道就绪时的回调"""
    print()
    print("=" * 55)
    print("✅ 隧道创建成功！")
    print("=" * 55)
    print()
    print(f"🌐 公网地址: {public_url}")
    print()
    print("📝 请打开测试号后台：")
    print("   https://mp.weixin.qq.com/debug/cgi-bin/sandbox")
    print()
    print("点击「接口配置信息」→ 修改，填写：")
    print(f"   URL:   {public_url}/wechat")
    print(f"   Token: fundagent123")
    print()
    print("提交成功后，用微信扫描测试号二维码关注")
    print("发送消息即可和巧克力聊天！")
    print()
    print("=" * 55)
    print()


def main():
    print_banner()

    # 1. 获取配置
    app_id, app_secret, token = get_config()

    # 2. 启动 Bot 服务
    print("🚀 启动基金助手服务...")
    bot, bot_thread = start_bot_service(app_id, app_secret, token, port=9000)
    time.sleep(2)
    print("✅ 服务已启动 (端口 9000)")
    print()

    # 3. 启动内网穿透
    print("🔗 正在建立内网穿透（连接到 serveo.net）...")
    print("   首次连接可能需要 10-30 秒")
    print()

    try:
        start_serveo_tunnel(port=9000)
    except KeyboardInterrupt:
        print()
        print("👋 已停止")


if __name__ == "__main__":
    main()
