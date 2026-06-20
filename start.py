#!/usr/bin/env python3
"""
⚡ 基金报告助手 - 一键启动脚本

支持三种启动模式：
  1. python start.py           → 控制台交互模式（推荐新手）
  2. python start.py --wechat  → 微信交互模式（需安装 itchat）
  3. python start.py --report  → 生成报告并发送到微信

首次使用前请确保已配置 config.yaml：
  1. 填写你的持仓基金信息（基金代码、投入金额、持有份额）
  2. 如使用微信模式，配置接收人列表
"""

import os
import sys
import subprocess
import argparse

# ====== 配置检查 ======

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
CONFIG_EXAMPLE = os.path.join(PROJECT_ROOT, "config.yaml.example")


def print_banner():
    """打印启动横幅"""
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     🤖  基 金 报 告 助 手                    ║")
    print("║     Fund Report Agent                       ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  支持: 持仓分析 · 风险评估 · 基金推荐       ║")
    print("║  模式: 控制台 · 微信                        ║")
    print("╚══════════════════════════════════════════════╝")
    print()


def check_config():
    """检查配置文件是否就绪"""
    if not os.path.exists(CONFIG_FILE):
        if os.path.exists(CONFIG_EXAMPLE):
            print("⚠️  未检测到 config.yaml 配置文件")
            print("   正在从示例文件创建...")
            import shutil
            shutil.copy(CONFIG_EXAMPLE, CONFIG_FILE)
            print(f"   ✅ 已创建 {CONFIG_FILE}")
            print("   ⚠️  请先编辑 config.yaml，填写您的持仓信息后再运行！")
            print("     编辑完成后重新运行: python start.py")
            print()
            print("   📝 关键配置项说明：")
            print("     1. portfolios.default_user.funds  → 你的持仓基金")
            print("        - code: 基金代码（如 000001）")
            print("        - name: 基金名称")
            print("        - cost: 总投入金额（元）")
            print("        - shares: 持有份额")
            print("     2. wechat.receivers  → 微信接收人（可选）")
            print()
            sys.exit(0)
        else:
            print("❌ 未找到配置文件！")
            print("   请确保以下文件存在：")
            print(f"   - {CONFIG_FILE}")
            print(f"   - {CONFIG_EXAMPLE}")
            print()
            print("   如果文件缺失，请重新下载项目。")
            sys.exit(1)
    return True


def check_dependencies():
    """检查关键依赖是否安装"""
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        import yaml
    except ImportError:
        missing.append("pyyaml")
    try:
        import numpy
    except ImportError:
        missing.append("numpy")
    try:
        import dateutil
    except ImportError:
        missing.append("python-dateutil")

    if missing:
        print(f"⚠️  缺少依赖包: {', '.join(missing)}")
        print("   正在尝试安装...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r",
                 os.path.join(PROJECT_ROOT, "requirements.txt")]
            )
            print("   ✅ 依赖安装完成！")
        except subprocess.CalledProcessError as e:
            print(f"   ❌ 依赖安装失败: {e}")
            print("   请手动执行: pip install -r requirements.txt")
            sys.exit(1)


def check_wechat_mode(args):
    """检查微信模式参数"""
    return args.wechat or args.report


def run_console():
    """启动控制台模式"""
    print("📋 启动控制台交互模式...")
    print("   输入指令与助手交互：")
    print("   - 📋 输入「报告」→ 生成持仓报告")
    print("   - 🔍 输入基金代码 → 查询单支基金")
    print("   - 🔎 输入「搜索 xxx」→ 搜索基金")
    print("   - 🎯 输入「推荐」→ 获取基金推荐")
    print("   - ❓ 输入「帮助」→ 查看帮助菜单")
    print("   - 🚪 输入「退出」→ 退出程序")
    print()

    # 导入并运行主程序
    sys.path.insert(0, PROJECT_ROOT)
    from core.agent import FundAgent
    import yaml

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    agent = FundAgent(config)
    
    # 启动前先输出帮助信息
    print(agent.process_message("帮助"))
    print()

    while True:
        try:
            user_input = input("👤 请输入: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("退出", "exit", "quit", "q"):
                print("👋 感谢使用基金报告助手，再见！")
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


def run_wechat():
    """启动微信交互模式"""
    print("📱 启动微信交互模式...")
    print("   请确保已安装 itchat: pip install itchat")
    print()
    print("   登录成功后，在微信中发送指令即可交互。")
    print()

    sys.path.insert(0, PROJECT_ROOT)
    import yaml

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # 检查微信配置
    wechat_config = config.get("wechat", {})
    if not wechat_config.get("enabled", True):
        print("⚠️  微信模式未启用（config.yaml 中 wechat.enabled 为 false）")
        print("   如需启用，请修改配置或使用控制台模式: python start.py")
        return

    from core.agent import FundAgent
    from wechat.bot import run_wechat_bot

    agent = FundAgent(config)
    run_wechat_bot(agent, wechat_config)


def send_report():
    """生成报告并发送到微信"""
    print("📋 正在生成报告...")
    
    sys.path.insert(0, PROJECT_ROOT)
    import yaml

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    from core.agent import FundAgent
    agent = FundAgent(config)

    reply = agent.process_message("报告", "default_user")
    
    if "❌" in reply[:5]:
        print(f"❌ 报告生成失败: {reply[:200]}")
        return

    print("✅ 报告已生成！准备发送到微信...")
    print()

    try:
        import itchat
        print("📱 请扫描二维码登录微信...")
        itchat.auto_login(hotReload=True, enableCmdQR=2)

        wechat_config = config.get("wechat", {})
        receivers = wechat_config.get("receivers", ["文件传输助手"])

        import time
        for receiver in receivers:
            if receiver == "文件传输助手":
                itchat.send(reply, "filehelper")
                print(f"   ✅ 已发送到「文件传输助手」")
            else:
                users = itchat.search_friends(name=receiver)
                if users:
                    itchat.send(reply, users[0].get("UserName"))
                    print(f"   ✅ 已发送给「{receiver}」")
                else:
                    print(f"   ⚠️  未找到联系人「{receiver}」")
            time.sleep(1)

        itchat.logout()
        print()
        print("📊 报告发送完成！")

    except ImportError:
        print("❌ 请先安装 itchat: pip install itchat")
        print("   python -m pip install itchat")
    except Exception as e:
        print(f"❌ 发送报告失败: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="🤖 基金报告助手 - 一键启动"
    )
    parser.add_argument(
        "--wechat", "-w",
        action="store_true",
        help="启动微信交互模式"
    )
    parser.add_argument(
        "--report", "-r",
        action="store_true",
        help="生成持仓报告并发送到微信"
    )
    parser.add_argument(
        "--console", "-c",
        action="store_true",
        help="启动控制台交互模式（默认）"
    )

    args = parser.parse_args()

    # 打印横幅
    print_banner()

    # 检查配置和依赖
    check_config()
    check_dependencies()

    # 选择启动模式
    if args.wechat:
        run_wechat()
    elif args.report:
        send_report()
    else:
        run_console()


if __name__ == "__main__":
    main()
