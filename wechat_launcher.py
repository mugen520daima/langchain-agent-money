#!/usr/bin/env python3
"""
📱 微信启动器 - 一键启动微信对话模式

功能：
  - 首次运行：弹出二维码，扫码后即可微信对话
  - 后续运行：自动复用登录状态，无需重新扫码
  - 24小时在线：后台运行，不会掉线

使用方法：
  python wechat_launcher.py              # 启动微信对话模式
  python wechat_launcher.py --daemon     # 后台运行（nohup）
"""

import os
import sys
import time
import logging
import threading
import signal

# 添加项目根路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

import yaml
from core.agent import FundAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WeChatBot")

# ====== 配置 ======
CONFIG_FILE = os.path.join(PROJECT_ROOT, "config.yaml")
CACHE_FILE = os.path.join(PROJECT_ROOT, "itchat.pkl")


def load_config():
    """加载配置"""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ 未找到配置文件: {CONFIG_FILE}")
        print(f"   请先执行: cp config.yaml.example config.yaml")
        sys.exit(1)

    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def check_login_cache():
    """检查是否有登录缓存"""
    if os.path.exists(CACHE_FILE):
        size = os.path.getsize(CACHE_FILE)
        print(f"✅ 检测到登录缓存 (itchat.pkl, {size} bytes)")
        print(f"   将自动登录，无需扫码")
        return True
    return False


def print_banner(first_time):
    """打印启动信息"""
    print()
    print("╔══════════════════════════════════════════════╗")
    print("║     📱  基 金 报 告 助 手                     ║")
    print("║        微信对话模式                          ║")
    print("╠══════════════════════════════════════════════╣")
    print("║  驱动力: 通义千问 qwen-plus                   ║")
    print("║  角色: 傲娇猫娘「巧克力」                     ║")
    print("╚══════════════════════════════════════════════╝")
    print()

    if first_time:
        print("📱 首次启动，请用手机微信扫描弹出的二维码...")
        print("   扫码后点击「登录」，即可开始对话")
        print()
    else:
        print("📱 检测到登录缓存，正在自动登录...")
        print()


def run():
    """主流程"""
    config = load_config()
    agent = FundAgent(config)

    # 检查缓存
    has_cache = check_login_cache()
    print_banner(not has_cache)

    # 动态导入 itchat（延迟加载）
    try:
        import itchat
    except ImportError:
        print("❌ 缺少 itchat 库，请安装:")
        print("   pip install itchat")
        sys.exit(1)

    # 创建消息处理器
    def handle_message(msg):
        """处理微信消息"""
        text = msg.get("Text", "").strip()
        from_user = msg.get("FromUserName", "")
        user_name = msg.get("User", {}).get("NickName", "未知用户")

        # 忽略空消息
        if not text:
            return None

        logger.info(f"📩 [{user_name}] {text}")

        try:
            reply = agent.process_message(text, user_name)
            if reply:
                logger.info(f"📤 [{user_name}] 已回复")
                return reply
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return f"呜...巧克力好像出错了喵~ {str(e)}"

        return None

    # 注册消息处理器
    @itchat.msg_register(itchat.content.TEXT)
    def text_reply(msg):
        return handle_message(msg)

    @itchat.msg_register(itchat.content.PICTURE)
    def pic_reply(msg):
        return "图片收到喵~ 不过巧克力只会看文字哦，试试发送基金代码？"

    # 登录 - 优先使用缓存
    print("=" * 50)
    if has_cache:
        print("🔄 正在使用缓存登录...")
    else:
        print("📸 正在生成二维码...")
    print("=" * 50)
    print()

    # 在 Mac 上，如果安装了 Pillow 会有弹窗二维码
    # 否则会在终端打印二维码字符画
    try:
        import PIL
        # 有 Pillow，生成图片文件自动打开
        qr_file = os.path.join(PROJECT_ROOT, "qr_code.png")
        itchat.auto_login(
            hotReload=True,
            enableCmdQR=2,
            picDir=qr_file if not has_cache else None,
        )
        # 尝试用系统预览打开
        if not has_cache and os.path.exists(qr_file):
            os.system(f"open {qr_file}")
            print("📸 已打开二维码图片窗口，请用微信扫描")
    except ImportError:
        # 没有 Pillow，用终端字符画
        itchat.auto_login(
            hotReload=True,
            enableCmdQR=2,
        )

    if not has_cache:
        print()
        print("✅ 微信登录成功！")
        print("💡 已缓存登录状态，下次启动无需扫码")
        print()

    print("🐱 「巧克力」已上线！快去微信找她聊天吧~")
    print()
    print("📋 微信中支持发送：")
    print("   🔍 基金代码 → 查详情（如 110011）")
    print("   📋 报告 → 持仓分析")
    print("   🔎 搜索 xxx → 找基金")
    print("   🎯 推荐 → 精选推荐")
    print("   💬 任意聊天 → 傲娇猫娘陪你")
    print()
    print("⏳ 正在监听消息... (按 Ctrl+C 停止)")
    print()

    # 保持运行
    itchat.run()


if __name__ == "__main__":
    # 后台运行参数
    if "--daemon" in sys.argv:
        print("📱 后台模式启动...")
        print(f"   日志: {os.path.join(PROJECT_ROOT, 'wechat.log')}")
        print(f"   停止: kill {os.getpid()}")
        # 重定向输出到文件
        log_file = open(os.path.join(PROJECT_ROOT, "wechat.log"), "a")
        sys.stdout = log_file
        sys.stderr = log_file

    try:
        run()
    except KeyboardInterrupt:
        print()
        print("👋 巧克力已下线，下次见喵~")
        sys.exit(0)
