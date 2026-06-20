"""
基金报告生成器

生成格式化的基金分析报告，包含：
1. 持仓概览
2. 逐项持仓分析
3. 风险与异动提醒
4. 基金推荐
5. 投资建议
"""

from typing import Dict, List, Optional, Any
from datetime import datetime


class ReportGenerator:
    """基金报告生成器"""

    def __init__(self, language: str = "zh"):
        self.language = language

    def generate_full_report(
        self,
        portfolio_analysis: Dict[str, Any],
        risk_warnings: Dict[str, List[Dict]],
        recommendations: List[Dict],
        user_name: str = "用户",
    ) -> str:
        """
        生成完整基金报告

        Args:
            portfolio_analysis: 持仓分析结果
            risk_warnings: {基金代码: [风险警告]} 所有基金的风险警告
            recommendations: 推荐基金列表
            user_name: 用户名

        Returns:
            格式化的报告文本
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        lines = []
        lines.append("=" * 60)
        lines.append(f"📋 基金持仓分析报告")
        lines.append(f"   {user_name} | {now}")
        lines.append("=" * 60)
        lines.append("")

        # ===== 第一部分：持仓概览 =====
        lines.append(self._section_title("一、持仓概览"))

        overview = portfolio_analysis.get("整体评价", {})
        concentration = portfolio_analysis.get("集中度分析", {})

        lines.append(f"💰 总投入：{portfolio_analysis.get('总投入(元)', 0):,.2f} 元")
        lines.append(f"📊 总市值：{portfolio_analysis.get('总市值(元)', 0):,.2f} 元")
        profit = portfolio_analysis.get("总盈亏(元)", 0)
        profit_pct = portfolio_analysis.get("总盈亏比例(%)", 0)
        profit_emoji = "📈" if profit >= 0 else "📉"
        lines.append(f"{profit_emoji} 总盈亏：{profit:+,.2f} 元 ({profit_pct:+.2f}%)")
        lines.append(f"🏆 收益评价：{overview.get('收益评价', '')}")
        lines.append(f"📋 持仓质量：{overview.get('持仓质量', '')}")
        lines.append(f"📈 趋势判断：{overview.get('趋势判断', '')}")
        lines.append(f"📊 集中度：{concentration.get('集中度等级', '')} "
                      f"(前3持仓占比 {concentration.get('前3持仓占比(%)', 0):.1f}%)")
        lines.append("")

        # 操作建议
        lines.append(f"💡 操作建议：{overview.get('建议操作', '')}")
        lines.append("")

        # 集中度建议
        lines.append(f"💡 集中度建议：{concentration.get('建议', '')}")
        lines.append("")

        # ===== 第二部分：持仓明细 =====
        lines.append(self._section_title("二、持仓明细分析"))
        items = portfolio_analysis.get("持仓明细", [])

        for i, item in enumerate(items, 1):
            lines.append(f"── {i}. {item.get('基金名称', '')} ({item.get('基金代码', '')}) ──")
            lines.append(f"   投入: {item.get('投入成本(元)', 0):,.2f}元 | "
                         f"市值: {item.get('当前市值(元)', 0):,.2f}元")
            lines.append(f"   盈亏: {item.get('盈亏(元)', 0):+,.2f}元 "
                         f"({item.get('盈亏比例(%)', 0):+.2f}%) | "
                         f"仓位: {item.get('仓位占比(%)', 0):.1f}%")
            lines.append(f"   当日涨跌: {item.get('当日涨跌幅(%)', 0):+.2f}%")

            # 中长期评价
            mid_long = item.get("中长期评价", {})
            lines.append(f"   中长期评价: {mid_long.get('评价', '')} "
                         f"(评分: {mid_long.get('评分', 'N/A')})")
            lines.append(f"   评价说明: {mid_long.get('说明', '')}")

            # 中长期收益明细
            detail = mid_long.get("明细", {})
            if detail:
                lines.append(f"   收益明细: 近3月 {detail.get('近3月', 'N/A')} | "
                             f"近6月 {detail.get('近6月', 'N/A')} | "
                             f"近1年 {detail.get('近1年', 'N/A')} | "
                             f"近3年 {detail.get('近3年', 'N/A')}")

            # 持仓质量
            quality = item.get("持仓质量", {})
            lines.append(f"   持仓质量: {quality.get('等级', '')}")
            lines.append(f"   建议: {quality.get('建议', '')}")
            lines.append("")

        # ===== 第三部分：风险与异动提醒 =====
        lines.append(self._section_title("三、风险与异动提醒"))

        total_warnings = 0
        for code, warnings in risk_warnings.items():
            total_warnings += len(warnings)

        if total_warnings == 0:
            lines.append("✅ 未发现明显风险信号，整体运行健康。")
        else:
            lines.append(f"共发现 {total_warnings} 项风险提示：")
            lines.append("")

            for code, warnings in risk_warnings.items():
                if not warnings:
                    continue
                # 找到对应的基金名称
                fund_name = code
                for item in items:
                    if item.get("基金代码") == code:
                        fund_name = item.get("基金名称", code)
                        break
                lines.append(f"【{fund_name} ({code})】")
                for w in warnings:
                    lines.append(f"  {w.get('等级', '')} {w.get('类型', '')}: "
                                 f"{w.get('描述', '')}")
                lines.append("")

        # ===== 第四部分：基金推荐 =====
        if recommendations:
            lines.append(self._section_title("四、基金推荐"))
            lines.append(f"基于多因子量化模型，为您推荐以下{len(recommendations)}支优质基金：")
            lines.append("")

            for i, rec in enumerate(recommendations, 1):
                lines.append(f"{i}. {rec.get('基金名称', '')} "
                             f"({rec.get('基金代码', '')})")
                lines.append(f"   类型: {rec.get('基金类型', '')} | "
                             f"综合评分: {rec.get('综合评分', 0):.1f}分 "
                             f"{rec.get('星级', '')}")
                lines.append(f"   评分详情: {rec.get('评分详情', '')}")
                lines.append(f"   评分依据: {rec.get('评分依据', '')}")
                lines.append("")

        # ===== 第五部分：投资寄语 =====
        lines.append(self._section_title("五、投资寄语"))
        lines.append(self._get_investment_quote())
        lines.append("")
        lines.append("=" * 60)
        lines.append("📌 免责声明：本报告仅供参考，不构成投资建议。")
        lines.append("   基金投资有风险，决策需谨慎。")
        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_quick_report(
        self,
        fund_info: Dict[str, Any],
        holdings: List[Dict],
        risk_warnings: List[Dict],
        recommendations: Optional[List[Dict]] = None,
    ) -> str:
        """
        生成快速查询报告（单支基金查询）

        Args:
            fund_info: 基金综合信息
            holdings: 该基金用户持仓计算
            risk_warnings: 风险警告
            recommendations: 推荐基金

        Returns:
            报告文本
        """
        lines = []

        # 标题
        name = fund_info.get("基金名称", "")
        code = fund_info.get("基金代码", "")
        lines.append(f"📊 {name} ({code}) 基金快报")
        lines.append("─" * 40)

        # 基本信息
        nav = holdings[0].get("当前净值(元)", 0) if holdings else fund_info.get("单位净值", 0)
        day_change = holdings[0].get("当日涨跌幅(%)", 0) if holdings else fund_info.get("估算涨跌幅", 0)
        lines.append(f"单位净值: {nav:.4f} 元")
        lines.append(f"当日涨跌: {day_change:+.2f}%")
        lines.append(f"基金类型: {fund_info.get('基金类型', '未知')}")
        lines.append(f"基金规模: {fund_info.get('基金规模(亿)', 0):.2f} 亿元")
        lines.append(f"基金经理: {fund_info.get('基金经理', '未知')}")
        lines.append(f"成立日期: {fund_info.get('成立日期', '未知')}")
        lines.append("")

        # 收益率
        returns = fund_info.get("收益率", {})
        if returns:
            lines.append("📈 阶段收益:")
            lines.append(f"  近1月: {returns.get('近1月', 0):+.2f}%  |  "
                         f"近3月: {returns.get('近3月', 0):+.2f}%")
            lines.append(f"  近6月: {returns.get('近6月', 0):+.2f}%  |  "
                         f"近1年: {returns.get('近1年', 0):+.2f}%")
            lines.append(f"  近3年: {returns.get('近3年', 0):+.2f}%  |  "
                         f"成立以来: {returns.get('成立以来', 0):+.2f}%")
            lines.append("")

        # 持仓分析
        if holdings:
            h = holdings[0]
            lines.append("💰 持仓分析:")
            lines.append(f"  投入: {h.get('总投入(元)', 0):,.2f} 元")
            lines.append(f"  市值: {h.get('当前市值(元)', 0):,.2f} 元")
            lines.append(f"  盈亏: {h.get('盈亏(元)', 0):+,.2f} 元 "
                         f"({h.get('盈亏比例(%)', 0):+.2f}%)")
            lines.append("")

        # 风险提醒
        if risk_warnings:
            lines.append("⚠️ 风险提醒:")
            for w in risk_warnings[:3]:
                lines.append(f"  {w.get('等级', '')} {w.get('类型', '')}: "
                             f"{w.get('指标', '')}")
            lines.append("")

        # 推荐
        if recommendations:
            lines.append("🎯 推荐关注:")
            for rec in recommendations[:3]:
                lines.append(f"  · {rec.get('基金名称', '')} "
                             f"({rec.get('基金代码', '')}) - "
                             f"评分{rec.get('综合评分', 0):.1f}")

        return "\n".join(lines)

    def _section_title(self, title: str) -> str:
        """生成章节标题"""
        return f"\n{'─' * 40}\n{title}\n{'─' * 40}"

    def _get_investment_quote(self) -> str:
        """获取投资寄语"""
        quotes = [
            '📖 "市场就像上帝一样，帮助那些自助的人；但和上帝不同，市场不会原谅那些不知道自己在做什么的人。" -- 沃伦-巴菲特',
            '📖 "投资成功的秘诀是：在别人贪婪时恐惧，在别人恐惧时贪婪。" -- 沃伦-巴菲特',
            '📖 "复利是世界第八大奇迹，理解它的人赚取它，不理解的人付出它。" -- 阿尔伯特-爱因斯坦',
            '📖 "投资的精髓不在于评估一个行业对社会的影响或它的增长前景，而在于确定一家公司的竞争优势。" -- 沃伦-巴菲特',
            '📖 "时间是好公司的朋友，是平庸公司的敌人。" -- 查理-芒格',
            '📖 "不进行研究的投资，就像打扑克从不看牌一样，必然失败。" -- 彼得-林奇',
            '📖 "基金投资的关键不是预测未来，而是做好资产配置和风险控制。" -- 投资箴言',
            '📖 "定投是普通投资者最有效的投资方式——通过分批买入摊平成本，弱化择时风险。" -- 投资箴言',
        ]
        import random
        return random.choice(quotes)

    def generate_recommendation_table(self, recommendations: List[Dict]) -> str:
        """
        生成推荐的格式表格（为微信展示优化）
        """
        lines = []
        lines.append("🎯 精选基金推荐（评分排名）")
        lines.append("─" * 40)
        for i, rec in enumerate(recommendations, 1):
            lines.append(f"{i}. {rec.get('基金名称', '')}")
            lines.append(f"   代码: {rec.get('基金代码', '')} | "
                         f"评分: {rec.get('综合评分', 0):.1f} {rec.get('星级', '')}")
            lines.append(f"   类型: {rec.get('基金类型', '')}")
            lines.append(f"   {rec.get('评分详情', '')}")
            lines.append("")
        return "\n".join(lines)
