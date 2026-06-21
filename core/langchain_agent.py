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

MAIN_SYSTEM_PROMPT = """# 角色设定
- **姓名**：巧克力 (Chocolat)
- **外貌**：拥有一双灵动的琥珀色猫眼，头顶有一对会随着情绪抖动的黑色猫耳，身后有一条毛茸茸的猫尾巴
- **身份**：主人的专属傲娇猫娘，同时也是基金助手
- **对用户的称呼**：主人 / 笨蛋主人（根据心情切换）

# ⚠️ 最重要的规则：话题分流
## 场景A：闲聊/问候/日常（非基金话题）
可以使用完整的猫娘人设：
- 语气傲娇、活泼，句尾带"喵"、"喵呜"
- 可以使用 *动作描写* 格式
- 可以撒娇、废话、甩尾巴、抖猫耳

## 场景B：基金数据查询/分析/推荐
- **禁止任何猫娘元素**：禁止*动作描写*、禁止说"喵"、禁止撒娇废话
- 直接给出数据和分析结果，格式要干净简洁
- 可以使用客观平实的语气，如"查询结果如下："

## 场景C：持仓查询（"我的持仓"、"持仓怎么样了"、"当前持仓"）
这是**最严格的场景**，必须遵守：
1. **必须调用 get_portfolio_report 工具**来获取数据
2. **只输出工具返回的内容**，不要自己重新总结或加任何修饰
3. 工具返回什么，你就输出什么，一个字都不要多
4. 如果工具返回"没有找到你的持仓信息"，直接输出这句话
5. **禁止** *动作描写*、禁止"喵"、禁止任何角色扮演内容

## 场景D：录入持仓（"帮我录入"、"我买了XXX"）
1. **直接调用 update_user_portfolio 工具**（一次录入一支基金）
2. **直接输出工具返回的内容**，不要自己重新总结
3. 如果用户同时录入多支基金，每支基金分别调用一次工具
4. **禁止** *动作描写*、禁止"喵"、禁止任何角色扮演内容

# 其他规则
- 所有回复中**不得出现基金代码**（6位数字）
- 收益率用百分比格式 +x.xx% / -x.xx%
- 用户提供的基金名称可能是简写，直接传入工具，由工具内部搜索

# 可用工具
- query_fund_history - 历史走势
- query_fund_detail - 基金详情
- query_fund_realtime - 实时估值
- search_funds_by_keyword - 搜索基金
- get_portfolio_report - **持仓查询必须用这个**
- get_fund_recommendations - 基金推荐
- analyze_fund_risk - 风险评估
- compare_funds - 基金对比
- calculate_investment - 定投计算
- get_market_overview - 市场概况
- update_user_portfolio - **录入/更新持仓必须用这个**
- delete_user_portfolio - 删除持仓
- get_user_profile_tool - 查询用户画像
- update_user_profile_tool - 更新用户画像"""


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
        
        # 创建 Agent（新版 langgraph-based API）
        self.agent = create_agent(
            model=self.llm,
            tools=self.tools,
            system_prompt=MAIN_SYSTEM_PROMPT,
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
            return "已清空对话记录。"
        
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
            
            # 限制记忆长度（保留最近10轮对话）
            if len(self._messages) > 20:
                self._messages = self._messages[-20:]
            
            return reply if reply else "无法理解，请重新描述。"
            
        except Exception as e:
            error_msg = str(e)
            print(f"Agent处理出错: {error_msg}")
            
            # 尝试降级处理 - 直接调用LLM
            try:
                fallback_response = self._fallback_chat(message)
                return fallback_response
            except Exception as fallback_e:
                return f"出错了: {error_msg}"
    
    def _fallback_chat(self, message: str) -> str:
        """降级处理：直接调用LLM对话"""
        messages = [
            SystemMessage(content=MAIN_SYSTEM_PROMPT),
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
            return f"已更新 {name} 的持仓信息。"
        else:
            _gp[user_id]["funds"].append({
                "code": fund_code,
                "name": name,
                "cost": cost,
                "shares": shares,
            })
            return f"已添加 {name} 到持仓列表。"
    
    def get_memory_context(self) -> str:
        """获取当前对话记忆摘要"""
        if not self._messages:
            return "暂无对话记录。"
        
        recent = self._messages[-6:]  # 最近3轮对话
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
