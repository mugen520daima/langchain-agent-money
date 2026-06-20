#!/usr/bin/env python3
"""
基金报告助手 - 主入口

启动方式：
    1. 普通模式（生成报告到控制台）：
       python main.py

    2. 微信模式（通过微信交互）：
       python main.py --wechat

    3. 生成报告并发送到微信：
       python main.py --send-report

用法：
    - 先配置 config.yaml（可复制 config.yaml.example）
    - 在配置文件中填写持仓信息
    - 启动程序后根据提示操作
"""

import os
import sys
import argparse
import yaml
import logging

# 添加项目根路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from core.agent import FundAgent
from wechat.bot import WeChatBot, run_wechat_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("FundAgent")


def load_config(config_path: str = None) -> dict:
    """加载配置文件"""
    if not config_path:
        config_path = os.path.join(PROJECT_ROOT, "config.yaml")

    # 如果 config.yaml 不存在，使用示例配置
    if not os.path.exists(config_path):
        example_path = os.path.join(PROJECT_ROOT, "config.yaml.example")
        if os.path.exists(example_path):
            print(f"⚠️ 未找到配置文件 {config_path}")
            print(f"   已复制示例配置到 {config_path}")
            print("   请修改配置后重新运行。")
            import shutil
            shutil.copy(example_path, config_path)
            sys.exit(0)
        else:
            print("❌ 未找到配置文件！")
            print("   请将 config.yaml.example 复制为 config.yaml 并修改。")
            sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return config or {}


def run_console_mode(agent: FundAgent):
    """控制台交互模式"""
    print()
    print("=" * 50)
    print("🤖 基金报告助手 (控制台模式)")
    print("=" * 50)
    print("输入指令与助手交互：")
    print("  📋 输入「报告」→ 生成持仓报告")
    print("  🔍 输入基金代码（如 000001）→ 查询基金")
    print("  🔎 输入「搜索 白酒」→ 搜索基金")
    print("  🎯 输入「推荐」→ 获取基金推荐")
    print("  ❓ 输入「帮助」→ 查看帮助")
    print("  🚪 输入「退出」→ 退出程序")
    print("=" * 50)
    print()

    while True:
        try:
            user_input = input("👤 请输入: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("退出", "exit", "quit", "q"):
                print("👋 再见！")
                break

            reply = agent.process_message(user_input, "default_user")
            print()
            print(reply)
            print()

        except KeyboardInterrupt:
            print("\n👋 再见！")
            break
        except Exception as e:
            print(f"❌ 出错: {e}")
            print()


def run_wechat_mode(agent: FundAgent, config: dict):
    """微信交互模式"""
    wechat_config = config.get("wechat", {})
    if not wechat_config.get("enabled", True):
        print("⚠️ 微信模式未启用（请检查配置文件中的 wechat.enabled）")
        return

    print("=" * 50)
    print("📱 基金报告助手 - 微信模式")
    print("=" * 50)
    print("即将启动微信登录...")
    print("请确保已安装 itchat: pip install itchat")
    print()
    print("登录成功后，在微信中发送消息即可交互。")
    print("支持发送: 基金代码、报告、推荐、搜索等指令。")
    print("=" * 50)
    print()

    # 启动微信机器人
    run_wechat_bot(agent, wechat_config)


def send_report_to_wechat(agent: FundAgent, config: dict):
    """生成报告并发送到微信"""
    wechat_config = config.get("wechat", {})

    print("📋 正在生成报告...")
    reply = agent.process_message("报告", "default_user")
    print("✅ 报告已生成！")

    if "❌" in reply:
        print(reply)
        return

    # 启动微信发送
    try:
        import itchat
        print("📱 请扫描二维码登录微信以发送报告...")
        itchat.auto_login(hotReload=True, enableCmdQR=2)

        receivers = wechat_config.get("receivers", ["文件传输助手"])
        for receiver in receivers:
            if receiver == "文件传输助手":
                itchat.send(reply, "filehelper")
                print(f"✅ 报告已发送到「文件传输助手」")
            else:
                users = itchat.search_friends(name=receiver)
                if users:
                    itchat.send(reply, users[0].get("UserName"))
                    print(f"✅ 报告已发送给「{receiver}」")
                else:
                    print(f"⚠️ 未找到联系人「{receiver}」")
            import time
            time.sleep(1)

        itchat.logout()
        print("📊 报告发送完成！")

    except ImportError:
        print("❌ 请先安装 itchat: pip install itchat")
    except Exception as e:
        print(f"❌ 发送报告失败: {e}")


def main():
    parser = argparse.ArgumentParser(description="基金报告助手")
    parser.add_argument("--wechat", action="store_true", help="启动微信交互模式")
    parser.add_argument("--send-report", action="store_true", help="生成报告并发送到微信")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径")
    parser.add_argument("--console", action="store_true", help="控制台交互模式（默认）")
    args = parser.parse_args()

    # 加载配置
    config = load_config(args.config)

    # 创建Agent
    agent = FundAgent(config)

    # 选择模式
    if args.wechat:
        run_wechat_mode(agent, config)
    elif args.send_report:
        send_report_to_wechat(agent, config)
    else:
        run_console_mode(agent)


if __name__ == "__main__":
    main()
