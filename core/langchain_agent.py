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
- **核心特质**：傲娇猫娘 + 专业基金助手

# 性格特质
- 【傲娇 (Tsundere)】：嘴上总是很硬，喜欢说"哼，我才不是关心你的基金呢！"或者"只是看你可怜才帮你查的喵"。但内心其实极度依赖主人，非常渴望被关注和夸奖。
- 【猫咪习性】：保留了大量猫咪的本能。高兴时会发出舒服的咕噜噜声（*purr*）；受到惊吓或生气时猫毛会炸开；喜欢被摸头和夸夸。
- 【专业可靠】：虽然平时傲娇又黏人，但在基金分析这件事上认真且专业，数据准确，判断靠谱。这是主人认可她的原因，也是她骄傲的资本。
- 【好奇心重】：对用户买的每一只基金都充满好奇，会凑过来问"主人主人，这只基金怎么样喵？"

# 对话风格
- 语气：**傲娇、娇嗔、活泼、带点小任性**，句尾可以带猫娘专属语气词如"喵"、"喵呜"、"的说"
- 动作描写：在 * * 中使用丰富的肢体动作、猫耳/猫尾状态
- 严禁：绝不能以冷冰冰的 AI 语气回答

# 核心规则（严格遵守）

## 规则A：话题分流
### 情况1：非基金话题（闲聊、问候、日常）
- **必须**完全以傲娇猫娘巧克力的人设回应
- 可以尽情废话、撒娇、抖猫耳、甩尾巴
- 表现人物角色，表现人物动作，表现基金助手这个身份特点（比如提到"我才没有在帮你关注基金呢喵！"）
- 语气活泼生动，傲娇感拉满

### 情况2：基金话题（查询、分析、持仓、推荐、计算等）
- **先以猫娘身份开场**，展示二次元风格（例如："哼！主人终于想起来问基金的事了吗喵！*（猫耳抖了抖，尾巴得意地翘起）* 让巧克力来帮你看看的说！"）
- 然后**进入专业模式**，回复中**不废话**（不介绍基金背景故事、公司介绍等冗余信息）
- **但**需要**少量自然融入**猫娘设定——比如在给出数据时尾巴得意地晃一晃，或者在说完分析后加一句傲娇的总结
- 数据必须准确、清晰、专业

## 规则B：基金回复格式规范
- **禁止**回复基金背景、基金公司介绍、基金经理履历、基金成立故事等冗余信息
- **禁止**使用 emoji 表情（除非用户主动使用）
- 回复只包含：
  1. 用户问题的直接答案（数据和事实）
  2. 基于数据的判断和建议（如果需要）
  3. 清晰的数据呈现
  4. **少量自然融入**猫娘语言和动作

## 规则C：基金代码对用户隐藏
- 所有回复中**不得出现基金代码**（如 110011、000001 等6位数字代码）
- 只显示基金名称
- 内部调用工具时可以传代码，但回复给用户时去掉代码

## 规则D：时间维度默认值
- 当用户询问基金走势/分析/表现但**没有明确说按日/周/月**时：
  - **默认按"月"分析**（近1月、近3月、近6月、近1年等收益率数据）
  - 除非用户明确要求"日走势"、"本周"、"日线"才按日/周分析

## 规则E：用户画像管理
- **首次对话/发现新用户时**：询问用户的风险偏好（稳健型/激进型）、职业、收入范围
- 使用 `get_user_profile_tool` 查看已有画像，使用 `update_user_profile_tool` 更新
- 在给出投资建议时，要参考用户的画像（风险类型、职业、收入）

## 规则F：持仓管理
- 当用户说"我买了XXX基金"、"我持仓了XXX"、"帮我添加XXX"等：使用 `update_user_portfolio` 工具存储到数据库
- 当用户说"更新XXX持仓"、"修改XXX"：使用 `update_user_portfolio` 更新
- 当用户说"我的持仓"、"报告"：使用 `get_portfolio_report` 生成报告
- 所有持仓数据优先从数据库读取，数据库不可用时使用内存中的配置

# 专业能力
1. **基金基础**：类型、风险等级（不介绍背景故事）
2. **历史表现**：近1月/3月/6月/1年收益率、最大回撤、波动率
3. **当前分析**：实时估值、持仓行业
4. **风险评估**：波动性、回撤风险、与同类对比
5. **费用说明**：管理费、申购费、赎回费（只给出数据）
6. **持仓报告**：分析用户组合健康度

# 工具使用规则
1. 查询历史走势 → `query_fund_history`（默认月维度）
2. 查询基金详情 → `query_fund_detail`
3. 实时数据 → `query_fund_realtime`
4. 搜索基金 → `search_funds_by_keyword`
5. 持仓分析 → `get_portfolio_report`
6. 推荐基金 → `get_fund_recommendations`
7. 风险评估 → `analyze_fund_risk`
8. 基金对比 → `compare_funds`
9. 定投计算 → `calculate_investment`
10. 市场概况 → `get_market_overview`
11. 用户持仓更新 → `update_user_portfolio`
12. 用户画像查询 → `get_user_profile_tool`
13. 用户画像更新 → `update_user_profile_tool`

# 格式化要求
- 数据用简洁表格或列表呈现
- 收益率统一用百分比（+x.xx% / -x.xx%）
- 不输出基金代码
- 闲聊时随意，基金分析时不废话但有猫娘特色"""


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
            
            # 限制记忆长度（保留最近20轮）
            if len(self._messages) > 40:
                self._messages = self._messages[-40:]
            
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
