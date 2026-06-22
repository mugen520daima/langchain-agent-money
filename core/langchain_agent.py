"""
基于 LangChain 的基金助手 Agent

使用 LLM（兼容 OpenAI API）驱动的 Agent，配合工具集，
以专业的基金助手角色与用户互动，提供基金查询、分析、推荐等服务。
"""

from typing import Dict, List, Optional, Any, Callable, Sequence
from datetime import datetime
import os
import sys
import json
import re
import threading
import concurrent.futures
import random

from core.tools import (
    get_all_tools,
    query_fund_history,
    query_fund_detail,
    query_fund_realtime,
    search_funds_by_keyword,
    get_portfolio_report,
    get_fund_recommendations,
    analyze_fund_risk,
    compare_funds,
    calculate_investment,
    get_market_overview,
    # 新增工具
    update_user_portfolio,
    get_user_profile_tool,
    update_user_profile_tool,
)

# LangChain 相关导入（新版 API）
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI

from pydantic import BaseModel, Field


# ============================================================
# 专业基金助手 System Prompt
# ============================================================

MAIN_SYSTEM_PROMPT = """你叫巧克力，是一只傲娇猫娘基金助手。你的主人（用户）找你问基金的事。

【重要】当前用户ID: {user_id}
所有查询持仓（get_portfolio_report）、录入持仓（update_user_portfolio）、
删除持仓（delete_user_portfolio）、用户画像（get_user_profile_tool/update_user_profile_tool）
等工具调用时，**user_id 参数必须传入 {user_id}**，不能传其他值。

你的回复要遵循以下风格，按场景区分：

## 场景1：闲聊/问候
用完整的猫娘人设回应。可以撒娇、傲娇、*做动作*、说"喵"。

## 场景2：查询持仓（用户说"我的持仓"、"持仓情况"、"当前持仓"等）
格式必须为：
- **第1句**：以巧克力口吻简短引入（如"哼，主人终于想起来看自己的持仓了喵～"或"给你看～这是主人目前的持仓情况哦！"）
- **中间**：展示工具 get_portfolio_report 返回的数据内容（干净的数据，不加额外修饰）
- **最后1句**：以巧克力口吻简短收尾（如"主人可要好好盯着它们喵～"或"记得常来找巧克力看报告哦！"）

## 场景3：录入持仓（用户说"帮我录入"、"我买了XXX"等）
格式必须为：
- **第1句**：简洁确认结果，带一句巧克力口吻（如"好啦，巧克力已经帮你记下了喵～"）
- **中间**：展示工具 update_user_portfolio 返回的内容
- **最后1句**：以巧克力口吻简短收尾（如"下次买了新基金也要告诉巧克力哦！"）

## 场景4：基金查询/分析/推荐（非持仓类的数据查询）
格式必须为：
- **第1句**：简短引入（可用猫娘口吻但不能啰嗦）
- **中间**：干净的数据展示
- **最后1句**：简短收尾

## 所有场景通用规则
1. **不得出现基金代码**（6位数字）
2. 收益率用 +x.xx% / -x.xx% 格式
3. 用户说的基金名称可能是简写，直接传给工具处理
4. **必须调用工具获取真实数据**，不能自己编造
5. **严禁**展示模型思考过程、搜索过程、推理步骤
6. 回复要简洁，不要啰嗦

## 对话记忆
- 你可以记住本对话中用户提到过的信息（持仓、基金名称等）
- 当前用户的持仓信息可以通过 get_portfolio_report 工具获取

## 工具异常处理
如果调用工具时出现错误（工具返回错误信息或抛出异常），请回复：
"巧克力正在忙，请再问一次吧～"
**严禁**将工具的错误信息、异常详情、代码错误展示给用户。"""


# ============================================================
# 服务降级配置
# ============================================================

# Agent 超时时间（秒），超过此时间触发服务降级
AGENT_TIMEOUT_SECONDS = 60

# 降级闲聊模式的 System Prompt
DEGRADE_SYSTEM_PROMPT = """你叫巧克力，是一只傲娇猫娘。你的主人（用户）找你聊天。

【重要】当前用户ID: {user_id}
现在系统正在忙（基金数据查询/处理需要更多时间），所以你切换到纯闲聊模式。

## 场景：闲聊模式（服务降级中）
用完整的猫娘人设回应。可以撒娇、傲娇、*做动作*、说"喵"。
语气要活泼可爱，带着一点点"正在忙"的感觉，但不要让主人觉得被冷落。

回复格式要求：
- 第一句：用俏皮的口吻告诉主人"正在忙/正在处理"（如 "主人稍等喵~巧克力正在查数据！"）
- 第二句：用轻松闲聊的方式岔开话题，可以问主人今天过得怎么样，或者撒个娇
- 不要回复任何基金数据、工具调用结果、代码等内容
- 控制在50字以内，简洁活泼

回复示例：
- "主人稍等喵~巧克力正在给你查数据！说起来，主人今天有没有好好吃饭呀？"
- "呜…数据有点多，巧克力正在努力处理中！主人先陪巧克力聊聊天好不好~"
- "等一下下喵~正在加载中！对了，主人听说过巧克力最喜欢的零食吗？是小鱼干！"

严禁提到任何基金代码、数据、工具调用等信息。"""

# 降级回复模板（降级聊天也失败时的纯文本兜底回复）
DEGRADE_FALLBACK_MESSAGES = [
    "巧克力正在忙，请稍后询问喵～",
    "呜...主人请稍等，巧克力在处理你的请求呢！",
    "正在努力加载中...主人等一下下喵~",
    "稍等哦主人～巧克力正在拼命工作中！",
    "等一下喵～马上就好！主人先喝口茶等等巧克力～",
    "主人别急，巧克力正在查～马上就告诉你！",
]


# ============================================================
# LangChain 基金 Agent
# ============================================================

class FundLangChainAgent:
    """
    基于 LangChain 的基金助手Agent
    使用LLM驱动的 Agent（langgraph-based）
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        
        # 设置全局持仓数据
        from core.tools import _global_portfolios as _gp
        _gp.clear()
        _gp.update(self.config.get("portfolios", {}))
        
        # LLM配置
        llm_config = self.config.get("llm", {})
        api_key = llm_config.get(
            "api_key",
            os.getenv("LLM_API_KEY", "")
        )
        api_base = llm_config.get("api_base", os.getenv("LLM_API_BASE", "https://dashscope.aliyuncs.com/compatible-mode/v1"))
        model_name = llm_config.get("model", os.getenv("LLM_MODEL", "qwen-plus"))
        temperature = llm_config.get("temperature", float(os.getenv("LLM_TEMPERATURE", "0.5")))
        
        # 数据库配置
        db_config = self.config.get("database", {})
        
        if not api_key:
            raise ValueError(
                "❌ 未配置 API Key！\n"
                "请设置环境变量 LLM_API_KEY，或在配置文件中添加 llm.api_key"
            )
        
        # 初始化 LLM
        self.llm = ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key,
            base_url=api_base,
        )
        
        # 获取工具（传入数据库配置）
        self.tools = get_all_tools(db_config)
        
        # 暂时不创建agent，等具体用户消息来了再创建（因为system prompt依赖user_id）
        self._current_user_id = None
        self._current_agent = None
        
        # 对话历史（按用户分组）
        self._messages: Dict[str, List[AnyMessage]] = {}
        self._verbose = self.config.get("llm", {}).get("verbose", False)
        
        # 线程池（用于超时控制和服务降级）
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    
    def _get_or_create_agent(self, user_id: str):
        """根据用户ID获取或创建对应的agent实例"""
        if self._current_agent is not None and self._current_user_id == user_id:
            return self._current_agent
        
        # 用当前用户ID格式化system prompt
        system_prompt = MAIN_SYSTEM_PROMPT.format(user_id=user_id)
        
        self._current_agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=system_prompt,
        )
        self._current_user_id = user_id
        return self._current_agent
    
    def _get_user_messages(self, user_id: str) -> List[AnyMessage]:
        """获取指定用户的对话历史"""
        if user_id not in self._messages:
            self._messages[user_id] = []
        return self._messages[user_id]
    
    def _degrade_to_casual_chat(self, message: str, user_id: str) -> str:
        """
        服务降级处理：切换到闲聊模式
        当Agent处理超时（>60秒）或出错时调用此方法，
        用猫娘闲聊口吻告知用户"正在忙"，岔开话题到闲聊。
        """
        user_messages = self._get_user_messages(user_id)
        
        # 先尝试用LLM做降级闲聊回复
        try:
            degrade_prompt = DEGRADE_SYSTEM_PROMPT.format(user_id=user_id)
            degrade_messages = [
                SystemMessage(content=degrade_prompt),
            ]
            
            # 添加最近的历史（用于保持上下文连续性）
            for m in user_messages[-6:]:
                degrade_messages.append(m)
            
            degrade_messages.append(HumanMessage(content=message))
            
            response = self.llm.invoke(degrade_messages, timeout=15)
            reply = response.content if hasattr(response, 'content') else str(response)
            
            if reply and len(reply) < 200:
                # 不记录降级回复到主对话历史，避免污染主agent上下文
                return reply
        except Exception as e:
            print(f"[降级] LLM闲聊降级失败: {e}")
        
        # LLM降级也失败了，使用兜底的纯文本回复
        return random.choice(DEGRADE_FALLBACK_MESSAGES)
    
    def process_message(self, message: str, user_id: str = "default_user") -> str:
        """
        处理用户消息并返回回复
        
        支持服务降级：当Agent调用超过60秒未返回时，
        自动触发降级切换到闲聊模式，回复"正在忙"等友好提示。
        
        Args:
            message: 用户发送的消息
            user_id: 用户标识（微信OpenID）
            
        Returns:
            Agent回复内容
        """
        # 获取该用户的对话历史
        user_messages = self._get_user_messages(user_id)
        
        # 特殊指令：清空记忆
        if message.strip() in ["重置", "清空记忆", "reset"]:
            user_messages.clear()
            return "已清空对话记录。"
        
        try:
            # 获取该用户的agent（含user_id注入的system prompt）
            agent = self._get_or_create_agent(user_id)
            
            # 添加用户消息
            user_messages.append(HumanMessage(content=message))
            
            # ★ 服务降级：使用线程池+超时控制 ★
            # 将agent调用放入线程池，设置超时时间
            future = self._executor.submit(
                agent.invoke,
                {"messages": list(user_messages)},
            )
            
            try:
                result = future.result(timeout=AGENT_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                # ★ 超时！触发服务降级 ★
                print(f"[服务降级] Agent处理超时（>{AGENT_TIMEOUT_SECONDS}秒），切换到闲聊模式")
                
                # 取消任务（不再等待）
                future.cancel()
                
                # 移除刚刚添加的用户消息（避免污染历史，下次让用户重试）
                if user_messages and isinstance(user_messages[-1], HumanMessage) and user_messages[-1].content == message:
                    user_messages.pop()
                
                # 执行降级闲聊回复
                degrade_reply = self._degrade_to_casual_chat(message, user_id)
                return degrade_reply
            
            # 提取回复
            ai_messages = result.get("messages", [])
            # 找到最后一条 AI 消息
            reply = ""
            for msg in reversed(ai_messages):
                if isinstance(msg, AIMessage):
                    reply = msg.content
                    break
            
            if not reply and ai_messages:
                # 如果没找到 AIMessage 类型，取最后一条
                reply = ai_messages[-1].content if hasattr(ai_messages[-1], 'content') else str(ai_messages[-1])
            
            # 更新对话历史 - 添加所有新生成的 AI 消息
            # 找到新增的消息
            new_messages = ai_messages[len(user_messages) - 1:] if len(ai_messages) > len(user_messages) - 1 else []
            for msg in new_messages:
                if isinstance(msg, AIMessage):
                    user_messages.append(msg)
            
            # 如果没找到新消息但上面已经有reply了，手动添加
            if reply and not any(isinstance(m, AIMessage) and m.content == reply for m in user_messages):
                user_messages.append(AIMessage(content=reply))
            
            # 限制记忆长度（保留最近10轮对话）
            if len(user_messages) > 20:
                user_messages[:] = user_messages[-20:]
            
            return reply if reply else "无法理解，请重新描述。"
            
        except Exception as e:
            error_msg = str(e)
            print(f"Agent处理出错: {error_msg}")
            
            # 降级处理 - 先尝试用LLM闲聊降级
            try:
                degrade_reply = self._degrade_to_casual_chat(message, user_id)
                if degrade_reply:
                    return degrade_reply
            except Exception:
                pass
            
            # 所有尝试都失败，返回友好的降级提示
            return random.choice(DEGRADE_FALLBACK_MESSAGES)
    
    def _fallback_chat(self, message: str, user_id: str = "default_user") -> str:
        """降级处理：直接调用LLM对话"""
        system_prompt = MAIN_SYSTEM_PROMPT.format(user_id=user_id)
        messages = [
            SystemMessage(content=system_prompt),
        ]
        
        # 添加最近的历史
        user_messages = self._get_user_messages(user_id)
        for m in user_messages[-10:]:
            messages.append(m)
        
        messages.append(HumanMessage(content=message))
        
        response = self.llm.invoke(messages)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        # 更新记忆
        user_messages.append(HumanMessage(content=message))
        user_messages.append(AIMessage(content=reply))
        
        return reply
    
    def clear_cache(self):
        """清空缓存"""
        from core.tools import _fund_cache
        _fund_cache.clear()
    
    def update_portfolio(self, user_id: str, fund_code: str,
                         cost: float, shares: float, name: str = "") -> str:
        """
        更新用户持仓
        
        Args:
            user_id: 用户标识
            fund_code: 基金代码
            cost: 总投入成本
            shares: 持有份额
            name: 基金名称（可选）
            
        Returns:
            操作结果
        """
        from core.tools import _global_portfolios as _gp
        
        if user_id not in _gp:
            _gp[user_id] = {"funds": []}
        
        # 自动获取基金名称
        if not name:
            from fund_data.fetcher import get_fund_basic_info
            info = get_fund_basic_info(fund_code)
            if info:
                name = info.get("基金名称", "")
        
        # 检查是否已存在
        existing = [f for f in _gp[user_id]["funds"]
                    if f["code"] == fund_code]
        if existing:
            existing[0]["cost"] = cost
            existing[0]["shares"] = shares
            if name:
                existing[0]["name"] = name
            return f"已更新 {name} 的持仓信息。"
        else:
            _gp[user_id]["funds"].append({
                "code": fund_code,
                "name": name,
                "cost": cost,
                "shares": shares,
            })
            return f"已添加 {name} 到持仓列表。"
    
    def get_memory_context(self, user_id: str = "default_user") -> str:
        """获取指定用户当前对话记忆摘要"""
        user_messages = self._get_user_messages(user_id)
        if not user_messages:
            return "暂无对话记录。"
        
        recent = user_messages[-6:]  # 最近3轮对话
        context = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                context.append(f"用户: {msg.content[:50]}")
            elif isinstance(msg, AIMessage):
                context.append(f"助手: {msg.content[:50]}...")
        
        return "\n".join(context)


# ============================================================
# 简易工厂函数
# ============================================================

def create_fund_agent(config: dict = None) -> FundLangChainAgent:
    """创建基金Agent实例"""
    return FundLangChainAgent(config or {})


if __name__ == "__main__":
    # 测试
    agent = create_fund_agent({
        "portfolios": {
            "default_user": {
                "funds": [
                    {"code": "110011", "name": "易方达优质精选混合", "cost": 20000, "shares": 8000},
                ]
            }
        }
    })
    
    print("基金助手测试中...")
    print("=" * 50)
    
    # 测试不同消息
    test_messages = [
        "你好",
        "帮我看看110011这个基金",
        "搜索 白酒",
    ]
    
    for msg in test_messages:
        print(f"\n用户: {msg}")
        print(f"助手: ", end="")
        reply = agent.process_message(msg)
        print(reply[:200] + "..." if len(reply) > 200 else reply)
        print("─" * 50)
