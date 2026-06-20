"""
风险与异动分析模块

分析基金的风险指标和异常变动，包括：
1. 最大回撤异常
2. 基金经理变更预警
3. 基金规模异动
4. 行业集中度风险
5. 波动率异常
6. 近期业绩突变
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from collections import defaultdict


class RiskAnalyzer:
    """基金风险与异动分析器"""

    # 风险阈值配置
    THRESHOLDS = {
        "max_drawdown_warn": 15.0,       # 最大回撤超过此值预警（%）
        "max_drawdown_danger": 25.0,     # 最大回撤超过此值危险（%）
        "manager_tenure_warn_days": 180,  # 基金经理任职少于该天数预警
        "size_change_warn_pct": 50.0,    # 规模变化超过此值预警（%）
        "industry_concentration_warn": 60.0,  # 单一行业占比超过此值预警
        "volatility_warn": 5.0,          # 近期日波动率超过此值预警（%）
        "return_turnaround_warn": 10.0,  # 近期收益率较前期下降超过此值预警
        "consecutive_down_days": 5,      # 连续下跌天数预警
        "fund_size_tiny": 1.0,           # 规模小于此值预警（亿）
        "fund_size_huge": 300.0,         # 规模大于此值预警（亿，船大难掉头）
    }

    def __init__(self, custom_thresholds: Optional[Dict] = None):
        if custom_thresholds:
            self.THRESHOLDS.update(custom_thresholds)

    def analyze(self, fund_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        对单支基金进行全面的风险分析

        Args:
            fund_info: 基金的详细信息（来自 fetcher.get_fund_comprehensive_info）

        Returns:
            风险警告列表，每个警告包含类型、等级、描述
        """
        warnings = []

        # 1. 检查回撤风险
        warnings.extend(self._check_drawdown_risk(fund_info))

        # 2. 检查基金经理风险
        warnings.extend(self._check_manager_risk(fund_info))

        # 3. 检查规模风险
        warnings.extend(self._check_size_risk(fund_info))

        # 4. 检查行业集中度风险
        warnings.extend(self._check_industry_risk(fund_info))

        # 5. 检查业绩突变风险
        warnings.extend(self._check_performance_risk(fund_info))

        # 6. 检查近期连续下跌
        warnings.extend(self._check_consecutive_drop(fund_info))

        return warnings

    def _check_drawdown_risk(self, info: Dict) -> List[Dict]:
        """检查最大回撤风险"""
        warnings = []
        max_dd = info.get("最大回撤")

        if max_dd is not None:
            abs_dd = abs(max_dd)
            if abs_dd >= self.THRESHOLDS["max_drawdown_danger"]:
                warnings.append({
                    "类型": "回撤风险",
                    "等级": "🔴 高危",
                    "指标": f"最大回撤 {max_dd:.2f}%",
                    "描述": f"该基金历史最大回撤高达{max_dd:.2f}%，风险极高，"
                            f"远超{self.THRESHOLDS['max_drawdown_danger']}%的危险阈值。"
                            f"建议密切关注市场变化，必要时减仓控制风险。",
                })
            elif abs_dd >= self.THRESHOLDS["max_drawdown_warn"]:
                warnings.append({
                    "类型": "回撤风险",
                    "等级": "🟡 预警",
                    "指标": f"最大回撤 {max_dd:.2f}%",
                    "描述": f"该基金历史最大回撤为{max_dd:.2f}%，"
                            f"超过{self.THRESHOLDS['max_drawdown_warn']}%的预警线。"
                            f"属于中高风险基金，需注意市场下行风险。",
                })
        else:
            warnings.append({
                "类型": "回撤风险",
                "等级": "🔵 提示",
                "指标": "最大回撤未知",
                "描述": "未能获取该基金的最大回撤数据，建议在天天基金网查询详情。",
            })
        return warnings

    def _check_manager_risk(self, info: Dict) -> List[Dict]:
        """检查基金经理变更风险"""
        warnings = []
        managers = info.get("基金经理列表", [])

        if not managers and info.get("基金经理"):
            # 有基金经理名字但无详细数据
            pass
        elif not managers:
            return warnings

        # 检查是否有基金经理近期变更
        for mgr in managers:
            tenure_days = mgr.get("任职天数", 0)
            if 0 < tenure_days < self.THRESHOLDS["manager_tenure_warn_days"]:
                warnings.append({
                    "类型": "经理变更",
                    "等级": "🟡 预警",
                    "指标": f"新基金经理任职{tenure_days}天",
                    "描述": f"基金经理{mgr.get('基金经理','')}任职仅{tenure_days}天，"
                            f"不足{self.THRESHOLDS['manager_tenure_warn_days']}天。"
                            f"新经理的投资风格和业绩有待观察，建议保持关注。",
                })

        # 检查是否有多位基金经理（可能不稳定）
        if len(managers) >= 3:
            manager_names = "、".join([m.get("基金经理", "") for m in managers[:3]])
            warnings.append({
                "类型": "经理变更",
                "等级": "🟡 预警",
                "指标": f"近年更换{len(managers)}位经理",
                "描述": f"该基金近年频繁更换基金经理 ({manager_names})，"
                        f"可能影响投资策略的稳定性和持续性。",
            })

        # 查看基金经理历史回报
        for mgr in managers:
            ret = mgr.get("任职回报(%)", 0)
            if ret is not None and ret < -20:
                warnings.append({
                    "类型": "经理业绩",
                    "等级": "🔴 高危",
                    "指标": f"经理任职回报{ret:.2f}%",
                    "描述": f"基金经理{mgr.get('基金经理','')}任职期间回报{ret:.2f}%，"
                            f"表现不佳。",
                })

        return warnings

    def _check_size_risk(self, info: Dict) -> List[Dict]:
        """检查基金规模风险"""
        warnings = []
        size = info.get("基金规模(亿)", 0)

        if size == 0:
            return warnings

        if size < self.THRESHOLDS["fund_size_tiny"]:
            warnings.append({
                "类型": "规模风险",
                "等级": "🔴 高危",
                "指标": f"规模{size:.2f}亿",
                "描述": f"该基金规模仅{size:.2f}亿元，属于迷你基金。"
                        f"根据监管要求，连续60日规模低于5000万元可能触发清盘。"
                        f"建议考虑转换到规模更大的基金。",
            })
        elif size < 5:
            warnings.append({
                "类型": "规模风险",
                "等级": "🟡 预警",
                "指标": f"规模{size:.2f}亿",
                "描述": f"该基金规模{size:.2f}亿元，规模偏小。"
                        f"小规模基金运营成本占比高，且可能面临流动性问题。",
            })
        elif size > self.THRESHOLDS["fund_size_huge"]:
            warnings.append({
                "类型": "规模风险",
                "等级": "🟡 预警",
                "指标": f"规模{size:.2f}亿",
                "描述": f"该基金规模高达{size:.2f}亿元，属于巨型基金。"
                        f"大规模基金灵活性下降，调仓成本高，超额收益获取难度增加。",
            })

        return warnings

    def _check_industry_risk(self, info: Dict) -> List[Dict]:
        """检查行业集中度风险"""
        warnings = []
        industries = info.get("行业分布", [])

        if not industries:
            return warnings

        # 检查最大行业占比
        top_industry = industries[0] if industries else {}
        top_ratio = top_industry.get("比例(%)", 0)

        if top_ratio >= self.THRESHOLDS["industry_concentration_warn"]:
            warnings.append({
                "类型": "行业集中",
                "等级": "🔴 高危",
                "指标": f"行业集中度{top_ratio:.1f}%",
                "描述": f"基金在'{top_industry.get('行业','')}'行业的持仓占比高达"
                        f"{top_ratio:.1f}%，行业集中度极高。"
                        f"一旦该行业出现系统性风险，基金净值将受到重大影响。",
            })
        elif top_ratio >= 40:
            warnings.append({
                "类型": "行业集中",
                "等级": "🟡 预警",
                "指标": f"行业集中度{top_ratio:.1f}%",
                "描述": f"基金在'{top_industry.get('行业','')}'行业的持仓占比{top_ratio:.1f}%，"
                        f"行业集中度较高，需关注行业风险。",
            })

        return warnings

    def _check_performance_risk(self, info: Dict) -> List[Dict]:
        """检查业绩突变风险"""
        warnings = []
        returns = info.get("收益率", {})

        if not returns:
            return warnings

        # 1. 检查近1月收益率是否大幅为负
        recent_1m = returns.get("近1月", 0)
        if recent_1m < -10:
            warnings.append({
                "类型": "业绩风险",
                "等级": "🔴 高危",
                "指标": f"近1月下跌{recent_1m:.2f}%",
                "描述": f"该基金近1个月暴跌{recent_1m:.2f}%，远超市场平均跌幅。"
                        f"建议立即核查基金公告，了解是否有重大持仓暴雷。",
            })
        elif recent_1m < -5:
            warnings.append({
                "类型": "业绩风险",
                "等级": "🟡 预警",
                "指标": f"近1月下跌{recent_1m:.2f}%",
                "描述": f"该基金近1个月下跌{recent_1m:.2f}%，表现较弱。"
                        f"建议关注持仓标的和行业动态。",
            })

        # 2. 检查收益率衰减（近1月 vs 近3月/3 半月均比较）
        recent_3m = returns.get("近3月", 0)
        if recent_3m != 0 and recent_1m != 0:
            monthly_of_3m = recent_3m / 3
            if recent_1m < monthly_of_3m - 5:
                warnings.append({
                    "类型": "业绩衰减",
                    "等级": "🟡 预警",
                    "指标": f"近1月({recent_1m:.2f}%) < 近3月均({monthly_of_3m:.2f}%)",
                    "描述": f"该基金近期业绩呈现衰减趋势。近3月均涨幅{monthly_of_3m:.2f}%，"
                            f"但近1月仅{recent_1m:.2f}%，为负/远低于均值。"
                            f"基金可能正在经历困难期，建议关注。",
                })

        # 3. 检查近1年和近3年收益对比（如果近1年很差但近3年好，说明近期出了问题）
        recent_1y = returns.get("近1年", 0)
        recent_3y = returns.get("近3年", 0)
        if recent_1y and recent_3y:
            if recent_3y > 15 and recent_1y < -5:
                warnings.append({
                    "类型": "业绩反转",
                    "等级": "🔴 高危",
                    "指标": f"1年({recent_1y:.2f}%) vs 3年({recent_3y:.2f}%)",
                    "描述": f"该基金近3年累计收益{recent_3y:.2f}%，但近1年却下跌{recent_1y:.2f}%。"
                            f"近1年表现与长期趋势严重背离，可能有重大变化发生。"
                            f"建议核查是否更换基金经理或投资策略。",
                })

        return warnings

    def _check_consecutive_drop(self, info: Dict) -> List[Dict]:
        """检查连续下跌风险"""
        warnings = []
        nav_history = info.get("历史净值", [])

        if len(nav_history) < 10:
            return warnings

        # 分析最近一段时间净值走势
        recent_navs = nav_history[-30:]  # 最近30个交易日
        consecutive_downs = 0
        max_consecutive = 0
        drop_start = None

        for i in range(1, len(recent_navs)):
            if recent_navs[i]["单位净值"] < recent_navs[i-1]["单位净值"]:
                if consecutive_downs == 0:
                    drop_start = recent_navs[i-1]["日期"]
                consecutive_downs += 1
                max_consecutive = max(max_consecutive, consecutive_downs)
            else:
                consecutive_downs = 0
                drop_start = None

        if max_consecutive >= self.THRESHOLDS["consecutive_down_days"]:
            warnings.append({
                "类型": "连续下跌",
                "等级": "🔴 高危" if max_consecutive >= 7 else "🟡 预警",
                "指标": f"连跌{max_consecutive}天",
                "描述": f"该基金近期出现连续{max_consecutive}个交易日下跌。"
                        f"自{drop_start}起持续走弱，建议关注市场及持仓变化。"
                        f"{'如无特殊利好，建议考虑止损。' if max_consecutive >= 7 else ''}",
            })

        return warnings

    def summarize_risk_level(self, warnings: List[Dict]) -> Dict[str, Any]:
        """
        汇总风险等级

        Returns:
            {
                "整体风险": "低/中/高",
                "高危数": N,
                "预警数": N,
                "提示数": N,
                "关键警告": [高风险项]
            }
        """
        high = sum(1 for w in warnings if "高危" in w.get("等级", ""))
        mid = sum(1 for w in warnings if "预警" in w.get("等级", ""))
        low = sum(1 for w in warnings if "提示" in w.get("等级", ""))

        if high >= 2:
            level = "高风险 ⚠️"
        elif high >= 1 or mid >= 2:
            level = "中风险 ⚡"
        elif mid >= 1:
            level = "低风险 🔍"
        else:
            level = "健康 ✅"

        key_warnings = [w for w in warnings if "高危" in w.get("等级", "")]

        return {
            "整体风险": level,
            "高危数": high,
            "预警数": mid,
            "提示数": low,
            "风险总数": len(warnings),
            "关键警告": key_warnings,
        }
