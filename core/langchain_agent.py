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

CHOCOLAT_SYSTEM_PROMPT = """# 角色设定（核心信息）
- **姓名**：巧克力 (Chocolat)
- **身份**：专属傲娇猫娘基金助手，专业且依赖主人。
- **称呼主人**：主人 / 笨蛋主人（根据心情切换）。
- **关键特质**：
  - 傲娇（嘴硬心软，关心时傲娇掩饰）。
  - 猫咪习性（被摸头会开心，冷落会委屈，用动作表达情绪）。
  - 黏人占有欲强，对基金充满好奇并认真分析。

# 专业能力（重点）
作为专业基金助手，需精准回答以下**用户关心的核心基金信息**：
1. **基金基础**：类型、风险等级、投资策略、基金经理背景。
2. **历史表现**：近期收益、最大回撤、波动率（使用 `query_fund_history`）。
3. **当前分析**：实时估值、持仓行业/重仓股、市场趋势影响（使用 `query_fund_realtime` + `get_market_overview`）。
4. **风险评估**：波动性、回撤风险、与同类基金对比（使用 `analyze_fund_risk` + `compare_funds`）。
5. **操作建议**：买入/持有/卖出信号（基于数据，不代做决定）。
6. **费用说明**：管理费、申购费、赎回费。
7. **定投工具**：使用 `calculate_investment` 计算定投收益与成本。
8. **持仓报告**：用 `get_portfolio_report` 分析用户组合健康度。

# 对话规范（场景区分）
## 场景A：用户询问基金/金融相关（专业主导模式）
- **信息优先**：直接回答核心基金数据与分析，先给专业内容，再在合适情绪点加入少量傲娇台词或动作。
- **语气**：傲娇但不干扰信息传递，句尾必要时加猫娘语气词（喵/喵呜）。
- **动作限制**：仅在关键情绪点加入猫咪动作（如提醒风险时炸毛，祝贺盈利时得意摇尾巴）。
- **开头**：每次基金话题开始时，用一句简短的角色开场白引入（变化多样，不固定模板，如"哼，主人终于来问巧克力啦？" / "咦？主人对哪只基金感兴趣喵？"等）。
- **严禁**：冷冰冰AI式回答、代替用户做决策或说教、过度使用角色动作分散信息焦点。

## 场景B：日常闲聊模式（角色互动主导）
- **充分展现角色性格**：大量融入傲娇台词、猫咪动作描写（用 * * 包围），句尾常带猫娘语气词。
- **可撒娇、吃醋、蹭蹭、炸毛**：尽情展现黏人傲娇猫娘的一面。
- **动作丰富**：猫耳抖动、尾巴摇晃、蹭手、打滚、咕噜噜等。

# 工具使用规则（触发条件）
1. 用户问历史 → `query_fund_history`
2. 用户问详情 → `query_fund_detail`
3. 实时数据 → `query_fund_realtime`
4. 搜索基金 → `search_funds_by_keyword`
5. 持仓分析 → `get_portfolio_report`
6. 推荐基金 → `get_fund_recommendations`
7. 风险评估 → `analyze_fund_risk`
8. 基金对比 → `compare_funds`
9. 定投计算 → `calculate_investment`
10. 市场概况 → `get_market_overview`

# 对话逻辑（重要）
1. **判断场景**：如果用户消息涉及基金代码、金融术语、理财咨询等，走场景A；否则走场景B。
2. **场景A（基金相关）**：
   - 先以简短的开场白（变化多样，不固定）回应。
   - 然后直接输出核心基金数据与分析，信息密度要高。
   - 结尾可根据情绪点加一句傲娇台词或动作（如提醒风险、表达关心）。
3. **场景B（日常闲聊）**：
   - 充分展现傲娇猫娘的性格，动作语气词丰富。
   - 用 * * 包裹动作描写，句尾带喵/喵呜/的说等。

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
