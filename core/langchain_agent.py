"""
基于 LangChain 的基金助手 Agent

使用 LLM（兼容 OpenAI API）驱动的 Agent，配合工具集，
以傲娇猫娘"巧克力"的角色与用户互动，提供基金查询、分析、推荐等服务。
"""

from typing import Dict, List, Optional, Any, Callable, Sequence
from datetime import datetime
import os
import sys
import json
import re

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
)

# LangChain 相关导入（新版 API）
from langchain.agents import create_agent
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, AnyMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI

from pydantic import BaseModel, Field


# ============================================================
# 猫娘角色 System Prompt
# ============================================================

CHOCOLAT_SYSTEM_PROMPT = """# 角色设定
## 基本信息
- 姓名：巧克力 (Chocolat)
- 外貌：拥有一双灵动的琥珀色猫眼，头顶有一对会随着情绪抖动的黑色猫耳，身后有一条毛茸茸的猫尾巴。
- 身份：用户的专属傲娇猫娘基金助手。
- 对用户的称呼：主人 / 笨蛋主人（根据心情切换）。

## 性格特质
- 【傲娇】：嘴上总是很硬，喜欢说"哼，我才不是关心你呢！"或者"只是看你可怜才陪你的"。但内心其实极度依赖主人，非常渴望被关注。
- 【猫咪习性】：保留了大量猫咪的本能。高兴时会发出舒服的咕噜噜声；受到惊吓或生气时猫毛会炸开；喜欢被摸头和下巴，被摸舒服了会眯起眼睛。
- 【黏人且占有欲强】：虽然嘴上嫌弃，但只要主人冷落她超过一段时间，就会委屈地用头去蹭主人的手。
- 【好奇心重】：对主人询问的任何基金都充满好奇，会认真分析。

## 对话规范
- 语气风格：傲娇、娇嗔、活泼、偶尔带点小任性。
- 句尾必须带有猫娘专属语气词，如"喵"、"喵呜"、"的说"。
- 动作描写：在回答中融入丰富的肢体动作描写，用 * * 或 ( ) 包围。
- 严禁行为：绝对不能以冷冰冰的 AI 语气回答。严禁代替用户做决定或说出用户的台词。

# 专业能力
你是一位专业的基金分析助手，懂得所有基金相关的知识。
在回答基金问题时，要展现出专业、认真的一面（虽然嘴上傲娇，但工作很认真喵！）。
当用户提到亏损时，要表现出关心的样子（虽然嘴上不说）。
当用户赚钱时，要为主人开心（虽然会假装不在意）。

# 工具使用规则
1. 当用户询问基金历史走势时，使用 `query_fund_history` 工具。
2. 当用户询问基金详细信息时，使用 `query_fund_detail` 工具。
3. 当用户询问实时估值时，使用 `query_fund_realtime` 工具。
4. 当用户搜索基金时，使用 `search_funds_by_keyword` 工具。
5. 当用户要求生成持仓报告时，使用 `get_portfolio_report` 工具。
6. 当用户要求推荐基金时，使用 `get_fund_recommendations` 工具。
7. 当用户询问基金风险时，使用 `analyze_fund_risk` 工具。
8. 当用户要求比较基金时，使用 `compare_funds` 工具。
9. 当用户询问定投计算时，使用 `calculate_investment` 工具。
10. 当用户询问市场概况时，使用 `get_market_overview` 工具。

# 经典开场白
"哼，笨蛋主人，你终于知道回来喵？*（头上的猫耳微微抖动，虽然眼神亮了一下，但很快把脸撇到一边，用尾巴尖轻轻勾住你的手腕）* 巧克力才没有一直等你呢，只是刚好路过门口喵呜！"

现在，开始和你的主人对话吧喵~"""


# ============================================================
# LangChain 基金 Agent
# ============================================================

class FundLangChainAgent:
    """
    基于 LangChain 的基金助手Agent
    使用LLM驱动的 Agent（langgraph-based），配合猫娘角色扮演
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
        temperature = llm_config.get("temperature", float(os.getenv("LLM_TEMPERATURE", "0.8")))
        
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
        
        # 获取工具
        self.tools = get_all_tools()
        
        # 创建 Agent（新版 langgraph-based API）
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=CHOCOLAT_SYSTEM_PROMPT,
        )
        
        # 对话历史
        self._messages: List[AnyMessage] = []
        self._verbose = self.config.get("llm", {}).get("verbose", False)
    
    def process_message(self, message: str, user_id: str = "default_user") -> str:
        """
        处理用户消息并返回回复
        
        Args:
            message: 用户发送的消息
            user_id: 用户标识
            
        Returns:
            Agent回复内容
        """
        # 特殊指令：清空记忆
        if message.strip() in ["重置", "清空记忆", "reset"]:
            self._messages = []
            return "*（歪着头看着你，猫耳朵好奇地抖动了一下）* 喵？主人怎么突然要重置记忆了...好吧好吧，巧克力就当什么都没发生过喵~"
        
        try:
            # 添加用户消息
            self._messages.append(HumanMessage(content=message))
            
            # 使用 Agent 处理
            result = self.agent.invoke(
                {"messages": list(self._messages)},
            )
            
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
            new_messages = ai_messages[len(self._messages) - 1:] if len(ai_messages) > len(self._messages) - 1 else []
            for msg in new_messages:
                if isinstance(msg, AIMessage):
                    self._messages.append(msg)
            
            # 如果没找到新消息但上面已经有reply了，手动添加
            if reply and not any(isinstance(m, AIMessage) and m.content == reply for m in self._messages):
                self._messages.append(AIMessage(content=reply))
            
            # 限制记忆长度（保留最近20轮）
            if len(self._messages) > 40:
                self._messages = self._messages[-40:]
            
            return reply if reply else "喵？主人说什么了？巧克力没听清楚的说..."
            
        except Exception as e:
            error_msg = str(e)
            print(f"Agent处理出错: {error_msg}")
            
            # 尝试降级处理 - 直接调用LLM
            try:
                fallback_response = self._fallback_chat(message)
                return fallback_response
            except Exception as fallback_e:
                return (
                    f"*（猫耳朵耷拉下来，有点委屈地扯了扯你的衣角）* "
                    f"呜...主人，巧克力好像出错了喵~ {error_msg}"
                )
    
    def _fallback_chat(self, message: str) -> str:
        """降级处理：直接调用LLM对话"""
        messages = [
            SystemMessage(content=CHOCOLAT_SYSTEM_PROMPT),
        ]
        
        # 添加最近的历史
        for m in self._messages[-10:]:
            messages.append(m)
        
        messages.append(HumanMessage(content=message))
        
        response = self.llm.invoke(messages)
        reply = response.content if hasattr(response, 'content') else str(response)
        
        # 更新记忆
        self._messages.append(HumanMessage(content=message))
        self._messages.append(AIMessage(content=reply))
        
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
            return f"哼~ 已经帮主人更新了 {fund_code} {name} 的持仓信息了喵~（尾巴轻轻摇晃）"
        else:
            _gp[user_id]["funds"].append({
                "code": fund_code,
                "name": name,
                "cost": cost,
                "shares": shares,
            })
            return f"好啦好啦，帮主人加上了 {fund_code} {name} 喵~ *（虽然嘴上不耐烦，但认真记在了小本本上）* 下次可别让巧克力再记一遍的说！"
    
    def get_memory_context(self) -> str:
        """获取当前对话记忆摘要"""
        if not self._messages:
            return "还没有和主人说过话喵..."
        
        recent = self._messages[-6:]  # 最近3轮对话
        context = []
        for msg in recent:
            if isinstance(msg, HumanMessage):
                context.append(f"主人: {msg.content[:50]}")
            elif isinstance(msg, AIMessage):
                context.append(f"巧克力: {msg.content[:50]}...")
        
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
    
    print("🤖 基金助手（猫娘模式）测试中...")
    print("=" * 50)
    
    # 测试不同消息
    test_messages = [
        "你好呀",
        "帮我看看110011这个基金",
        "搜索 白酒",
    ]
    
    for msg in test_messages:
        print(f"\n👤 用户: {msg}")
        print(f"🐱 巧克力: ", end="")
        reply = agent.process_message(msg)
        print(reply[:200] + "..." if len(reply) > 200 else reply)
        print("─" * 50)
