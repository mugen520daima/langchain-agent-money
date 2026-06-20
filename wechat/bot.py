"""
微信交互模块

使用 itchat 库实现微信消息的接收和发送。
支持：
1. 接收用户发送的基金查询消息
2. 自动生成报告并回复
3. 主动推送持仓报告
"""

import os
import sys
import threading
import time
import logging
from typing import Optional, Callable

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WeChatBot")


class WeChatBot:
    """微信机器人"""

    def __init__(self, config: dict = None, message_handler: Callable = None):
        """
        Args:
            config: 微信配置
            message_handler: 消息处理函数，接收消息文本和发送者，返回回复文本
        """
        self.config = config or {}
        self.message_handler = message_handler
        self.receivers = self.config.get("receivers", ["文件传输助手"])
        self.auto_reply = self.config.get("auto_reply", True)

        # itchat 实例（延迟导入）
        self._itchat = None
        self._is_running = False
        self._login_hook = None

    def start(self):
        """启动微信机器人"""
        try:
            import itchat
            self._itchat = itchat
        except ImportError:
            logger.error("itchat 未安装，请执行: pip install itchat")
            print("❌ itchat 未安装！请执行: pip install itchat")
            print("提示: itchat 可能不支持最新版微信，建议使用文件传输助手模式。")
            return

        # 注册消息处理
        @itchat.msg_register(itchat.content.TEXT)
        def text_reply(msg):
            """处理文本消息"""
            if not self.auto_reply:
                return

            text = msg.get("Text", "").strip()
            from_user = msg.get("FromUserName", "")
            to_user = msg.get("ToUserName", "")
            user_name = msg.get("User", {}).get("NickName", "未知用户")

            logger.info(f"收到消息: [{user_name}] {text}")

            # 处理消息
            if self.message_handler:
                try:
                    reply = self.message_handler(text, user_name)
                    if reply:
                        # 回复消息
                        return reply
                except Exception as e:
                    logger.error(f"处理消息失败: {e}")
                    return f"❌ 处理消息时出错，请稍后重试。\n错误: {str(e)}"

            return None

        # 注册图片消息（用于发送报告图片）
        @itchat.msg_register(itchat.content.PICTURE)
        def pic_reply(msg):
            return "图片已收到，请发送基金代码或文字指令查询。"

        # 登录
        print("=" * 50)
        print("📱 请扫描二维码登录微信...")
        print("=" * 50)
        print("提示：登录成功后，在微信中发送消息即可交互。")
        print("支持的命令：基金代码、报告、推荐、搜索 等")
        print("=" * 50)

        itchat.auto_login(
            hotReload=True,
            enableCmdQR=2,
            exitCallback=self._on_logout,
        )

        self._is_running = True

        if self._login_hook:
            self._login_hook()

        print("✅ 微信登录成功！基金报告助手已启动。")
        itchat.run()

    def stop(self):
        """停止微信机器人"""
        self._is_running = False
        if self._itchat:
            self._itchat.logout()

    def send_message(self, message: str, to_user: str = None):
        """
        发送微信消息

        Args:
            message: 消息内容
            to_user: 接收人（昵称或备注），默认发送给所有配置的接收人
        """
        if not self._itchat or not self._is_running:
            logger.warning("微信未连接，无法发送消息")
            return

        try:
            if to_user:
                # 发送给指定联系人
                users = self._itchat.search_friends(name=to_user)
                if users:
                    self._itchat.send(message, users[0].get("UserName"))
                    logger.info(f"消息已发送给 {to_user}")
                else:
                    logger.warning(f"未找到联系人: {to_user}")
            else:
                # 发送给所有接收人
                for receiver in self.receivers:
                    if receiver == "文件传输助手":
                        self._itchat.send(message, "filehelper")
                    else:
                        users = self._itchat.search_friends(name=receiver)
                        if users:
                            self._itchat.send(message, users[0].get("UserName"))
                    logger.info(f"消息已发送给 {receiver}")

        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    def send_report(self, report_text: str, receivers: list = None):
        """
        发送报告给指定接收人

        Args:
            report_text: 报告文本
            receivers: 接收人列表，默认使用配置中的接收人
        """
        targets = receivers or self.receivers
        for target in targets:
            self.send_message(report_text, target)
            time.sleep(1)  # 避免发送过快

    def send_to_filehelper(self, message: str):
        """发送消息到文件传输助手"""
        if self._itchat and self._is_running:
            try:
                self._itchat.send(message, "filehelper")
            except Exception as e:
                logger.error(f"发送到文件传输助手失败: {e}")

    def set_login_hook(self, hook: Callable):
        """设置登录成功后的回调"""
        self._login_hook = hook

    def _on_logout(self):
        """退出登录回调"""
        self._is_running = False
        logger.info("微信已退出登录")


# ========== 便捷使用 ==========

def run_wechat_bot(agent, config: dict):
    """
    启动微信机器人并绑定基金Agent

    Args:
        agent: FundAgent 实例
        config: 微信配置
    """
    def handler(text, user):
        return agent.process_message(text, user)

    bot = WeChatBot(config, message_handler=handler)

    print("🔄 正在启动基金报告助手...")
    print("提示：登录微信后，发送基金代码即可查询。")
    print("     发送「报告」生成完整持仓报告。")
    print("     发送「帮助」获取完整指令列表。")
    print()

    bot.start()
    return bot
