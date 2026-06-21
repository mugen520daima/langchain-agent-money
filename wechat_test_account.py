#!/usr/bin/env python3
"""
📱 微信测试号接入模块

工作原理：
  1. 开通微信测试号（免费）→ 获取 appID + appSecret
  2. 代码启动一个 Web 服务器（/wechat 路径）
  3. 把 URL + Token 填回测试号后台
  4. 用户给测试号发消息 → 微信推送到我们的服务器 → AI 回复 → 回送微信

前置条件（无需任何额外安装）：
  - Python 自带 http.server

使用方法：
  1. 开通测试号：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
  2. 扫码登录，记下 appID 和 appsecret
  3. 配置本模块的环境变量
  4. 启动服务
  5. 配置内网穿透（如 ngrok）获得公网 URL
  6. 回填 URL 和 Token 到测试号后台

微信公众号文档：
  https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Access_Overview.html
"""

import os
import sys
import json
import hashlib
import hmac
import time
import re
import xml.etree.ElementTree as ET
import threading
import urllib.request
import urllib.parse
import logging
from typing import Optional, Callable, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler

# 添加项目根路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("WeChatTestAccount")


class WeChatTestBot:
    """
    微信测试号 Bot
    
    接收微信用户消息，通过基金 Agent 处理并回复。
    """
    
    # 微信消息类型
    MSG_TEXT = "text"
    MSG_IMAGE = "image"
    MSG_VOICE = "voice"
    MSG_VIDEO = "video"
    MSG_LOCATION = "location"
    MSG_LINK = "link"
    MSG_EVENT = "event"
    
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        token: str,
        agent: Optional[Callable] = None,
        host: str = "0.0.0.0",
        port: int = 9000,
    ):
        """
        Args:
            app_id: 微信测试号 appID
            app_secret: 微信测试号 appsecret
            token: 自定义的 Token（需回填测试号后台）
            agent: 消息处理函数，接收 (text, user_id) 返回回复文本
            host: 监听地址
            port: 监听端口
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.token = token
        self.agent = agent
        self.host = host
        self.port = port
        
        # access_token 缓存
        self._access_token = None
        self._token_expires_at = 0
        
        # 服务器
        self._server = None
        self._thread = None
        
        logger.info(f"📱 微信测试号 Bot 初始化完成")
        logger.info(f"   监听地址: http://{host}:{port}")
        logger.info(f"   回调路径: /wechat")
        logger.info(f"   Token: {token}")
    
    def _verify_signature(self, params: Dict) -> bool:
        """验证微信签名"""
        signature = params.get("signature", "")
        timestamp = params.get("timestamp", "")
        nonce = params.get("nonce", "")
        
        arr = sorted([self.token, timestamp, nonce])
        tmp_str = "".join(arr)
        sha1 = hashlib.sha1(tmp_str.encode()).hexdigest()
        
        return sha1 == signature
    
    def _get_access_token(self) -> Optional[str]:
        """获取微信 API 的 access_token（缓存机制）"""
        now = time.time()
        if self._access_token and now < self._token_expires_at:
            return self._access_token
        
        url = "https://api.weixin.qq.com/cgi-bin/stable_token"
        data = json.dumps({
            "grant_type": "client_credential",
            "appid": self.app_id,
            "secret": self.app_secret,
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
                
            if "access_token" in result:
                self._access_token = result["access_token"]
                self._token_expires_at = now + result.get("expires_in", 7200) - 60
                logger.info("✅ 获取 access_token 成功")
                return self._access_token
            else:
                logger.error(f"❌ 获取 access_token 失败: {result}")
                return None
        except Exception as e:
            logger.error(f"❌ 请求 access_token 出错: {e}")
            return None
    
    def _send_message(self, openid: str, content: str):
        """发送客服消息给用户"""
        logger.info(f"📤 准备发送消息给 {openid[:8]}... 内容长度: {len(content)}")
        
        access_token = self._get_access_token()
        if not access_token:
            logger.error("❌ 无法发送消息：access_token 获取失败")
            return False
        
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/send?access_token={access_token}"
        # 使用 ensure_ascii=False 防止中文被转义为 \uXXXX
        data = json.dumps({
            "touser": openid,
            "msgtype": "text",
            "text": {"content": content}
        }, ensure_ascii=False).encode('utf-8')
        
        try:
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            
            if result.get("errcode") == 0:
                logger.info(f"✅ 消息发送成功 (errcode=0)")
                return True
            elif result.get("errcode") == 40001:
                # token 过期，清缓存重试
                logger.warning("⚠️ token过期，重试中...")
                self._access_token = None
                return self._send_message(openid, content)
            else:
                logger.error(f"❌ 发送消息失败: {json.dumps(result, ensure_ascii=False)}")
                return False
        except Exception as e:
            logger.error(f"❌ 发送消息请求异常: {e}")
            return False
    
    def _send_typing(self, openid: str):
        """发送"正在输入"状态"""
        access_token = self._get_access_token()
        if not access_token:
            return
        
        url = f"https://api.weixin.qq.com/cgi-bin/message/custom/typing?access_token={access_token}"
        data = json.dumps({
            "touser": openid,
            "command": "Typing"
        }).encode()
        
        try:
            req = urllib.request.Request(url, data=data, headers={
                "Content-Type": "application/json"
            })
            urllib.request.urlopen(req, timeout=5)
        except:
            pass
    
    def _parse_xml(self, xml_data: str) -> Dict:
        """解析微信 XML 消息"""
        root = ET.fromstring(xml_data)
        result = {}
        for child in root:
            result[child.tag] = child.text
        return result
    
    def _build_xml_reply(self, from_user: str, to_user: str, content: str) -> str:
        """构建 XML 回复消息"""
        # content 中的中文直接使用即可，XML/HTTP 传输会正确处理 UTF-8
        return f"""<xml>
<ToUserName><![CDATA[{from_user}]]></ToUserName>
<FromUserName><![CDATA[{to_user}]]></FromUserName>
<CreateTime>{int(time.time())}</CreateTime>
<MsgType><![CDATA[text]]></MsgType>
<Content><![CDATA[{content}]]></Content>
</xml>"""
    
    # 最近处理过的消息缓存，用于去重（避免微信重试导致重复处理）
    # 使用类变量 + 锁保证线程安全
    _msg_lock = threading.Lock()
    # 正在处理中的消息（防并发重试）
    _processing_keys = set()
    
    def _is_duplicate_message(self, content: str) -> bool:
        """
        检查是否是重复消息（微信重试机制导致）
        使用30秒的去重窗口 + 处理中标记
        """
        import hashlib
        now = time.time()
        key = hashlib.md5(content.encode()).hexdigest()
        
        with self._msg_lock:
            # 初始化类变量
            if not hasattr(WeChatTestBot, '_recent_fingerprints'):
                WeChatTestBot._recent_fingerprints = {}
                WeChatTestBot._processing_keys = set()
            
            # 检查是否有正在处理中的相同消息
            if key in WeChatTestBot._processing_keys:
                logger.info(f"⏭️ 检测到正在处理中的消息，跳过")
                return True
            
            # 清理超过30秒的记录
            for k in list(WeChatTestBot._recent_fingerprints.keys()):
                if now - WeChatTestBot._recent_fingerprints[k] > 30:
                    del WeChatTestBot._recent_fingerprints[k]
            
            if key in WeChatTestBot._recent_fingerprints:
                logger.info(f"⏭️ 检测到重复消息（30秒内），跳过处理")
                return True
            
            # 标记为正在处理
            WeChatTestBot._processing_keys.add(key)
            WeChatTestBot._recent_fingerprints[key] = now
            return False
    
    def _finish_processing(self, content: str):
        """处理完成，清除处理中标记"""
        import hashlib
        key = hashlib.md5(content.encode()).hexdigest()
        with self._msg_lock:
            WeChatTestBot._processing_keys.discard(key)
    
    def _handle_message(self, xml_data: str) -> str:
        """处理微信消息，返回 success"""
        msg = self._parse_xml(xml_data)
        
        msg_type = msg.get("MsgType", "")
        from_user = msg.get("FromUserName", "")
        to_user = msg.get("ToUserName", "")
        content = msg.get("Content", "").strip()
        
        logger.info(f"📩 收到消息 [{from_user[:8]}...]: {content}")
        
        # 只处理文本消息
        if msg_type != self.MSG_TEXT:
            logger.info(f"⏭️ 跳过非文本消息: {msg_type}")
            return "success"
        
        # 去重检查：微信可能在未收到客服消息时重试POST
        if not content or self._is_duplicate_message(content):
            return "success"
        
        # 如果有 Agent，用 Agent 处理
        if self.agent:
            try:
                logger.info(f"🤖 Agent正在处理消息...")
                reply = self.agent(content, from_user)
                logger.info(f"🤖 Agent返回了 {len(reply)} 个字符")
                logger.info(f"📄 回复内容: {reply[:300]}")
                
                if reply:
                    logger.info(f"[WX_RESP] 回复给用户 [{from_user[:8]}...] 的完整内容:\n---\n{reply}\n---")
                    
                    # 先发送"正在输入"状态
                    self._send_typing(from_user)
                    
                    # 发起后台线程发送消息，但先立即返回 success
                    def _send_reply(reply_text, to_user):
                        try:
                            # 微信客服消息限制 2048 字节，中文字符每字约 3 字节
                            # 安全起见每块不超过 600 字符（约 1800 字节）
                            chunk_size = 600
                            for i in range(0, len(reply_text), chunk_size):
                                chunk = reply_text[i:i + chunk_size]
                                if i + chunk_size < len(reply_text):
                                    chunk += "…"
                                result = self._send_message(to_user, chunk)
                                logger.info(f"📤 发送消息块 {i//chunk_size + 1}: {'✅' if result else '❌'}")
                                if not result:
                                    logger.warning(f"⚠️ 消息块 {i//chunk_size + 1} 发送失败，重试...")
                                    time.sleep(0.5)
                                    result = self._send_message(to_user, chunk)
                                    logger.info(f"📤 重试: { '✅' if result else '❌'}")
                                time.sleep(0.3)
                            logger.info(f"📤 消息发送完成")
                        except Exception as e:
                            logger.error(f"❌ 异步发送消息异常: {e}")
                    
                    import threading
                    send_thread = threading.Thread(target=_send_reply, args=(reply, from_user))
                    send_thread.daemon = True
                    send_thread.start()
                else:
                    logger.warning("⚠️ Agent返回了空回复")
                
            except Exception as e:
                logger.error(f"❌ 处理消息失败: {e}")
            finally:
                self._finish_processing(content)
        
        return "success"
    
    def start(self):
        """启动 Web 服务器"""
        
        class RequestHandler(BaseHTTPRequestHandler):
            bot = self  # 类变量持有 bot 引用
            
            def log_message(self, format, *args):
                logger.info(f"🌐 {args[0]} {args[1]} {args[2]}")
            
            def do_GET(self):
                """处理微信验证请求 (GET)"""
                # 健康检查
                if self.path == "/health":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"status":"ok"}')
                    return
                
                # 不管路径，只要带 signature 参数就尝试验证
                params = {
                    "signature": self._get_param("signature"),
                    "timestamp": self._get_param("timestamp"),
                    "nonce": self._get_param("nonce"),
                    "echostr": self._get_param("echostr"),
                }
                
                echostr = params.get("echostr", "")
                
                # 如果有 echostr 说明是验证请求
                if echostr:
                    logger.info(f"🔐 收到验证请求")
                    
                    if self.bot._verify_signature(params):
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain")
                        self.end_headers()
                        self.wfile.write(echostr.encode())
                        logger.info("✅ 验证通过！")
                        return
                    else:
                        self.send_response(403)
                        self.end_headers()
                        logger.error("❌ 签名验证失败")
                        return
                
                # 没有 echostr，正常处理
                self.send_response(404)
                self.end_headers()
            
            def do_POST(self):
                """处理微信消息推送 (POST)"""
                # 不管路径是否带参数，只要是以 /wechat 开头就处理
                if not self.path.startswith("/wechat"):
                    self.send_response(404)
                    self.end_headers()
                    return
                
                content_length = int(self.headers.get("Content-Length", 0))
                xml_data = self.rfile.read(content_length).decode()
                
                # 验证签名
                params = {
                    "signature": self._get_param("signature"),
                    "timestamp": self._get_param("timestamp"),
                    "nonce": self._get_param("nonce"),
                }
                
                if not self.bot._verify_signature(params):
                    self.send_response(403)
                    self.end_headers()
                    return
                
                # 处理消息
                reply = self.bot._handle_message(xml_data)
                
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(reply.encode())
            
            def _get_param(self, name):
                """从 URL 查询参数中取值（使用 url 标准库）"""
                try:
                    from urllib.parse import urlparse, parse_qs
                    # 注意：self.path 可能包含查询参数
                    parsed = urlparse(self.path)
                    params = parse_qs(parsed.query, keep_blank_values=True)
                    vals = params.get(name, [""])
                    return vals[0] if vals else ""
                except Exception as e:
                    logger.warning(f"解析参数 {name} 失败: {e}")
                    return ""
        
        self._server = HTTPServer((self.host, self.port), RequestHandler)
        
        print()
        print("=" * 55)
        print("📱 微信测试号 Bot 已启动")
        print("=" * 55)
        print(f"   监听地址: http://{self.host}:{self.port}")
        print(f"   回调路径: http://{self.host}:{self.port}/wechat")
        print(f"   Token:    {self.token}")
        print()
        print("📋 下一步操作：")
        print("   1. 开通测试号：https://mp.weixin.qq.com/debug/cgi-bin/sandbox")
        print("   2. 扫码登录，复制 appID 和 appsecret")
        print("   3. 用 ngrok 等工具将本机映射到公网")
        print("   4. 将回调 URL 和 Token 填回测试号配置页")
        print("   5. 用微信关注测试号，发送消息")
        print("=" * 55)
        print()
        
        logger.info("等待微信消息...")
        
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            print()
            logger.info("👋 服务已停止")
            self._server.server_close()
    
    def stop(self):
        """停止服务"""
        if self._server:
            self._server.shutdown()


def run_with_agent(agent, config: dict = None):
    """
    便捷启动函数：绑定基金 Agent 并启动微信测试号服务
    
    Args:
        agent: FundAgent 实例
        config: 包含 wechat_test 配置的字典
    """
    # 从环境变量或配置读取
    test_config = (config or {}).get("wechat_test", {})
    
    app_id = test_config.get("app_id") or os.getenv("WX_APP_ID")
    app_secret = test_config.get("app_secret") or os.getenv("WX_APP_SECRET")
    token = test_config.get("token") or os.getenv("WX_TOKEN", "fundagent123")
    port = test_config.get("port", 9000)
    
    if not app_id or not app_secret:
        print("❌ 未配置微信测试号信息！")
        print()
        print("请按以下步骤操作：")
        print()
        print("1. 打开微信测试号开通页面：")
        print("   https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login")
        print()
        print("2. 用微信扫码登录")
        print()
        print("3. 在页面上找到 appID 和 appsecret，复制它们")
        print()
        print("4. 设置环境变量或修改配置文件：")
        print("   export WX_APP_ID='你的appID'")
        print("   export WX_APP_SECRET='你的appsecret'")
        print("   export WX_TOKEN='自定义token'")
        print()
        print("   或在 config.yaml 中添加：")
        print("   wechat_test:")
        print("     app_id: '你的appID'")
        print("     app_secret: '你的appsecret'")
        print("     token: 'fundagent123'")
        print("     port: 9000")
        print()
        sys.exit(1)
    
    def handler(text, user_id):
        """消息处理器"""
        return agent.process_message(text, user_id)
    
    bot = WeChatTestBot(
        app_id=app_id,
        app_secret=app_secret,
        token=token,
        agent=handler,
        host="0.0.0.0",
        port=port,
    )
    
    print()
    print("🐱 「巧克力」已就绪！")
    print()
    
    bot.start()
    return bot


if __name__ == "__main__":
    # 独立运行模式
    print("📱 微信测试号模式")
    print()
    print("请先设置环境变量：")
    print("  export WX_APP_ID='你的appID'")
    print("  export WX_APP_SECRET='你的appsecret'")
    print("  export WX_TOKEN='自定义token'")
    print()
    print("然后启动服务，并用 ngrok 映射公网地址")
    print()
    print("需要 ngrok: https://ngrok.com/download")
    print()
