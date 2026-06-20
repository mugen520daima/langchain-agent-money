"""
持仓分析引擎

对用户持仓进行综合分析，包括：
1. 持仓集中度分析
2. 行业暴露度分析
3. 持仓盈亏分析
4. 中长期收益评价
5. 资产配置建议
"""

from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
from datetime import datetime


class PortfolioAnalyzer:
    """持仓分析器"""

    def __init__(self):
        pass

    def analyze_portfolio(self, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析完整的投资组合

        Args:
            holdings: 持仓列表，每项包含:
                {
                    "基金代码": str,
                    "基金名称": str,
                    "总投入(元)": float,
                    "持有份额": float,
                    "当前净值(元)": float,
                    "当前市值(元)": float,
                    "盈亏(元)": float,
                    "盈亏比例(%)": float,
                    "当日涨跌幅(%)": float,
                    ...
                }

        Returns:
            分析报告字典
        """
        total_cost = sum(h.get("总投入(元)", 0) for h in holdings)
        total_value = sum(h.get("当前市值(元)", 0) for h in holdings)
        total_profit = sum(h.get("盈亏(元)", 0) for h in holdings)
        total_profit_pct = (total_profit / total_cost * 100) if total_cost > 0 else 0

        # 逐项分析
        items = []
        for h in holdings:
            items.append(self._analyze_holding(h))

        # 整体评价
        overall = self._evaluate_overall(items, total_profit_pct)

        # 持仓集中度
        concentration = self._calc_concentration(items, total_value)

        return {
            "分析时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "总投入(元)": round(total_cost, 2),
            "总市值(元)": round(total_value, 2),
            "总盈亏(元)": round(total_profit, 2),
            "总盈亏比例(%)": round(total_profit_pct, 2),
            "持仓明细": items,
            "集中度分析": concentration,
            "整体评价": overall,
        }

    def _analyze_holding(self, holding: Dict[str, Any]) -> Dict[str, Any]:
        """分析单支持仓"""
        code = holding.get("基金代码", "")
        name = holding.get("基金名称", "")
        cost = holding.get("总投入(元)", 0)
        value = holding.get("当前市值(元)", 0)
        profit = holding.get("盈亏(元)", 0)
        profit_pct = holding.get("盈亏比例(%)", 0)
        day_change = holding.get("当日涨跌幅(%)", 0)

        # 中长期收益评价
        medium_long_eval = self._evaluate_medium_long_term(holding)

        # 收益质量判断
        quality = self._judge_quality(profit_pct, medium_long_eval["评分"])

        return {
            "基金代码": code,
            "基金名称": name,
            "投入成本(元)": round(cost, 2),
            "当前市值(元)": round(value, 2),
            "盈亏(元)": round(profit, 2),
            "盈亏比例(%)": round(profit_pct, 2),
            "当日涨跌幅(%)": day_change,
            "中长期评价": medium_long_eval,
            "持仓质量": quality,
            "仓位占比(%)": 0,  # 稍后计算
        }

    def _evaluate_medium_long_term(self, holding: Dict) -> Dict[str, Any]:
        """
        评价基金的中长期表现

        评价维度：
        - 中长期收益稳定性
        - 相对于同类基金的表现
        - 风险调整后收益

        评分标准（0-100）：
        - 近3月 > 10% 且 近6月 > 15% 且 近1年 > 20%：优秀 (90-100)
        - 近3月 > 5% 且 近1年 > 10%：良好 (70-89)
        - 正收益但偏低：一般 (50-69)
        - 轻微亏损：较差 (30-49)
        - 大幅亏损：差 (0-29)
        """
        returns = holding.get("收益率", {})

        if not returns:
            return {
                "评分": None,
                "评价": "数据不足",
                "等级": "未知",
                "说明": "无法获取该基金的中长期收益数据，建议在天天基金网查询。",
            }

        r3m = returns.get("近3月", 0)
        r6m = returns.get("近6月", 0)
        r1y = returns.get("近1年", 0)
        r3y = returns.get("近3年", 0)

        # 计算综合评分
        score = 0
        reasons = []

        if r3y:
            if r3y > 50:
                score += 40
                reasons.append(f"近3年+{r3y:.2f}% 长期表现出色")
            elif r3y > 20:
                score += 30
                reasons.append(f"近3年+{r3y:.2f}% 长期表现良好")
            elif r3y > 0:
                score += 20
                reasons.append(f"近3年+{r3y:.2f}% 长期正收益")
            else:
                score += 5
                reasons.append(f"近3年{r3y:.2f}% 长期亏损")

        if r1y:
            if r1y > 20:
                score += 30
                reasons.append(f"近1年+{r1y:.2f}% 近期表现优秀")
            elif r1y > 10:
                score += 25
                reasons.append(f"近1年+{r1y:.2f}% 近期表现良好")
            elif r1y > 0:
                score += 15
                reasons.append(f"近1年+{r1y:.2f}% 近期正收益")
            else:
                score += 5
                reasons.append(f"近1年{r1y:.2f}% 近期下跌")

        if r6m:
            if r6m > 15:
                score += 20
            elif r6m > 5:
                score += 15
            elif r6m > 0:
                score += 10
            else:
                score += 3

        if r3m:
            if r3m > 10:
                score += 10
            elif r3m > 3:
                score += 8
            elif r3m > 0:
                score += 5
            else:
                score += 2

        # 确定等级
        if score >= 80:
            level = "⭐ 优秀"
            desc = "该基金中长期表现非常出色，收益稳定且持续跑赢同类，是优质的持仓标的。"
        elif score >= 60:
            level = "👍 良好"
            desc = "该基金中长期表现良好，具备较强的盈利能力，值得继续持有。"
        elif score >= 40:
            level = "📊 一般"
            desc = "该基金中长期表现平平，收益能力一般，建议关注同类表现更好的基金。"
        elif score >= 20:
            level = "⚠️ 较差"
            desc = "该基金中长期表现较差，持续亏损或大幅跑输同类，建议考虑调整。"
        else:
            level = "❌ 差"
            desc = "该基金中长期表现很差，持续大幅亏损，强烈建议尽快赎回换仓。"

        return {
            "评分": round(min(100, score), 1),
            "评价": level,
            "等级": level.split(" ")[1] if " " in level else level,
            "说明": desc,
            "依据": "; ".join(reasons),
            "明细": {
                "近3月": f"{r3m:.2f}%" if r3m else "无数据",
                "近6月": f"{r6m:.2f}%" if r6m else "无数据",
                "近1年": f"{r1y:.2f}%" if r1y else "无数据",
                "近3年": f"{r3y:.2f}%" if r3y else "无数据",
            }
        }

    def _judge_quality(self, profit_pct: float,
                       medium_long_score: Optional[float]) -> Dict[str, str]:
        """判断持仓质量"""
        if medium_long_score is None:
            # 当长期评价数据不足时，使用盈亏比例做简单判断
            if profit_pct > 10:
                return {
                    "等级": "盈利良好 ✅",
                    "建议": f"当前盈利{profit_pct:.1f}%，收益可观。建议继续持有的同时关注市场变化。",
                }
            elif profit_pct > 0:
                return {
                    "等级": "小幅盈利 📈",
                    "建议": f"当前盈利{profit_pct:.1f}%，表现尚可。可继续持有观察。",
                }
            elif profit_pct >= -10:
                return {
                    "等级": "小幅浮亏 📉",
                    "建议": f"当前浮亏{abs(profit_pct):.1f}%，在正常波动范围内。建议持续关注。",
                }
            elif profit_pct >= -20:
                return {
                    "等级": "需关注 ⚠️",
                    "建议": f"当前浮亏{abs(profit_pct):.1f}%，亏损较大。建议评估是否继续持有或设止损。",
                }
            else:
                return {
                    "等级": "深度亏损 ❌",
                    "建议": f"当前浮亏{abs(profit_pct):.1f}%，亏损严重。强烈建议审视投资逻辑。",
                }

        if profit_pct > 0 and medium_long_score >= 70:
            return {
                "等级": "优质持仓 ✅",
                "建议": "该基金盈利能力强，建议继续持有并适当加仓。",
            }
        elif profit_pct > 0 and medium_long_score >= 40:
            return {
                "等级": "中等持仓 📊",
                "建议": "目前有盈利但长期表现一般，可继续持有观察，不急于加仓。",
            }
        elif profit_pct > 0 and medium_long_score < 40:
            return {
                "等级": "需关注 ⚠️",
                "建议": "虽有盈利但长期表现偏弱，建议寻找更好的替代品种。",
            }
        elif profit_pct <= 0 and medium_long_score >= 70:
            return {
                "等级": "暂时浮亏 🔄",
                "建议": "短期浮亏但长期表现优秀，建议坚持定投或逢低加仓，长期持有。",
            }
        elif profit_pct <= 0 and medium_long_score >= 40:
            return {
                "等级": "需警惕 ⚠️",
                "建议": "浮亏且长期表现一般，建议设定止损线，观察后续表现。",
            }
        else:
            return {
                "等级": "建议止损 ❌",
                "建议": "浮亏较大且长期表现差，建议及时止损，换仓到更优质的基金。",
            }

    def _calc_concentration(self, items: List[Dict],
                            total_value: float) -> Dict[str, Any]:
        """计算持仓集中度"""
        if total_value <= 0:
            return {"说明": "总市值为0，无法计算"}

        # 计算各基金仓位占比
        for item in items:
            val = item.get("当前市值(元)", 0)
            item["仓位占比(%)"] = round(val / total_value * 100, 2) if total_value > 0 else 0

        # 按仓位排序
        sorted_items = sorted(items, key=lambda x: x["仓位占比(%)"], reverse=True)

        # 计算前三大持仓占比
        top3_ratio = sum(item["仓位占比(%)"] for item in sorted_items[:3])
        top1_ratio = sorted_items[0]["仓位占比(%)"] if sorted_items else 0

        if len(sorted_items) == 1:
            level = "全仓单支"
            suggestion = "全仓单支基金风险过于集中，建议分散投资3-5支不同类型基金。"
        elif top1_ratio > 50:
            level = "高度集中"
            suggestion = f"单支基金占比{top1_ratio:.1f}%过高，建议降低至30%以下以分散风险。"
        elif top3_ratio > 80:
            level = "较为集中"
            suggestion = f"前三支基金占比{top3_ratio:.1f}%，建议增配其他基金降低集中度。"
        elif top3_ratio > 60:
            level = "适中"
            suggestion = "持仓集中度适中，风险控制良好。"
        else:
            level = "分散"
            suggestion = "持仓较为分散，风险控制优秀。"

        return {
            "集中度等级": level,
            "前3持仓占比(%)": round(top3_ratio, 2),
            "最大单支占比(%)": round(top1_ratio, 2),
            "建议": suggestion,
        }

    def _evaluate_overall(self, items: List[Dict],
                          total_profit_pct: float) -> Dict[str, Any]:
        """整体持仓评价"""
        good_count = sum(1 for i in items if "优质" in i.get("持仓质量", {}).get("等级", ""))
        medium_count = sum(1 for i in items if "中等" in i.get("持仓质量", {}).get("等级", ""))
        warn_count = sum(1 for i in items if "需" in i.get("持仓质量", {}).get("等级", "") or "止损" in i.get("持仓质量", {}).get("等级", ""))

        total = len(items)

        if total_profit_pct > 20:
            profit_level = "🎉 大幅盈利"
            profit_desc = "整体持仓盈利丰厚，表现优秀！"
        elif total_profit_pct > 5:
            profit_level = "✅ 盈利"
            profit_desc = "整体持仓为正收益，表现良好。"
        elif total_profit_pct > -5:
            profit_level = "🔶 小幅亏损"
            profit_desc = "整体持仓小幅亏损，属于正常波动范围。"
        elif total_profit_pct > -15:
            profit_level = "⚠️ 较大亏损"
            profit_desc = "整体持仓亏损较大，建议审视持仓结构。"
        else:
            profit_level = "🔴 严重亏损"
            profit_desc = "整体持仓严重亏损，强烈建议采取调整措施。"

        if good_count == total:
            quality = "非常健康"
            action = "建议继续持有，可考虑适当加仓优质标的。"
        elif good_count >= total / 2:
            quality = "较为健康"
            action = "大部分持仓表现良好，建议优化表现不佳的部分。"
        elif warn_count >= total / 2:
            quality = "需要调整"
            action = "多数持仓表现不佳，建议认真审视投资策略。"
        else:
            quality = "有待改善"
            action = "持仓质量参差不齐，建议去弱留强。"
        # 计算加权中长期评分
        total_value = sum(i.get("当前市值(元)", 0) for i in items)
        scores = []
        for i in items:
            val = i.get("当前市值(元)", 0)
            eval_data = i.get("中长期评价", {})
            s = eval_data.get("评分")
            if s is not None and total_value > 0:
                scores.append(s * val / total_value)

        avg_score = sum(scores) if scores else None

        if avg_score:
            if avg_score >= 75:
                trend = "📈 上行趋势"
            elif avg_score >= 50:
                trend = "➡️ 震荡趋势"
            else:
                trend = "📉 下行趋势"
        else:
            trend = "数据不足"

        return {
            "收益评价": profit_level,
            "收益描述": profit_desc,
            "持仓质量": quality,
            "加权中长期评分(加权)": round(avg_score, 1) if avg_score else None,
            "趋势判断": trend,
            "建议操作": action,
        }
