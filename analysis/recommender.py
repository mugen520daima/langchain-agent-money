"""
基金推荐算法引擎

基于多因子量化评分模型，从全市场基金中筛选推荐优质基金。

评分模型基于以下维度：
1. 收益因子（权重60%）：近1月、3月、6月、1年、3年收益加权
2. 风险因子（权重20%）：最大回撤、波动率（负向）
3. 稳定因子（权重10%）：基金经理稳定性、基金评级
4. 规模因子（权重10%）：适度规模加分，过大/过小减分

评分公式：
    Score = Σ(W_i * S_i)
    其中 W_i 为各因子权重，S_i 为各因子标准化得分（0-100分）
"""

from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import numpy as np


class FundRecommender:
    """基金推荐器"""

    # 默认评分权重
    DEFAULT_WEIGHTS = {
        "recent_1m": 0.08,
        "recent_3m": 0.12,
        "recent_6m": 0.15,
        "recent_1y": 0.20,
        "recent_3y": 0.15,
        "max_drawdown_neg": 0.10,   # 最大回撤（负向）
        "volatility_neg": 0.05,     # 波动率（负向）
        "manager_stability": 0.05,  # 基金经理稳定性
        "fund_rating": 0.05,        # 基金评级
        "size_score": 0.05,         # 规模评分
    }

    # 推荐基金类型偏好
    PREFERRED_TYPES = [
        "混合型", "股票型", "指数型", "LOF", "ETF"
    ]

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

        # 如果传入的权重总和不为1，进行归一化
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            for k in self.weights:
                self.weights[k] /= total

    def score_fund(self, fund_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        对单个基金进行综合评分

        Args:
            fund_data: 基金数据字典，包含收益率、规模、评级等信息

        Returns:
            {
                "基金代码": ...,
                "基金名称": ...,
                "综合评分": 0-100,
                "各维度评分": {...},
                "评分详情": "..."
            }
        """
        scores = {}
        reasons = []

        # ---- 1. 收益因子评分 ----
        returns = fund_data.get("收益率", fund_data)
        income_scores = {}

        # 近1月评分 (0-100)
        r1m = returns.get("近1月", 0)
        income_scores["近1月"] = self._normalize_return(r1m, 1)
        reasons.append(f"近1月收益{r1m:.2f}%")

        # 近3月评分
        r3m = returns.get("近3月", 0)
        income_scores["近3月"] = self._normalize_return(r3m, 3)
        reasons.append(f"近3月收益{r3m:.2f}%")

        # 近6月评分
        r6m = returns.get("近6月", 0)
        income_scores["近6月"] = self._normalize_return(r6m, 6)
        reasons.append(f"近6月收益{r6m:.2f}%")

        # 近1年评分
        r1y = returns.get("近1年", 0)
        income_scores["近1年"] = self._normalize_return(r1y, 12)
        reasons.append(f"近1年收益{r1y:.2f}%")

        # 近3年评分
        r3y = returns.get("近3年", 0)
        income_scores["近3年"] = self._normalize_return(r3y, 36)
        reasons.append(f"近3年收益{r3y:.2f}%")

        scores["收益评分"] = (
            income_scores["近1月"] * self.weights["recent_1m"] +
            income_scores["近3月"] * self.weights["recent_3m"] +
            income_scores["近6月"] * self.weights["recent_6m"] +
            income_scores["近1年"] * self.weights["recent_1y"] +
            income_scores["近3年"] * self.weights["recent_3y"]
        ) / sum(self.weights.get(k, 0) for k in
                ["recent_1m", "recent_3m", "recent_6m", "recent_1y", "recent_3y"])

        # 综合收益说明
        scores["收益详情"] = income_scores

        # ---- 2. 风险因子评分 ----
        risk_scores = {}

        # 最大回撤评分
        max_dd = fund_data.get("最大回撤")
        if max_dd is not None:
            dd_score = self._score_max_drawdown(abs(max_dd))
            risk_scores["最大回撤"] = dd_score
            reasons.append(f"最大回撤{abs(max_dd):.2f}%")
        else:
            dd_score = 50
            risk_scores["最大回撤"] = 50
            reasons.append("最大回撤数据未知")

        # 日涨跌幅波动评分 (近1月收益波动)
        day_change = returns.get("日涨跌幅", 0)
        vol_score = self._score_volatility(abs(day_change))
        risk_scores["日波动"] = vol_score
        reasons.append(f"日涨跌幅{day_change:.2f}%")

        scores["风险评分"] = (
            dd_score * self.weights.get("max_drawdown_neg", 0.10) +
            vol_score * self.weights.get("volatility_neg", 0.05)
        ) / (self.weights.get("max_drawdown_neg", 0.10) +
             self.weights.get("volatility_neg", 0.05))

        scores["风险详情"] = risk_scores

        # ---- 3. 稳定因子评分 ----
        stability_scores = {}

        # 基金经理稳定性
        managers = fund_data.get("基金经理列表", [])
        if managers:
            # 取第一位基金经理的任职天数
            top_mgr = managers[0]
            tenure_days = top_mgr.get("任职天数", 0)
            mgr_score = self._score_manager_tenure(tenure_days)
            stability_scores["经理稳定性"] = mgr_score
            reasons.append(f"经理任职{tenure_days}天")
        else:
            mgr_score = 50
            stability_scores["经理稳定性"] = 50

        # 基金评级
        rating = fund_data.get("基金评级", "")
        rating_score = self._score_rating(rating)
        stability_scores["基金评级"] = rating_score
        reasons.append(f"评级{rating}" if rating else "评级未知")

        scores["稳定评分"] = (
            mgr_score * self.weights.get("manager_stability", 0.05) +
            rating_score * self.weights.get("fund_rating", 0.05)
        ) / (self.weights.get("manager_stability", 0.05) +
             self.weights.get("fund_rating", 0.05))

        scores["稳定详情"] = stability_scores

        # ---- 4. 规模因子评分 ----
        size = fund_data.get("基金规模(亿)", 0)
        size_score = self._score_fund_size(size)
        scores["规模评分"] = size_score
        reasons.append(f"规模{size:.1f}亿")

        # ---- 5. 综合评分 ----
        total_income_weight = sum(self.weights.get(k, 0) for k in
                                  ["recent_1m", "recent_3m", "recent_6m",
                                   "recent_1y", "recent_3y"])
        total_risk_weight = (self.weights.get("max_drawdown_neg", 0.10) +
                             self.weights.get("volatility_neg", 0.05))
        total_stable_weight = (self.weights.get("manager_stability", 0.05) +
                               self.weights.get("fund_rating", 0.05))
        total_size_weight = self.weights.get("size_score", 0.05)

        # 归一化权重
        total_w = total_income_weight + total_risk_weight + total_stable_weight + total_size_weight

        final_score = (
            scores["收益评分"] * total_income_weight +
            scores["风险评分"] * total_risk_weight +
            scores["稳定评分"] * total_stable_weight +
            size_score * total_size_weight
        ) / total_w

        # 生成评分星级
        star_rating = self._score_to_stars(final_score)

        return {
            "基金代码": fund_data.get("基金代码", ""),
            "基金名称": fund_data.get("基金名称", ""),
            "基金类型": fund_data.get("基金类型", ""),
            "综合评分": round(final_score, 1),
            "星级": star_rating,
            "各维度评分": {
                "收益评分": round(scores["收益评分"], 1),
                "风险评分": round(scores["风险评分"], 1),
                "稳定评分": round(scores["稳定评分"], 1),
                "规模评分": round(size_score, 1),
            },
            "评分依据": "; ".join(reasons),
        }

    def recommend(self, fund_list: List[Dict[str, Any]],
                  top_n: int = 5,
                  exclude_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        从基金列表中推荐优质基金

        Args:
            fund_list: 基金数据列表
            top_n: 推荐数量
            exclude_codes: 需要排除的基金代码（用户已持有的）

        Returns:
            评分最高的 top_n 支基金
        """
        exclude_codes = exclude_codes or []

        # 过滤掉用户已持有的基金
        candidates = [f for f in fund_list
                      if f.get("基金代码", "") not in exclude_codes]

        if not candidates:
            return []

        # 对每个基金进行评分
        scored = []
        for fund in candidates:
            # 过滤掉非偏股/混合型基金
            ftype = fund.get("基金类型", "")
            if not any(pt in ftype for pt in self.PREFERRED_TYPES):
                continue
            try:
                result = self.score_fund(fund)
                scored.append(result)
            except Exception as e:
                print(f"评分基金 {fund.get('基金代码', '')} 失败: {e}")
                continue

        # 按综合评分排序
        scored.sort(key=lambda x: x["综合评分"], reverse=True)

        # 返回前N名
        return scored[:top_n]

    def _normalize_return(self, ret: float, months: int) -> float:
        """
        将收益率标准化到0-100分

        使用非线性映射：对正收益高分，负收益低分
        基准：月均收益1%为60分
        """
        if months <= 0:
            return 50

        monthly_ret = ret / months  # 月均收益率

        # Sigmoid-like 映射
        # 月均收益 0% -> 50分, +2% -> 80分, +5% -> 95分
        # 月均收益 -2% -> 20分, -5% -> 5分
        raw_score = 50 * (1 + np.tanh(monthly_ret * 0.5))

        return max(0, min(100, raw_score))

    def _score_max_drawdown(self, max_dd: float) -> float:
        """
        最大回撤评分
        回撤越小（绝对值），分数越高
        回撤<5% -> 90-100分
        回撤5-10% -> 70-90分
        回撤10-20% -> 40-70分
        回撤20-30% -> 10-40分
        回撤>30% -> 0-10分
        """
        if max_dd <= 5:
            return 100 - (max_dd / 5) * 10
        elif max_dd <= 10:
            return 90 - ((max_dd - 5) / 5) * 20
        elif max_dd <= 20:
            return 70 - ((max_dd - 10) / 10) * 30
        elif max_dd <= 30:
            return 40 - ((max_dd - 20) / 10) * 30
        else:
            return max(0, 10 - (max_dd - 30) / 10 * 10)

    def _score_volatility(self, daily_change: float) -> float:
        """
        波动率评分
        波动越小越稳定，分数越高
        """
        if daily_change <= 1:
            return 90
        elif daily_change <= 3:
            return 70
        elif daily_change <= 5:
            return 50
        elif daily_change <= 7:
            return 30
        else:
            return 10

    def _score_manager_tenure(self, days: int) -> float:
        """基金经理任职时长评分"""
        if days >= 1095:  # 3年以上
            return 90
        elif days >= 730:  # 2年以上
            return 75
        elif days >= 365:  # 1年以上
            return 60
        elif days >= 180:
            return 40
        else:
            return 20

    def _score_rating(self, rating: str) -> float:
        """基金评级评分"""
        rating_map = {
            "★★★★★": 95,
            "★★★★": 80,
            "★★★": 60,
            "★★": 30,
            "★": 10,
        }
        for key, val in rating_map.items():
            if key in str(rating):
                return val
        return 50

    def _score_fund_size(self, size_billion: float) -> float:
        """基金规模评分（单位：亿元）"""
        if size_billion <= 0:
            return 0
        elif size_billion <= 1:
            return 20  # 迷你基金
        elif size_billion <= 5:
            return 40  # 偏小
        elif size_billion <= 20:
            return 80  # 适中偏小，灵活
        elif size_billion <= 50:
            return 90  # 适中，最佳
        elif size_billion <= 100:
            return 85  # 适中偏大
        elif size_billion <= 200:
            return 70  # 偏大
        elif size_billion <= 500:
            return 50  # 大
        else:
            return 30  # 超大

    def _score_to_stars(self, score: float) -> str:
        """综合评分转为星级"""
        if score >= 90:
            return "★★★★★"
        elif score >= 75:
            return "★★★★☆"
        elif score >= 60:
            return "★★★☆☆"
        elif score >= 40:
            return "★★☆☆☆"
        else:
            return "★☆☆☆☆"

    def get_recommendation_summary(self, recommendations: List[Dict]) -> List[Dict]:
        """
        生成推荐摘要（含简要理由）
        """
        result = []
        for i, rec in enumerate(recommendations, 1):
            detail = rec.get("各维度评分", {})
            result.append({
                "排名": i,
                "基金代码": rec.get("基金代码", ""),
                "基金名称": rec.get("基金名称", ""),
                "基金类型": rec.get("基金类型", ""),
                "综合评分": rec.get("综合评分", 0),
                "星级": rec.get("星级", ""),
                "评分详情": (
                    f"收益{detail.get('收益评分', 0):.0f}分 | "
                    f"风控{detail.get('风险评分', 0):.0f}分 | "
                    f"稳定{detail.get('稳定评分', 0):.0f}分 | "
                    f"规模{detail.get('规模评分', 0):.0f}分"
                ),
                "评分依据": rec.get("评分依据", ""),
            })
        return result
