"""
基金报告助手 - 核心Agent（兼容层）

兼容旧版接口，内部使用基于 LangChain 的新版 Agent。
新用户可直接使用 core.langchain_agent 中的 FundLangChainAgent。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 尝试导入 LangChain Agent
try:
    from core.langchain_agent import FundLangChainAgent
    from core.tools import _global_portfolios
    _USE_LANGCHAIN = True
except ImportError as e:
    print(f"⚠️ LangChain Agent 导入失败 ({e})，使用旧版规则引擎")
    _USE_LANGCHAIN = False
    _global_portfolios = {}

from fund_data.fetcher import (
    get_fund_comprehensive_info,
    get_fund_basic_info,
    compute_investment_metrics,
    get_recommended_funds,
    search_funds,
)
from analysis.risk_analyzer import RiskAnalyzer
from analysis.recommender import FundRecommender
from analysis.portfolio_analyzer import PortfolioAnalyzer
from report.generator import ReportGenerator


class FundAgent:
    """基金报告助手 Agent（兼容层，内部使用 LangChain Agent）"""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.portfolios = self.config.get("portfolios", {})

        if _USE_LANGCHAIN:
            # 使用 LangChain Agent
            self._agent = FundLangChainAgent(self.config)
        else:
            # 使用旧版规则引擎
            self._agent = None
            self._init_legacy(config)

    def _init_legacy(self, config: dict):
        """初始化旧版引擎（备用）"""
        self.risk_analyzer = RiskAnalyzer(
            config.get("algorithm", {}).get("weights", None)
        )
        weights = config.get("algorithm", {}).get("weights", None)
        self.recommender = FundRecommender(weights)
        self.portfolio_analyzer = PortfolioAnalyzer()
        self.report_generator = ReportGenerator(
            config.get("report", {}).get("language", "zh")
        )
        self._fund_cache = {}
        self._chat_history = []

    def process_message(self, message: str, user_id: str = "default_user") -> str:
        """
        处理用户消息

        Args:
            message: 用户消息文本
            user_id: 用户标识

        Returns:
            回复内容
        """
        if _USE_LANGCHAIN and self._agent:
            return self._agent.process_message(message, user_id)
        else:
            return self._legacy_process_message(message, user_id)

    def _legacy_process_message(self, message: str, user_id: str) -> str:
        """旧版消息处理（备用）"""
        import re
        self._chat_history.append({
            "user": user_id,
            "message": message,
            "time": datetime.now().isoformat(),
        })
        message = message.strip()
        intent = self._parse_intent_legacy(message)
        
        if intent["type"] == "report":
            return self._handle_report_request_legacy(intent, user_id)
        elif intent["type"] == "fund_query":
            return self._handle_fund_query_legacy(intent)
        elif intent["type"] == "search":
            return self._handle_search_legacy(intent)
        elif intent["type"] == "recommend":
            return self._handle_recommend_legacy(intent, user_id)
        elif intent["type"] == "help":
            return self._get_help_text_legacy()
        else:
            return self._get_help_text_legacy()

    def _parse_intent_legacy(self, message: str) -> Dict[str, Any]:
        """解析用户意图（旧版）"""
        import re
        intent = {"type": "unknown", "params": {}}
        report_patterns = [r"报告", r"持仓", r"我的基金", r"总览", r"分析", r"盈亏", r"收益"]
        if any(re.search(p, message, re.I) for p in report_patterns):
            intent["type"] = "report"
            return intent
        query_patterns = [r"查询\s*(\d{6})", r"(\d{6})\s*(怎么样|如何|收益|净值)", r"看看\s*(\d{6})"]
        for pat in query_patterns:
            m = re.search(pat, message)
            if m:
                intent["type"] = "fund_query"
                intent["params"]["fund_code"] = m.group(1)
                return intent
        search_patterns = [r"(搜索|找|查找|搜一下)\s*(.+)", r"有没有\s*(.+)"]
        for pat in search_patterns:
            m = re.search(pat, message)
            if m:
                intent["type"] = "search"
                intent["params"]["keyword"] = m.group(2)
                return intent
        code_match = re.search(r'(\d{6})', message)
        if code_match:
            intent["type"] = "fund_query"
            intent["params"]["fund_code"] = code_match.group(1)
            return intent
        recommend_patterns = [r"推荐", r"好基金", r"买什么", r"recommend"]
        if any(re.search(p, message, re.I) for p in recommend_patterns):
            intent["type"] = "recommend"
            return intent
        help_patterns = [r"帮助", r"help", r"功能", r"指令", r"怎么用", r"菜单"]
        if any(re.search(p, message, re.I) for p in help_patterns):
            intent["type"] = "help"
            return intent
        return intent

    def _handle_report_request_legacy(self, intent: Dict, user_id: str) -> str:
        """处理报告请求（旧版）"""
        try:
            portfolio = self.portfolios.get(user_id, self.portfolios.get("default_user"))
            if not portfolio:
                return "❌ 未找到您的持仓信息，请先在配置文件中设置您的持仓。"
            funds = portfolio.get("funds", [])
            if not funds:
                return "❌ 您的持仓列表为空，请先在配置中添加基金。"
            holdings_data = []
            all_risk_warnings = {}
            for fund in funds:
                code = fund["code"]
                cost = fund.get("cost", 0)
                shares = fund.get("shares", 0)
                metrics = compute_investment_metrics(code, cost, shares)
                info = self._get_fund_data_legacy(code)
                if info:
                    metrics["收益率"] = info.get("收益率", {})
                    metrics["基金类型"] = info.get("基金类型", "")
                    metrics["基金规模(亿)"] = info.get("基金规模(亿)", 0)
                    metrics["最大回撤"] = info.get("最大回撤")
                    metrics["基金经理"] = info.get("基金经理", "")
                    metrics["基金经理列表"] = info.get("基金经理列表", [])
                    warnings = self.risk_analyzer.analyze(info)
                    if warnings:
                        all_risk_warnings[code] = warnings
                holdings_data.append(metrics)
            portfolio_result = self.portfolio_analyzer.analyze_portfolio(holdings_data)
            exclude_codes = [f["code"] for f in funds]
            recommendations = self._get_recommendations_legacy(exclude_codes)
            return self.report_generator.generate_full_report(
                portfolio_analysis=portfolio_result,
                risk_warnings=all_risk_warnings,
                recommendations=recommendations,
                user_name=user_id,
            )
        except Exception as e:
            return f"❌ 生成报告时出错: {str(e)}"

    def _handle_fund_query_legacy(self, intent: Dict) -> str:
        """处理单支基金查询（旧版）"""
        fund_code = intent["params"].get("fund_code", "")
        if not fund_code:
            return "❌ 请提供基金代码"
        try:
            info = self._get_fund_data_legacy(fund_code)
            if not info:
                return f"❌ 无法获取基金 {fund_code} 的信息"
            name = info.get("基金名称", fund_code)
            lines = [f"📊 {name} ({fund_code})", "─" * 35]
            nav = info.get("单位净值", info.get("估算净值", "N/A"))
            day_change = info.get("估算涨跌幅", info.get("日涨跌幅", "N/A"))
            lines.append(f"净值: {nav}")
            if isinstance(day_change, (int, float)):
                lines[-1] += f"  |  日涨跌: {day_change:+.2f}%"
            lines.append(f"类型: {info.get('基金类型', '未知')}")
            size = info.get("基金规模(亿)", 0)
            if size:
                lines.append(f"规模: {size:.2f}亿")
            mgr = info.get("基金经理", "")
            if mgr:
                lines.append(f"经理: {mgr}")
            returns = info.get("收益率", {})
            if returns:
                lines.append("")
                lines.append("📈 阶段收益:")
                lines.append(f"  近1月: {returns.get('近1月', 0):+.2f}%  |  近3月: {returns.get('近3月', 0):+.2f}%")
                lines.append(f"  近6月: {returns.get('近6月', 0):+.2f}%  |  近1年: {returns.get('近1年', 0):+.2f}%")
            warnings = self.risk_analyzer.analyze(info)
            if warnings:
                lines.append("")
                lines.append("⚠️ 风险提醒:")
                for w in warnings[:3]:
                    lines.append(f"  {w.get('等级', '')} {w.get('类型', '')}: {w.get('描述', '')}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 查询基金时出错: {str(e)}"

    def _handle_search_legacy(self, intent: Dict) -> str:
        """处理基金搜索（旧版）"""
        keyword = intent["params"].get("keyword", "")
        if not keyword:
            return "❌ 请提供搜索关键词"
        try:
            results = search_funds(keyword)
            if not results:
                return f"❌ 未找到与 '{keyword}' 相关的基金。"
            lines = [f"🔍 搜索 '{keyword}' 共找到 {len(results)} 支基金："]
            lines.append("─" * 35)
            for i, fund in enumerate(results[:15], 1):
                lines.append(f"{i}. {fund['基金名称']} ({fund['基金代码']})")
                lines.append(f"   类型: {fund['基金类型']}")
            lines.append("")
            lines.append("💡 回复基金代码可查询详情")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ 搜索基金时出错: {str(e)}"

    def _handle_recommend_legacy(self, intent: Dict, user_id: str) -> str:
        """处理推荐请求（旧版）"""
        try:
            portfolio = self.portfolios.get(user_id, self.portfolios.get("default_user"))
            exclude_codes = []
            if portfolio:
                exclude_codes = [f["code"] for f in portfolio.get("funds", [])]
            recommendations = self._get_recommendations_legacy(exclude_codes)
            if not recommendations:
                return "❌ 暂时无法获取基金推荐数据"
            return self.report_generator.generate_recommendation_table(recommendations)
        except Exception as e:
            return f"❌ 获取推荐时出错: {str(e)}"

    def _get_recommendations_legacy(self, exclude_codes=None) -> List[Dict]:
        """获取基金推荐（旧版）"""
        try:
            fund_list = get_recommended_funds(page=1, page_size=200)
            if not fund_list:
                return []
            scored = self.recommender.recommend(
                fund_list,
                top_n=self.config.get("report", {}).get("recommend_count", 5),
                exclude_codes=exclude_codes or [],
            )
            return self.recommender.get_recommendation_summary(scored)
        except Exception as e:
            print(f"获取推荐失败: {e}")
            return []

    def _get_fund_data_legacy(self, fund_code: str) -> Optional[Dict]:
        """获取基金数据（带缓存，旧版）"""
        if fund_code in self._fund_cache:
            return self._fund_cache[fund_code]
        data = get_fund_comprehensive_info(fund_code)
        if data:
            self._fund_cache[fund_code] = data
        return data

    def _get_help_text_legacy(self) -> str:
        """获取帮助文本（旧版）"""
        sep = "─" * 35
        return ("🤖 基金报告助手使用说明\n" + sep + "\n"
                + "📋 发送「报告」或「持仓」→ 生成完整持仓分析报告\n"
                + "🔍 发送基金代码（如 000001）→ 查询单支基金\n"
                + "🔎 发送「搜索 白酒」→ 搜索相关基金\n"
                + "🎯 发送「推荐」→ 获取精选基金推荐\n"
                + "❓ 发送「帮助」→ 显示此菜单\n"
                + sep + "\n"
                + "💡 首次使用请先在配置文件中设置您的持仓信息。")

    def update_portfolio(self, user_id: str, fund_code: str,
                         cost: float, shares: float, name: str = "") -> str:
        """更新用户持仓"""
        if _USE_LANGCHAIN and self._agent:
            return self._agent.update_portfolio(user_id, fund_code, cost, shares, name)
        if user_id not in self.portfolios:
            self.portfolios[user_id] = {"funds": []}
        if not name:
            info = get_fund_basic_info(fund_code)
            if info:
                name = info.get("基金名称", "")
        existing = [f for f in self.portfolios[user_id]["funds"] if f["code"] == fund_code]
        if existing:
            existing[0]["cost"] = cost
            existing[0]["shares"] = shares
            if name:
                existing[0]["name"] = name
            return f"✅ 已更新 {fund_code} {name} 的持仓信息"
        else:
            self.portfolios[user_id]["funds"].append({
                "code": fund_code, "name": name, "cost": cost, "shares": shares,
            })
            return f"✅ 已添加 {fund_code} {name} 到持仓列表"

    def clear_cache(self):
        """清空数据缓存"""
        if _USE_LANGCHAIN and self._agent:
            self._agent.clear_cache()
        else:
            self._fund_cache = {}
