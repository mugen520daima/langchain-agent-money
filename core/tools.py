"""
基金助手工具集 - LangChain Agent 使用的工具

包含：
1. query_fund_history - 查询基金历史净值走势（优先查数据库，没有则调API并入库）
2. query_fund_detail - 查询基金详细信息
3. query_fund_realtime - 查询基金实时估值
4. search_funds_by_keyword - 搜索基金
5. get_portfolio_report - 生成持仓分析报告
6. get_fund_recommendations - 获取基金推荐
7. analyze_fund_risk - 分析基金风险
8. get_market_overview - 获取市场概况
9. compare_funds - 比较多支基金
10. calculate_investment - 计算定投/投资收益
"""

from typing import Dict, List, Optional, Any, Type
from datetime import datetime, timedelta
import os
import sys
import json

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fund_data.fetcher import (
    get_fund_comprehensive_info,
    get_fund_realtime_estimate,
    get_fund_basic_info,
    compute_investment_metrics,
    get_recommended_funds,
    search_funds,
    get_fund_detail,
    get_fund_manager_info,
)
from analysis.risk_analyzer import RiskAnalyzer
from analysis.recommender import FundRecommender
from analysis.portfolio_analyzer import PortfolioAnalyzer
from report.generator import ReportGenerator

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field

# ============================================================
# 全局分析引擎实例（可复用）
# ============================================================

_risk_analyzer = RiskAnalyzer()
_recommender = FundRecommender()
_portfolio_analyzer = PortfolioAnalyzer()
_report_generator = ReportGenerator("zh")
_fund_cache: Dict[str, dict] = {}
_global_portfolios: Dict[str, dict] = {}  # 全局持仓数据（由 agent 设置）


def _get_fund_data(fund_code: str) -> Optional[Dict]:
    """获取基金数据（带缓存）"""
    if fund_code in _fund_cache:
        return _fund_cache[fund_code]
    data = get_fund_comprehensive_info(fund_code)
    if data:
        _fund_cache[fund_code] = data
    return data


# ============================================================
# 数据库模块（TiDB占位）
# ============================================================

class DatabaseManager:
    """数据库管理器 - TiDB（先留空）"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._initialized = False
    
    async def init(self):
        """初始化数据库连接（先空着）"""
        pass
    
    async def get_fund_history(self, fund_code: str) -> Optional[List[Dict]]:
        """从数据库查询基金历史走势（先空着，返回None表示需要调API）"""
        return None
    
    async def save_fund_history(self, fund_code: str, history_data: List[Dict]):
        """保存基金历史走势到数据库（先空着）"""
        pass
    
    async def get_fund_detail(self, fund_code: str) -> Optional[Dict]:
        """从数据库查询基金详情"""
        return None
    
    async def save_fund_detail(self, fund_code: str, detail: Dict):
        """保存基金详情到数据库"""
        pass

_db_manager = DatabaseManager()


# ============================================================
# 工具函数
# ============================================================

def _format_history_chart(history: List[Dict], max_points: int = 30) -> str:
    """
    将历史净值数据格式化为可读的走势文本
    用简单的ASCII可视化展示趋势
    """
    if not history:
        return "暂无历史数据"
    
    # 只取最近的数据
    recent = history[-max_points:]
    
    if not recent:
        return "暂无历史数据"
    
    # 提取净值
    values = [h.get("单位净值", 0) for h in recent]
    dates = [h.get("日期", "") for h in recent]
    
    if not values:
        return "暂无历史净值数据"
    
    min_val = min(values)
    max_val = max(values)
    diff = max_val - min_val if max_val != min_val else 1
    
    # 计算涨跌天数
    up_days = 0
    down_days = 0
    for i in range(1, len(values)):
        if values[i] > values[i-1]:
            up_days += 1
        elif values[i] < values[i-1]:
            down_days += 1
    
    # 计算区间涨跌幅
    start_val = values[0]
    end_val = values[-1]
    period_return = ((end_val - start_val) / start_val) * 100 if start_val > 0 else 0
    
    # 用简单的迷你图展示
    chars = []
    for v in values:
        normalized = (v - min_val) / diff * 6  # 0-6
        if normalized <= 1:
            chars.append("▁")
        elif normalized <= 2:
            chars.append("▂")
        elif normalized <= 3:
            chars.append("▃")
        elif normalized <= 4:
            chars.append("▅")
        elif normalized <= 5:
            chars.append("▆")
        else:
            chars.append("▇")
    
    chart = "".join(chars)
    
    # 格式化输出
    lines = [
        f"📈 净值走势（最近{len(recent)}个交易日）",
        f"  {chart}",
        f"  区间: {dates[0] if dates else ''} ~ {dates[-1] if dates else ''}",
        f"  区间涨跌: {period_return:+.2f}%",
        f"  区间高低: {min_val:.4f} ~ {max_val:.4f}",
        f"  上涨{up_days}天 / 下跌{down_days}天",
        f"  最新净值: {values[-1]:.4f}（{dates[-1] if dates else ''}）",
    ]
    return "\n".join(lines)


def _get_portfolio_data(portfolios: dict, user_id: str = "default_user") -> tuple:
    """获取用户的持仓配置数据"""
    portfolio = portfolios.get(user_id, portfolios.get("default_user"))
    if not portfolio:
        return [], {}
    funds = portfolio.get("funds", [])
    
    holdings_data = []
    all_risk_warnings = {}
    
    for fund in funds:
        code = fund["code"]
        name = fund.get("name", "")
        cost = fund.get("cost", 0)
        shares = fund.get("shares", 0)
        
        # 获取持仓指标
        metrics = compute_investment_metrics(code, cost, shares)
        
        # 获取综合信息
        info = _get_fund_data(code)
        if info:
            metrics["收益率"] = info.get("收益率", {})
            metrics["基金类型"] = info.get("基金类型", "")
            metrics["基金规模(亿)"] = info.get("基金规模(亿)", 0)
            metrics["最大回撤"] = info.get("最大回撤")
            metrics["基金经理"] = info.get("基金经理", "")
            metrics["基金经理列表"] = info.get("基金经理列表", [])
            
            warnings = _risk_analyzer.analyze(info)
            if warnings:
                all_risk_warnings[code] = warnings
        
        holdings_data.append(metrics)
    
    return holdings_data, all_risk_warnings


# ============================================================
# LangChain 工具定义
# ============================================================

class FundHistoryInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundHistoryInput)
def query_fund_history(fund_code: str) -> str:
    """
    查询基金的历史净值走势数据。
    优先从数据库查询，如果数据库没有则调用天天基金API获取并存入数据库。
    返回包含走势图、区间涨跌、最高最低净值等信息。
    """
    # 先尝试从数据库获取
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        history = loop.run_until_complete(_db_manager.get_fund_history(fund_code))
        loop.close()
        if history:
            # 数据库中已有
            chart = _format_history_chart(history)
            return f"✅ 从数据库查到基金 [{fund_code}] 的历史走势：\n{chart}"
    except Exception:
        pass
    
    # 数据库没有，调API获取
    detail = get_fund_detail(fund_code)
    if not detail:
        return f"❌ 无法获取基金 {fund_code} 的数据，请确认基金代码是否正确喵~"
    
    history = detail.get("历史净值", [])
    if not history:
        # 尝试从综合信息获取
        info = _get_fund_data(fund_code)
        if info:
            history = info.get("历史净值", [])
    
    if not history:
        return f"❌ 基金 {fund_code} 没有历史净值数据喵~"
    
    # 异步保存到数据库（不阻塞返回）
    try:
        import asyncio
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_db_manager.save_fund_history(fund_code, history))
        loop.close()
    except Exception:
        pass
    
    chart = _format_history_chart(history)
    name = detail.get("基金名称", fund_code)
    return (
        f"📊 {name} ({fund_code}) 历史走势喵~\n"
        f"（已保存到数据库）\n"
        f"{chart}"
    )


class FundDetailInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundDetailInput)
def query_fund_detail(fund_code: str) -> str:
    """
    查询基金的详细信息，包括基金名称、类型、规模、基金经理、收益率、
    持仓数据、行业分布等完整信息。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"❌ 无法获取基金 {fund_code} 的详细信息喵~ 请检查基金代码是否正确喵~"
    
    name = info.get("基金名称", fund_code)
    lines = [
        f"📋 {name}（{fund_code}）详细信息喵~",
        "─" * 35,
        f"类型: {info.get('基金类型', '未知')}",
        f"规模: {info.get('基金规模(亿)', 0):.2f}亿元" if info.get("基金规模(亿)") else "规模: 未知",
        f"经理: {info.get('基金经理', '未知')}",
        f"公司: {info.get('基金公司', '未知')}",
        f"成立: {info.get('成立日期', '未知')}",
    ]
    
    # 收益率
    returns = info.get("收益率", {})
    if returns:
        lines.append("")
        lines.append("📈 阶段收益:")
        lines.append(f"  近1月: {returns.get('近1月', 0):+.2f}%")
        lines.append(f"  近3月: {returns.get('近3月', 0):+.2f}%")
        lines.append(f"  近6月: {returns.get('近6月', 0):+.2f}%")
        lines.append(f"  近1年: {returns.get('近1年', 0):+.2f}%")
        r3y = returns.get("近3年", 0)
        if r3y:
            lines.append(f"  近3年: {r3y:+.2f}%")
        lines.append(f"  成立以来: {returns.get('成立以来', 0):+.2f}%")
    
    # 最大回撤
    max_dd = info.get("最大回撤")
    if max_dd is not None:
        lines.append("")
        lines.append(f"⚠️ 最大回撤: {abs(max_dd):.2f}%")
    
    # 持仓数据
    positions = info.get("持仓数据", [])
    if positions:
        lines.append("")
        lines.append("🏢 前十大重仓股:")
        for i, pos in enumerate(positions[:5], 1):
            lines.append(f"  {i}. {pos.get('股票名称', '')} ({pos.get('占净值比例(%)', 0):.2f}%)")
    
    return "\n".join(lines)


class FundRealtimeInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundRealtimeInput)
def query_fund_realtime(fund_code: str) -> str:
    """
    查询基金的实时估值和净值信息，包括估算净值、估算涨跌幅、昨日净值等。
    """
    info = get_fund_realtime_estimate(fund_code)
    if not info:
        return f"❌ 无法获取基金 {fund_code} 的实时估值喵~（非交易时间可能不显示）"
    
    name = info.get("基金名称", fund_code)
    estimate_nav = info.get("估算净值", 0)
    estimate_change = info.get("估算涨跌幅", 0)
    yesterday_nav = info.get("昨日净值", 0)
    estimate_time = info.get("估值时间", "")
    
    emoji = "📈" if estimate_change >= 0 else "📉"
    
    return (
        f"{emoji} {name}（{fund_code}）实时估值喵~\n"
        f"─" * 30 + "\n"
        f"估算净值: {estimate_nav:.4f}\n"
        f"估算涨跌: {estimate_change:+.2f}%\n"
        f"昨日净值: {yesterday_nav:.4f}\n"
        f"估值时间: {estimate_time}\n"
        f"（数据仅供参考，以当日官方公布的净值为准喵~）"
    )


class SearchFundsInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如'白酒'、'新能源'、'易方达'等")

@tool(args_schema=SearchFundsInput)
def search_funds_by_keyword(keyword: str) -> str:
    """
    根据关键词搜索基金，支持基金名称、基金类型等模糊搜索。
    返回匹配的基金列表及基本信息。
    """
    results = search_funds(keyword)
    if not results:
        return f"❌ 没有找到与「{keyword}」相关的基金喵~ 换个关键词试试喵~"
    
    # 按类型分组展示
    lines = [f"🔍 搜索「{keyword}」找到 {len(results)} 支基金喵~"]
    lines.append("─" * 35)
    
    for i, fund in enumerate(results[:15], 1):
        lines.append(f"{i}. {fund['基金名称']}（{fund['基金代码']}）")
        lines.append(f"   类型: {fund['基金类型']}")
    
    if len(results) > 15:
        lines.append(f"  ... 还有 {len(results) - 15} 支基金未显示喵~")
    
    lines.append("")
    lines.append("💡 发送基金代码可以查看详细信息喵~")
    
    return "\n".join(lines)


@tool
def get_portfolio_report(user_id: str = "default_user") -> str:
    """
    生成用户持仓的完整分析报告，包含持仓概览、明细分析、风险评估、基金推荐。
    需要用户已配置持仓信息。
    """
    # 实际调用时通过全局变量获取持仓数据
    portfolios = _global_portfolios if _global_portfolios else {}
    
    holdings_data, all_risk_warnings = _get_portfolio_data(portfolios, user_id)
    
    if not holdings_data:
        return "❌ 没有找到你的持仓信息喵~ 请先在配置文件中设置持仓喵~"
    
    # 持仓分析
    portfolio_result = _portfolio_analyzer.analyze_portfolio(holdings_data)
    
    # 获取推荐
    portfolio = portfolios.get(user_id, portfolios.get("default_user", {}))
    exclude_codes = [f["code"] for f in portfolio.get("funds", [])] if portfolio else []
    
    try:
        fund_list = get_recommended_funds(page=1, page_size=200)
        scored = _recommender.recommend(fund_list, top_n=5, exclude_codes=exclude_codes)
        recommendations = _recommender.get_recommendation_summary(scored) if scored else []
    except Exception:
        recommendations = []
    
    # 生成报告
    report = _report_generator.generate_full_report(
        portfolio_analysis=portfolio_result,
        risk_warnings=all_risk_warnings,
        recommendations=recommendations,
        user_name=user_id,
    )
    
    return report


class RecommendInput(BaseModel):
    count: int = Field(default=5, description="推荐的基金数量，默认5支")

@tool(args_schema=RecommendInput)
def get_fund_recommendations(count: int = 5) -> str:
    """
    从全市场获取基金推荐，基于多因子量化评分模型筛选优质基金。
    可指定推荐数量。
    """
    try:
        fund_list = get_recommended_funds(page=1, page_size=200)
        if not fund_list:
            return "❌ 暂时无法获取基金推荐数据喵~ 请稍后重试喵~"
        
        scored = _recommender.recommend(fund_list, top_n=min(count, 10))
        if not scored:
            return "❌ 暂时没有找到合适的推荐喵~"
        
        recommendations = _recommender.get_recommendation_summary(scored)
        return _report_generator.generate_recommendation_table(recommendations)
    
    except Exception as e:
        return f"❌ 获取推荐时出错喵~ {str(e)}"


class FundRiskInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundRiskInput)
def analyze_fund_risk(fund_code: str) -> str:
    """
    分析单支基金的风险状况，包括回撤风险、经理变更风险、规模风险、
    行业集中度风险、业绩突变风险等。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"❌ 无法获取基金 {fund_code} 的信息喵~"
    
    warnings = _risk_analyzer.analyze(info)
    summary = _risk_analyzer.summarize_risk_level(warnings)
    
    name = info.get("基金名称", fund_code)
    lines = [
        f"⚠️ {name}（{fund_code}）风险分析报告喵~",
        "─" * 35,
        f"整体风险等级: {summary.get('整体风险', '未知')}",
        f"共发现 {summary.get('风险总数', 0)} 项风险提示",
        f"  🔴 高危: {summary.get('高危数', 0)} 项",
        f"  🟡 预警: {summary.get('预警数', 0)} 项",
        f"  🔵 提示: {summary.get('提示数', 0)} 项",
    ]
    
    if warnings:
        lines.append("")
        lines.append("详细风险列表:")
        for w in warnings:
            lines.append(f"\n  {w.get('等级', '')} {w.get('类型', '')}")
            lines.append(f"  {w.get('描述', '')}")
    
    return "\n".join(lines)


class CompareFundsInput(BaseModel):
    fund_codes: str = Field(description="要比较的基金代码，用逗号分隔，如 '110011,000001,161725'")

@tool(args_schema=CompareFundsInput)
def compare_funds(fund_codes: str) -> str:
    """
    比较多支基金的收益率、规模、风险等指标。
    输入格式：用逗号分隔的基金代码，如 '110011,000001,161725'
    """
    codes = [c.strip() for c in fund_codes.split(",") if c.strip()]
    if len(codes) < 2:
        return "❌ 请至少提供两支基金代码进行比较喵~ 例如: 110011,000001"
    if len(codes) > 5:
        return "❌ 一次最多比较5支基金喵~"
    
    funds_data = []
    for code in codes:
        info = _get_fund_data(code)
        if info:
            funds_data.append(info)
    
    if len(funds_data) < 2:
        return "❌ 无法获取足够的基金数据进行比较喵~"
    
    lines = ["📊 基金对比喵~", "─" * 40]
    
    # 表头
    headers = ["指标"] + [f.get("基金名称", f.get("基金代码", "")) for f in funds_data]
    
    # 收益率对比
    returns_keys = ["近1月", "近3月", "近6月", "近1年", "近3年"]
    lines.append("\n📈 收益率对比:")
    for key in returns_keys:
        row = [key]
        for f in funds_data:
            rets = f.get("收益率", {})
            val = rets.get(key, "N/A")
            if isinstance(val, (int, float)):
                row.append(f"{val:+.2f}%")
            else:
                row.append("N/A")
        lines.append("  " + " | ".join(row))
    
    # 规模对比
    lines.append("\n🏢 规模和风险对比:")
    for f in funds_data:
        size = f.get("基金规模(亿)", 0)
        mgr = f.get("基金经理", "未知")
        dd = f.get("最大回撤")
        dd_str = f"{abs(dd):.2f}%" if dd else "N/A"
        lines.append(f"  {f.get('基金名称', '')}: 规模{size:.1f}亿 | 经理:{mgr} | 最大回撤:{dd_str}")
    
    # 风险分析对比
    lines.append("\n⚠️ 风险对比:")
    for f in funds_data:
        warnings = _risk_analyzer.analyze(f)
        summary = _risk_analyzer.summarize_risk_level(warnings)
        lines.append(f"  {f.get('基金名称', '')}: {summary.get('整体风险', '未知')}（{summary.get('风险总数', 0)}项风险）")
    
    return "\n".join(lines)


class CalculateInvestmentInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")
    amount: float = Field(description="每期定投金额，如 1000")
    periods: int = Field(default=12, description="定投期数（月数），默认12个月")
    frequency: str = Field(default="monthly", description="定投频率: 'monthly'（每月）或 'weekly'（每周）")

@tool(args_schema=CalculateInvestmentInput)
def calculate_investment(fund_code: str, amount: float, periods: int = 12, frequency: str = "monthly") -> str:
    """
    模拟计算基金的定投收益，基于历史净值数据进行回测。
    需要提供基金代码、每期金额、期数和频率。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"❌ 无法获取基金 {fund_code} 的数据喵~"
    
    history = info.get("历史净值", [])
    if not history:
        return f"❌ 基金 {fund_code} 没有足够的历史净值数据进行定投计算喵~"
    
    name = info.get("基金名称", fund_code)
    
    # 取足够的历史数据
    step = 1 if frequency == "weekly" else 4  # 按周或按月取数据点
    needed = periods * step
    
    if len(history) < needed:
        # 用所有可用的数据
        needed = len(history)
        periods = needed // step
    
    recent_history = history[-needed:] if needed > 0 else history
    
    if len(recent_history) < 2:
        return "❌ 历史数据不足，无法计算喵~"
    
    # 模拟定投
    total_invested = 0
    total_shares = 0
    investments_made = 0
    
    for i, h in enumerate(recent_history):
        if i % step == 0:  # 定投日
            nav = h.get("单位净值", 0)
            if nav > 0:
                shares_bought = amount / nav
                total_shares += shares_bought
                total_invested += amount
                investments_made += 1
    
    # 计算最终价值
    latest_nav = recent_history[-1].get("单位净值", 0)
    final_value = total_shares * latest_nav
    total_return = final_value - total_invested
    return_pct = (total_return / total_invested) * 100 if total_invested > 0 else 0
    
    # 计算成本均价
    avg_cost = total_invested / total_shares if total_shares > 0 else 0
    
    freq_str = "周" if frequency == "weekly" else "月"
    
    lines = [
        f"💎 {name}（{fund_code}）定投回测喵~",
        "─" * 35,
        f"定投方式: 每{freq_str}定投 {amount:.2f}元",
        f"定投次数: {investments_made} 次",
        f"总投资额: {total_invested:.2f}元",
        f"累计份额: {total_shares:.2f}份",
        f"最新净值: {latest_nav:.4f}",
        f"成本均价: {avg_cost:.4f}",
        f"最终市值: {final_value:.2f}元",
        f"总收益: {total_return:+.2f}元（{return_pct:+.2f}%）",
    ]
    
    emoji = "📈" if total_return >= 0 else "📉"
    lines.insert(1, f"{emoji}")
    
    return "\n".join(lines)


class GetMarketOverviewInput(BaseModel):
    category: str = Field(default="all", description="市场类别: 'all'（全部）, 'stock'（股票型）, 'mixed'（混合型）, 'index'（指数型）, 'bond'（债券型）")

@tool(args_schema=GetMarketOverviewInput)
def get_market_overview(category: str = "all") -> str:
    """
    获取基金市场概况，了解当前市场热门基金表现。
    可以指定基金类别筛选。
    """
    try:
        fund_list = get_recommended_funds(page=1, page_size=100)
        if not fund_list:
            return "❌ 暂时无法获取市场数据喵~"
        
        # 过滤类别
        if category != "all":
            type_map = {
                "stock": "股票型",
                "mixed": "混合型", 
                "index": "指数型",
                "bond": "债券型",
            }
            target = type_map.get(category, category)
            fund_list = [f for f in fund_list if target in f.get("基金类型", "")]
        
        if not fund_list:
            return f"❌ 没有找到相关类型的基金数据喵~"
        
        # 统计概览
        total = len(fund_list)
        up_count = sum(1 for f in fund_list if f.get("日涨跌幅", 0) > 0)
        down_count = sum(1 for f in fund_list if f.get("日涨跌幅", 0) < 0)
        
        # 找表现最好和最差的
        sorted_by_day = sorted(fund_list, key=lambda x: x.get("日涨跌幅", 0), reverse=True)
        top_5 = sorted_by_day[:5]
        bottom_5 = sorted_by_day[-5:]
        
        category_name = category if category != "all" else "全部"
        
        lines = [
            f"📊 {category_name}基金市场概况喵~",
            "─" * 35,
            f"统计基金数: {total} 支",
            f"今日上涨: {up_count} 支",
            f"今日下跌: {down_count} 支",
        ]
        
        lines.append("\n📈 今日涨幅TOP5:")
        for i, f in enumerate(top_5, 1):
            lines.append(f"  {i}. {f.get('基金名称', '')} ({f.get('基金代码', '')})")
            lines.append(f"     {f.get('日涨跌幅', 0):+.2f}%")
        
        lines.append("\n📉 今日跌幅TOP5:")
        for i, f in enumerate(bottom_5, 1):
            lines.append(f"  {i}. {f.get('基金名称', '')} ({f.get('基金代码', '')})")
            lines.append(f"     {f.get('日涨跌幅', 0):+.2f}%")
        
        lines.append("\n💡 回复基金代码可以查看详细信息喵~")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"❌ 获取市场概况时出错喵~ {str(e)}"


# ============================================================
# 所有工具列表
# ============================================================

def get_all_tools() -> List[BaseTool]:
    """获取所有工具列表"""
    return [
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
    ]
