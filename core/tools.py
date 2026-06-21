"""
基金助手工具集 - LangChain Agent 使用的工具

包含：
1. query_fund_history - 查询基金历史净值走势
2. query_fund_detail - 查询基金详细信息
3. query_fund_realtime - 查询基金实时估值
4. search_funds_by_keyword - 搜索基金
5. get_portfolio_report - 生成持仓分析报告
6. get_fund_recommendations - 获取基金推荐
7. analyze_fund_risk - 分析基金风险
8. get_market_overview - 获取市场概况
9. compare_funds - 比较多支基金
10. calculate_investment - 计算定投/投资收益
11. update_user_portfolio - 更新用户持仓（数据库持久化）
12. get_user_profile_tool - 查询用户画像
13. update_user_profile_tool - 更新用户画像
"""

from typing import Dict, List, Optional, Any, Type
from datetime import datetime, timedelta
import os
import sys
import json
import re
import asyncio
import threading

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fund_data.fetcher import (
    get_fund_comprehensive_info,
    get_fund_realtime_estimate,
    get_fund_basic_info,
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

import logging
logger = logging.getLogger("FundTools")

# ============================================================
# 全局分析引擎实例（可复用）
# ============================================================

_risk_analyzer = RiskAnalyzer()
_recommender = FundRecommender()
_portfolio_analyzer = PortfolioAnalyzer()
_report_generator = ReportGenerator("zh")
_fund_cache: Dict[str, dict] = {}
_global_portfolios: Dict[str, dict] = {}  # 全局持仓数据（由 agent 设置）
_db_config: Dict = {}  # 数据库配置


def _get_fund_data(fund_code: str) -> Optional[Dict]:
    """获取基金数据（带缓存）"""
    if fund_code in _fund_cache:
        return _fund_cache[fund_code]
    data = get_fund_comprehensive_info(fund_code)
    if data:
        _fund_cache[fund_code] = data
    return data


def _get_fund_name(fund_code: str) -> str:
    """根据基金代码获取基金名称"""
    info = _get_fund_data(fund_code)
    if info:
        return info.get("基金名称", fund_code)
    return fund_code


def _search_fund_code_by_name(keyword: str) -> Optional[str]:
    """
    根据基金名称关键词搜索基金代码
    支持模糊匹配，返回第一个匹配的基金代码
    如果第一次没搜到，会提取关键部分再次搜索
    """
    logger.info(f"[DBG] 搜索基金代码，关键词: {keyword}")
    results = search_funds(keyword)
    if results:
        logger.info(f"[DBG] 搜索成功: {keyword} -> {results[0]['基金代码']} ({results[0]['基金名称']})")
        return results[0]["基金代码"]
    
    # 第一次没搜到，提取关键部分再搜
    # 去除常见后缀和前缀
    clean_name = keyword.strip()
    clean_name = re.sub(r'\(QDII\)', '', clean_name)
    clean_name = re.sub(r'[（(].*?[）)]', '', clean_name)  # 去掉括号内容
    clean_name = re.sub(r'A$|C$|B$|E$', '', clean_name)
    clean_name = clean_name.replace('指数', '').replace('混合', '').replace('发起式', '')
    clean_name = clean_name.strip()
    
    if clean_name and clean_name != keyword:
        logger.info(f"[DBG] 清洗后重试搜索: {clean_name}")
        results = search_funds(clean_name)
        if results:
            logger.info(f"[DBG] 清洗搜索成功: {clean_name} -> {results[0]['基金代码']} ({results[0]['基金名称']})")
            return results[0]["基金代码"]
    
    # 再试：只取前4个中文字作为关键词
    import re as _re
    chinese_chars = _re.findall(r'[\u4e00-\u9fff]+', keyword)
    for chars in chinese_chars:
        if len(chars) >= 4:
            short_key = chars[:4]
            logger.info(f"[DBG] 中文关键词搜索: {short_key}")
            results = search_funds(short_key)
            if results:
                logger.info(f"[DBG] 中文关键词搜索成功: {short_key} -> {results[0]['基金代码']} ({results[0]['基金名称']})")
                return results[0]["基金代码"]
    
    logger.warning(f"[DBG] 所有搜索方式都未找到: {keyword}")
    return None


# ============================================================
# 数据库模块（TiDB）
# ============================================================

class DatabaseManager:
    """数据库管理器 - TiDB"""
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._initialized = False
        self._real_db = None
    
    async def _ensure_db(self):
        """确保数据库已初始化"""
        if not self._initialized and self.config.get("enabled", False):
            try:
                from db.database import get_db_manager
                self._real_db = get_db_manager(self.config)
                await self._real_db.connect()
                self._initialized = True
            except Exception as e:
                print(f"数据库初始化失败: {e}")
    
    async def get_fund_history(self, fund_code: str) -> Optional[List[Dict]]:
        """从数据库查询基金历史走势"""
        await self._ensure_db()
        if self._real_db:
            try:
                return await self._real_db.get_fund_history(fund_code)
            except Exception:
                pass
        return None
    
    async def save_fund_history(self, fund_code: str, history_data: List[Dict]):
        """保存基金历史走势到数据库"""
        await self._ensure_db()
        if self._real_db:
            try:
                await self._real_db.save_fund_history(fund_code, history_data)
            except Exception:
                pass
    
    async def get_fund_detail(self, fund_code: str) -> Optional[Dict]:
        """从数据库查询基金详情"""
        await self._ensure_db()
        if self._real_db:
            try:
                return await self._real_db.get_fund_detail(fund_code)
            except Exception:
                pass
        return None
    
    async def save_fund_detail(self, fund_code: str, detail: Dict):
        """保存基金详情到数据库"""
        await self._ensure_db()
        if self._real_db:
            try:
                await self._real_db.save_fund_detail(fund_code, detail)
            except Exception:
                pass
    
    # ---------- 用户画像 ----------
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """获取用户画像"""
        await self._ensure_db()
        if self._real_db:
            try:
                return await self._real_db.get_user_profile(user_id)
            except Exception:
                pass
        return None
    
    async def save_user_profile(self, user_id: str, risk_type: str = "稳健型",
                                 occupation: str = "", income_range: str = ""):
        """保存或更新用户画像"""
        await self._ensure_db()
        if self._real_db:
            try:
                await self._real_db.save_user_profile(user_id, risk_type, occupation, income_range)
            except Exception:
                pass
    
    # ---------- 用户持仓 ----------
    
    async def get_user_portfolios(self, user_id: str) -> Optional[List[Dict]]:
        """获取用户在数据库中的持仓（含实时市值和盈亏率）"""
        await self._ensure_db()
        if self._real_db:
            try:
                return await self._real_db.get_user_portfolios(user_id)
            except Exception:
                pass
        return None
    
    async def save_user_portfolio(self, user_id: str, fund_code: str,
                                   fund_name: str, cost_amount: float, shares: float,
                                   channel: str = "") -> bool:
        """保存或更新用户持仓（含实时市值计算）"""
        await self._ensure_db()
        if self._real_db:
            try:
                # 获取最新净值计算当前市值
                from fund_data.fetcher import get_fund_realtime_estimate
                info = get_fund_realtime_estimate(fund_code)
                nav = 0
                if info:
                    nav = info.get("估算净值", 0) or info.get("昨日净值", 0)
                current_value = shares * nav if nav > 0 else cost_amount
                profit_rate = ((current_value - cost_amount) / cost_amount * 100) if cost_amount > 0 else 0
                
                return await self._real_db.save_user_portfolio(
                    user_id, fund_code, fund_name, cost_amount, current_value, profit_rate, shares, channel
                )
            except Exception as e:
                print(f"保存持仓失败: {e}")
                pass
        return False
    
    async def delete_user_portfolio(self, user_id: str, fund_code: str) -> bool:
        """删除用户某支基金持仓"""
        await self._ensure_db()
        if self._real_db:
            try:
                return await self._real_db.delete_user_portfolio(user_id, fund_code)
            except Exception:
                pass
        return False

_db_manager = DatabaseManager()


# 全局共享事件循环（用于所有异步数据库操作）
_shared_loop = None

def _get_shared_loop():
    """获取或创建共享事件循环"""
    global _shared_loop
    if _shared_loop is None or _shared_loop.is_closed():
        _shared_loop = asyncio.new_event_loop()
        
        def _run_loop(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        
        import threading
        t = threading.Thread(target=_run_loop, args=(_shared_loop,), daemon=True)
        t.start()
    
    return _shared_loop


def _run_async(coro):
    """同步方式运行异步协程（线程安全，使用共享事件循环）"""
    try:
        loop = _get_shared_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=30)
    except Exception as e:
        print(f"_run_async 错误: {e}")
        import traceback
        traceback.print_exc()
        return None


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
            chars.append("_")
        elif normalized <= 2:
            chars.append("_")
        elif normalized <= 3:
            chars.append("-")
        elif normalized <= 4:
            chars.append("-")
        elif normalized <= 5:
            chars.append("^")
        else:
            chars.append("^")
    
    chart = "".join(chars)
    
    # 格式化输出
    lines = [
        f"净值走势（最近{len(recent)}个交易日）",
        f"  {chart}",
        f"  区间: {dates[0] if dates else ''} ~ {dates[-1] if dates else ''}",
        f"  区间涨跌: {period_return:+.2f}%",
        f"  区间高低: {min_val:.4f} ~ {max_val:.4f}",
        f"  上涨{up_days}天 / 下跌{down_days}天",
        f"  最新净值: {values[-1]:.4f}（{dates[-1] if dates else ''}）",
    ]
    return "\n".join(lines)


def _is_today_trading_day() -> bool:
    """
    判断今天是否是交易日
    周末（周六/周日）一定不是交易日，非周末可能是交易日
    """
    now = datetime.now()
    weekday = now.weekday()  # 0=周一, 6=周日
    if weekday >= 5:  # 周六(5) 或 周日(6)
        logger.info(f"[DBG] 今天({now.strftime('%Y-%m-%d')})是周末，非交易日")
        return False
    return True


def _get_portfolio_data(user_id: str = "default_user") -> tuple:
    """
    获取用户的持仓配置数据
    优先从数据库读取（含实时市值和盈亏率），数据库不可用时用内存中的配置
    """
    logger.info(f"[DBG] 查询持仓数据，user_id={user_id}")
    
    # 从数据库获取
    db_portfolios = _run_async(_db_manager.get_user_portfolios(user_id))
    if db_portfolios:
        logger.info(f"[DBG] 从数据库读取到 {len(db_portfolios)} 条持仓: {json.dumps([{'code':f['code'],'name':f.get('name',''),'cost':f.get('cost',0)} for f in db_portfolios], ensure_ascii=False)}")
        funds = db_portfolios
    else:
        logger.info(f"[DBG] 数据库无持仓数据")
        return [], {}
    
    is_trading_day = _is_today_trading_day()
    holdings_data = []
    all_risk_warnings = {}
    
    for fund in funds:
        code = fund["code"]
        name = fund.get("name", "")
        cost = fund.get("cost", 0)
        shares = fund.get("shares", 0)
        
        # 优先使用数据库已计算好的当前市值和盈亏率
        db_current_value = fund.get("current_value")
        db_profit_rate = fund.get("profit_rate")
        
        # 获取最新实时数据计算最新市值
        from fund_data.fetcher import get_fund_realtime_estimate
        realtime = get_fund_realtime_estimate(code)
        if realtime:
            nav = realtime.get("估算净值", 0) or realtime.get("昨日净值", 0)
            current_value = shares * nav if nav > 0 else (db_current_value or cost)
            profit = current_value - cost
            profit_pct = (profit / cost * 100) if cost > 0 else 0
        else:
            # 使用数据库存的值或回退到投入成本
            current_value = db_current_value if db_current_value else cost
            profit_pct = db_profit_rate if db_profit_rate else 0
            nav = current_value / shares if shares > 0 else 0
        
        # 判断当日涨跌幅：非交易日必须为0
        daily_change = realtime.get("估算涨跌幅", 0) if realtime else 0
        if not is_trading_day:
            daily_change = 0
        
        metrics = {
            "基金代码": code,
            "基金名称": name,
            "存储渠道": fund.get("channel", ""),
            "总投入(元)": round(cost, 2),
            "持有份额": shares,
            "当前净值(元)": round(nav, 4),
            "当前市值(元)": round(current_value, 2),
            "盈亏(元)": round(current_value - cost, 2),
            "盈亏比例(%)": round(profit_pct, 2),
            "当日涨跌幅(%)": daily_change,
            "估值时间": realtime.get("估值时间", "") if realtime else "",
        }
        
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
# 工具：隐藏基金代码的处理函数
# ============================================================

def _hide_codes(text: str) -> str:
    """从回复文本中隐藏基金代码（6位数字）"""
    # 替换常见的 "基金名称 (代码)" 格式为只保留名称
    text = re.sub(r'（\d{6}）', '', text)
    text = re.sub(r'\(\d{6}\)', '', text)
    # 替换单独的6位数字（但要避免替换净值数字等）
    # 使用更精确的替换：只在基金上下文中的代码
    return text


# ============================================================
# LangChain 工具定义
# ============================================================

class FundHistoryInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")
    period: str = Field(default="month", description="分析周期: 'day'（日）, 'week'（周）, 'month'（月），默认'month'")

@tool(args_schema=FundHistoryInput)
def query_fund_history(fund_code: str, period: str = "month") -> str:
    """
    查询基金的历史净值走势数据。
    优先从数据库查询，如果数据库没有则调用天天基金API获取并存入数据库。
    返回包含走势图、区间涨跌、最高最低净值等信息。
    如果用户没有明确说按日/周/月，默认按月分析。
    """
    # 先尝试从数据库获取
    try:
        history = _run_async(_db_manager.get_fund_history(fund_code))
        if history:
            chart = _format_history_chart(history)
            name = _get_fund_name(fund_code)
            return f"{name} 历史走势：\n{chart}"
    except Exception:
        pass
    
    # 数据库没有，调API获取
    detail = get_fund_detail(fund_code)
    if not detail:
        return f"无法获取基金数据，请确认基金名称是否正确。"
    
    history = detail.get("历史净值", [])
    if not history:
        info = _get_fund_data(fund_code)
        if info:
            history = info.get("历史净值", [])
    
    if not history:
        return f"该基金没有历史净值数据。"
    
    # 异步保存到数据库（不阻塞返回）
    try:
        _run_async(_db_manager.save_fund_history(fund_code, history))
    except Exception:
        pass
    
    chart = _format_history_chart(history)
    name = _get_fund_name(fund_code)
    period_label = {"day": "日", "week": "周", "month": "月"}.get(period, "月")
    return (
        f"{name} 历史走势（{period_label}度）：\n"
        f"{chart}"
    )


class FundDetailInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundDetailInput)
def query_fund_detail(fund_code: str) -> str:
    """
    查询基金的详细信息，包括基金名称、类型、规模、收益率、持仓数据等。
    注意：回复中不要显示基金代码。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"无法获取该基金的详细信息。"
    
    name = info.get("基金名称", fund_code)
    lines = [
        f"{name} 详细信息：",
        "-" * 30,
        f"类型: {info.get('基金类型', '未知')}",
        f"规模: {info.get('基金规模(亿)', 0):.2f}亿元" if info.get("基金规模(亿)") else "规模: 未知",
    ]
    
    # 收益率
    returns = info.get("收益率", {})
    if returns:
        lines.append("")
        lines.append("阶段收益:")
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
        lines.append(f"最大回撤: {abs(max_dd):.2f}%")
    
    # 持仓数据 - 只显示前3
    positions = info.get("持仓数据", [])
    if positions:
        lines.append("")
        lines.append("前三大重仓股:")
        for i, pos in enumerate(positions[:3], 1):
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
        return f"无法获取该基金的实时估值（非交易时间可能不显示）。"
    
    name = info.get("基金名称", fund_code)
    estimate_nav = info.get("估算净值", 0)
    estimate_change = info.get("估算涨跌幅", 0)
    yesterday_nav = info.get("昨日净值", 0)
    estimate_time = info.get("估值时间", "")
    
    # 非交易日涨跌幅置为0
    if not _is_today_trading_day():
        estimate_change = 0
    
    return (
        f"{name} 实时估值：\n"
        f"估算净值: {estimate_nav:.4f}\n"
        f"估算涨跌: {estimate_change:+.2f}%\n"
        f"昨日净值: {yesterday_nav:.4f}\n"
        f"估值时间: {estimate_time}\n"
    )


class SearchFundsInput(BaseModel):
    keyword: str = Field(description="搜索关键词，如'白酒'、'新能源'、'易方达'等")

@tool(args_schema=SearchFundsInput)
def search_funds_by_keyword(keyword: str) -> str:
    """
    根据关键词搜索基金，支持基金名称、基金类型等模糊搜索。
    返回匹配的基金列表及基本信息。
    注意：回复中不要显示基金代码。
    """
    results = search_funds(keyword)
    if not results:
        return f"没有找到与「{keyword}」相关的基金。换个关键词试试。"
    
    lines = [f"搜索「{keyword}」找到 {len(results)} 支基金："]
    lines.append("-" * 30)
    
    for i, fund in enumerate(results[:15], 1):
        lines.append(f"{i}. {fund['基金名称']}")
        lines.append(f"   类型: {fund['基金类型']}")
    
    if len(results) > 15:
        lines.append(f"  ... 还有 {len(results) - 15} 支未显示。")
    
    return "\n".join(lines)


class PortfolioReportInput(BaseModel):
    user_id: str = Field(default="default_user", description="用户标识")

@tool(args_schema=PortfolioReportInput)
def get_portfolio_report(user_id: str = "default_user") -> str:
    """
    生成用户持仓的完整分析报告，包含持仓概览、明细分析、风险评估、基金推荐。
    需要用户已配置持仓信息。
    注意：回复中不要显示基金代码。
    """
    logger.info(f"[DBG] get_portfolio_report 被调用，user_id={user_id}")
    holdings_data, all_risk_warnings = _get_portfolio_data(user_id)
    
    logger.info(f"[DBG] 持仓查询结果: holdings_data={len(holdings_data)}条, risk_warnings={len(all_risk_warnings)}")
    if not holdings_data:
        logger.info(f"[DBG] 无持仓数据，返回空报告")
        return "没有找到你的持仓信息，请先告诉我你买了哪些基金。"
    
    # 持仓分析
    portfolio_result = _portfolio_analyzer.analyze_portfolio(holdings_data)
    
    # 获取推荐
    portfolio = _global_portfolios.get(user_id, _global_portfolios.get("default_user", {}))
    db_funds = _run_async(_db_manager.get_user_portfolios(user_id))
    
    exclude_codes = []
    if db_funds:
        exclude_codes = [f["code"] for f in db_funds]
    elif portfolio:
        exclude_codes = [f["code"] for f in portfolio.get("funds", [])]
    
    try:
        fund_list = get_recommended_funds(page=1, page_size=200)
        scored = _recommender.recommend(fund_list, top_n=5, exclude_codes=exclude_codes)
        recommendations = _recommender.get_recommendation_summary(scored) if scored else []
    except Exception:
        recommendations = []
    
    # 生成报告 - 去掉基金代码
    report = _report_generator.generate_full_report(
        portfolio_analysis=portfolio_result,
        risk_warnings=all_risk_warnings,
        recommendations=recommendations,
        user_name="用户",
    )
    
    # 隐藏代码
    report = re.sub(r'（\d{6}）', '', report)
    report = re.sub(r'\(\d{6}\)', '', report)
    
    return report


class RecommendInput(BaseModel):
    count: int = Field(default=5, description="推荐的基金数量，默认5支")

@tool(args_schema=RecommendInput)
def get_fund_recommendations(count: int = 5) -> str:
    """
    从全市场获取基金推荐，基于多因子量化评分模型筛选优质基金。
    可指定推荐数量。
    注意：回复中不要显示基金代码。
    """
    try:
        fund_list = get_recommended_funds(page=1, page_size=200)
        if not fund_list:
            return "暂时无法获取基金推荐数据。"
        
        scored = _recommender.recommend(fund_list, top_n=min(count, 10))
        if not scored:
            return "暂时没有找到合适的推荐。"
        
        recommendations = _recommender.get_recommendation_summary(scored)
        table = _report_generator.generate_recommendation_table(recommendations)
        
        # 隐藏代码
        table = re.sub(r'代码: \d{6} \| ', '', table)
        table = re.sub(r'（\d{6}）', '', table)
        table = re.sub(r'\(\d{6}\)', '', table)
        
        return table
    
    except Exception as e:
        return f"获取推荐时出错: {str(e)}"


class FundRiskInput(BaseModel):
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=FundRiskInput)
def analyze_fund_risk(fund_code: str) -> str:
    """
    分析单支基金的风险状况，包括回撤风险、经理变更风险、规模风险、
    行业集中度风险、业绩突变风险等。
    注意：回复中不要显示基金代码。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"无法获取该基金的信息。"
    
    warnings = _risk_analyzer.analyze(info)
    summary = _risk_analyzer.summarize_risk_level(warnings)
    
    name = info.get("基金名称", fund_code)
    lines = [
        f"{name} 风险分析：",
        "-" * 30,
        f"整体风险等级: {summary.get('整体风险', '未知')}",
        f"共发现 {summary.get('风险总数', 0)} 项风险提示",
        f"  高危: {summary.get('高危数', 0)} 项",
        f"  预警: {summary.get('预警数', 0)} 项",
        f"  提示: {summary.get('提示数', 0)} 项",
    ]
    
    if warnings:
        lines.append("")
        lines.append("详细风险:")
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
    输入格式：用逗号分隔的基金代码。
    注意：回复中不要显示基金代码。
    """
    codes = [c.strip() for c in fund_codes.split(",") if c.strip()]
    if len(codes) < 2:
        return "请至少提供两支基金进行比较。"
    if len(codes) > 5:
        return "一次最多比较5支基金。"
    
    funds_data = []
    for code in codes:
        info = _get_fund_data(code)
        if info:
            funds_data.append(info)
    
    if len(funds_data) < 2:
        return "无法获取足够的基金数据进行比较。"
    
    lines = ["基金对比：", "-" * 35]
    
    # 收益率对比
    returns_keys = ["近1月", "近3月", "近6月", "近1年", "近3年"]
    lines.append("\n收益率对比:")
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
    
    # 规模和风险对比
    lines.append("\n规模和风险对比:")
    for f in funds_data:
        size = f.get("基金规模(亿)", 0)
        mgr = f.get("基金经理", "未知")
        dd = f.get("最大回撤")
        dd_str = f"{abs(dd):.2f}%" if dd else "N/A"
        lines.append(f"  {f.get('基金名称', '')}: 规模{size:.1f}亿 | 经理:{mgr} | 最大回撤:{dd_str}")
    
    # 风险分析对比
    lines.append("\n风险对比:")
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
    注意：回复中不要显示基金代码。
    """
    info = _get_fund_data(fund_code)
    if not info:
        return f"无法获取该基金的数据。"
    
    history = info.get("历史净值", [])
    if not history:
        return f"该基金没有足够的历史净值数据进行定投计算。"
    
    name = info.get("基金名称", fund_code)
    
    # 取足够的历史数据
    step = 1 if frequency == "weekly" else 4
    needed = periods * step
    
    if len(history) < needed:
        needed = len(history)
        periods = needed // step
    
    recent_history = history[-needed:] if needed > 0 else history
    
    if len(recent_history) < 2:
        return "历史数据不足，无法计算。"
    
    # 模拟定投
    total_invested = 0
    total_shares = 0
    investments_made = 0
    
    for i, h in enumerate(recent_history):
        if i % step == 0:
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
    
    avg_cost = total_invested / total_shares if total_shares > 0 else 0
    
    freq_str = "周" if frequency == "weekly" else "月"
    
    lines = [
        f"{name} 定投回测：",
        "-" * 30,
        f"定投方式: 每{freq_str}定投 {amount:.2f}元",
        f"定投次数: {investments_made} 次",
        f"总投资额: {total_invested:.2f}元",
        f"累计份额: {total_shares:.2f}份",
        f"最新净值: {latest_nav:.4f}",
        f"成本均价: {avg_cost:.4f}",
        f"最终市值: {final_value:.2f}元",
        f"总收益: {total_return:+.2f}元（{return_pct:+.2f}%）",
    ]
    
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
            return "暂时无法获取市场数据。"
        
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
            return f"没有找到相关类型的基金数据。"
        
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
            f"{category_name}基金市场概况：",
            "-" * 30,
            f"统计基金数: {total} 支",
            f"今日上涨: {up_count} 支",
            f"今日下跌: {down_count} 支",
        ]
        
        lines.append("\n今日涨幅TOP5:")
        for i, f in enumerate(top_5, 1):
            lines.append(f"  {i}. {f.get('基金名称', '')}  {f.get('日涨跌幅', 0):+.2f}%")
        
        lines.append("\n今日跌幅TOP5:")
        for i, f in enumerate(bottom_5, 1):
            lines.append(f"  {i}. {f.get('基金名称', '')}  {f.get('日涨跌幅', 0):+.2f}%")
        
        return "\n".join(lines)
    
    except Exception as e:
        return f"获取市场概况时出错: {str(e)}"


# ============================================================
# 工具：用户持仓管理（数据库持久化）
# ============================================================

class UpdatePortfolioInput(BaseModel):
    user_id: str = Field(default="default_user", description="用户标识")
    fund_code: str = Field(default="", description="基金代码，如 '110011'。如果不知道代码，可传空字符串，通过fund_name自动搜索")
    fund_name: str = Field(default="", description="基金名称，如'易方达优质精选混合'。如果知道基金代码可以直接传代码，名称留空")
    cost_amount: float = Field(description="总投入金额（元），如 10000")
    channel: str = Field(default="", description="存储渠道，如'支付宝'、'天天基金'、'银行'、'微信'等")

@tool(args_schema=UpdatePortfolioInput)
def update_user_portfolio(user_id: str, fund_code: str = "", fund_name: str = "",
                          cost_amount: float = 0, channel: str = "") -> str:
    """
    添加或更新用户的基金持仓信息。
    用户只需告知投入金额和存储渠道（如支付宝），系统自动根据最新净值计算持有份额。
    如果用户已持有该基金则更新，否则新增。
    数据会持久化到数据库中，并自动计算当前市值和盈亏率。
    注意：回复中不要显示基金代码。
    """
    # 如果只有基金名称没有代码，尝试搜索代码
    if not fund_code and fund_name:
        searched_code = _search_fund_code_by_name(fund_name)
        if searched_code:
            fund_code = searched_code
            logger.info(f"通过名称搜索到基金代码: {fund_name} -> {fund_code}")
    
    if not fund_code:
        logger.error(f"[DBG] 未找到基金代码，fund_name={fund_name}")
        # 记录全局持仓状态
        logger.info(f"[DBG] 当前内存持仓: user_id={user_id}, portfolios_keys={list(_global_portfolios.keys())}")
        if user_id in _global_portfolios:
            logger.info(f"[DBG] 用户持仓明细: {json.dumps(_global_portfolios[user_id].get('funds', []), ensure_ascii=False)}")
        return f"无法找到基金「{fund_name}」对应的代码，请输入更准确的基金名称。"
    
    logger.info(f"[DBG] 更新持仓: user={user_id}, code={fund_code}, name={fund_name}, cost={cost_amount}, channel={channel}")
    
    # 自动获取基金名称
    if not fund_name:
        info = _get_fund_data(fund_code)
        if info:
            fund_name = info.get("基金名称", "")
    
    if not fund_name:
        basic = get_fund_basic_info(fund_code)
        if basic:
            fund_name = basic.get("基金名称", fund_code)
        else:
            fund_name = fund_code
    
    # 获取最新净值，自动计算持有份额
    from fund_data.fetcher import get_fund_realtime_estimate
    realtime = get_fund_realtime_estimate(fund_code)
    nav = 0
    if realtime:
        nav = realtime.get("估算净值", 0) or realtime.get("昨日净值", 0)
    
    shares = cost_amount / nav if nav > 0 else 0
    
    # 计算当前市值和盈亏率
    current_value = shares * nav if nav > 0 else cost_amount
    profit_rate = ((current_value - cost_amount) / cost_amount * 100) if cost_amount > 0 else 0
    
    # 保存到数据库
    success = _run_async(_db_manager.save_user_portfolio(user_id, fund_code, fund_name, cost_amount, shares, channel))
    
    if success:
        return f"已保存 {fund_name} 的持仓信息（投入{cost_amount:.2f}元）。当前净值{nav:.4f}，持有{shares:.2f}份。"
    else:
        raise Exception("数据库保存失败")


class DeletePortfolioInput(BaseModel):
    user_id: str = Field(default="default_user", description="用户标识")
    fund_code: str = Field(description="基金代码，如 '110011'")

@tool(args_schema=DeletePortfolioInput)
def delete_user_portfolio(user_id: str, fund_code: str) -> str:
    """
    删除用户的某支基金持仓。
    """
    name = _get_fund_name(fund_code)
    
    # 从内存删除
    if user_id in _global_portfolios:
        _global_portfolios[user_id]["funds"] = [
            f for f in _global_portfolios[user_id]["funds"] if f["code"] != fund_code
        ]
    
    # 同步从数据库删除
    success = _run_async(_db_manager.delete_user_portfolio(user_id, fund_code))
    
    if success:
        return f"已删除 {name} 的持仓信息。"
    else:
        return f"删除 {name} 的持仓信息失败。"


# ============================================================
# 工具：用户画像管理
# ============================================================

class GetUserProfileInput(BaseModel):
    user_id: str = Field(default="default_user", description="用户标识")

@tool(args_schema=GetUserProfileInput)
def get_user_profile_tool(user_id: str = "default_user") -> str:
    """
    查询用户在数据库中的画像信息（风险偏好、职业、收入）。
    首次对话时调用此工具判断是否需要新建画像。
    """
    profile = _run_async(_db_manager.get_user_profile(user_id))
    if profile:
        return (
            f"用户画像: {profile.get('risk_type', '未知')}, "
            f"职业: {profile.get('occupation', '未知')}, "
            f"收入: {profile.get('income_range', '未知')}"
        )
    return f"用户 {user_id} 还没有画像信息，需要询问其风险偏好、职业和收入。"


class UpdateUserProfileInput(BaseModel):
    user_id: str = Field(default="default_user", description="用户标识")
    risk_type: str = Field(default="稳健型", description="风险类型: '稳健型', '激进型'")
    occupation: str = Field(default="", description="职业")
    income_range: str = Field(default="", description="收入范围")

@tool(args_schema=UpdateUserProfileInput)
def update_user_profile_tool(user_id: str = "default_user", risk_type: str = "稳健型",
                              occupation: str = "", income_range: str = "") -> str:
    """
    保存或更新用户的画像信息（风险偏好、职业、收入）。
    当用户告知其风险偏好、职业或收入时调用此工具存储。
    """
    _run_async(_db_manager.save_user_profile(user_id, risk_type, occupation, income_range))
    return f"已保存用户画像: {risk_type}, 职业:{occupation}, 收入:{income_range}"


# ============================================================
# 获取所有工具
# ============================================================

def get_all_tools(db_config: dict = None) -> List:
    """获取所有可用的LangChain工具"""
    global _db_config, _db_manager
    if db_config:
        _db_config = db_config
        _db_manager.config = db_config
    
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
        update_user_portfolio,
        delete_user_portfolio,
        get_user_profile_tool,
        update_user_profile_tool,
    ]
