#!/usr/bin/env python3
"""
基金报告助手 - 测试脚本

测试各模块是否正常工作
"""

import sys
import os

# 添加项目根路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=" * 50)
print("🔍 基金报告助手 - 模块测试")
print("=" * 50)

# 测试1: 导入模块
print("\n1️⃣  测试模块导入...")
IMPORT_ERRORS = []

try:
    from fund_data.fetcher import (
        get_fund_basic_info, get_fund_detail,
        get_fund_realtime_estimate, compute_investment_metrics,
        get_fund_comprehensive_info, search_funds
    )
    print("   ✅ fund_data.fetcher - 导入成功")
except Exception as e:
    print(f"   ❌ fund_data.fetcher - 导入失败: {e}")
    IMPORT_ERRORS.append("fund_data.fetcher")

try:
    from analysis.risk_analyzer import RiskAnalyzer
    print("   ✅ analysis.risk_analyzer - 导入成功")
except Exception as e:
    print(f"   ❌ analysis.risk_analyzer - 导入失败: {e}")
    IMPORT_ERRORS.append("risk_analyzer")

try:
    from analysis.recommender import FundRecommender
    print("   ✅ analysis.recommender - 导入成功")
except Exception as e:
    print(f"   ❌ analysis.recommender - 导入失败: {e}")
    IMPORT_ERRORS.append("recommender")

try:
    from analysis.portfolio_analyzer import PortfolioAnalyzer
    print("   ✅ analysis.portfolio_analyzer - 导入成功")
except Exception as e:
    print(f"   ❌ analysis.portfolio_analyzer - 导入失败: {e}")
    IMPORT_ERRORS.append("portfolio_analyzer")

try:
    from report.generator import ReportGenerator
    print("   ✅ report.generator - 导入成功")
except Exception as e:
    print(f"   ❌ report.generator - 导入失败: {e}")
    IMPORT_ERRORS.append("report.generator")

try:
    from core.agent import FundAgent
    print("   ✅ core.agent - 导入成功")
except Exception as e:
    print(f"   ❌ core.agent - 导入失败: {e}")
    IMPORT_ERRORS.append("core.agent")

if IMPORT_ERRORS:
    print(f"\n⚠️  部分模块导入失败 ({len(IMPORT_ERRORS)}个)，后续测试可能受影响")
    print(f"   请确保依赖已安装: pip install -r requirements.txt")
else:
    print(f"\n✅ 所有模块导入成功！")

# 测试2: 基金数据获取（使用易方达中小盘混合 110011）
print("\n2️⃣  测试API数据获取（110011 易方达中小盘混合）...")

try:
    info = get_fund_basic_info("110011")
    if info:
        print(f"   ✅ 基本信息: {info.get('基金名称', '')} - 净值: {info.get('单位净值', 'N/A')}")
    else:
        print("   ⚠️  无法获取基本信息，网络可能不通")
except Exception as e:
    print(f"   ⚠️  获取基本信息失败: {e}")

try:
    realtime = get_fund_realtime_estimate("110011")
    if realtime:
        print(f"   ✅ 实时估值: {realtime.get('估算净值', 'N/A')} ({realtime.get('估算涨跌幅', 0):+.2f}%)")
    else:
        print("   ⚠️  无法获取实时估值")
except Exception as e:
    print(f"   ⚠️  获取实时估值失败: {e}")

# 测试3: 基金详情
print("\n3️⃣  测试基金详情获取...")
detail = None
try:
    detail = get_fund_comprehensive_info("110011")
    if detail:
        print(f"   ✅ 基金名称: {detail.get('基金名称', '')}")
        print(f"   ✅ 基金类型: {detail.get('基金类型', '')}")
        print(f"   ✅ 基金规模: {detail.get('基金规模(亿)', 0)}亿")
        print(f"   ✅ 基金经理: {detail.get('基金经理', '')}")

        returns = detail.get("收益率", {})
        if returns:
            print(f"   ✅ 收益率: 近1月 {returns.get('近1月', 0):+.2f}% | "
                  f"近3月 {returns.get('近3月', 0):+.2f}% | "
                  f"近1年 {returns.get('近1年', 0):+.2f}%")

        positions = detail.get("持仓数据", [])
        if positions:
            print(f"   ✅ 持仓数据: 前十大重仓股 {len(positions)} 支")
        else:
            print("   ℹ️  无持仓数据")

        managers = detail.get("基金经理列表", [])
        if managers:
            print(f"   ✅ 基金经理列表: {len(managers)} 位")
    else:
        print("   ❌ 获取基金详情失败")
except Exception as e:
    print(f"   ❌ 获取基金详情异常: {e}")

# 测试4: 风险分析
print("\n4️⃣  测试风险分析引擎...")
try:
    analyzer = RiskAnalyzer()
    if detail:
        warnings = analyzer.analyze(detail)
        summary = analyzer.summarize_risk_level(warnings)

        print(f"   ✅ 风险分析完成:")
        print(f"      整体风险: {summary.get('整体风险', 'N/A')}")
        print(f"      风险总数: {summary.get('风险总数', 0)} 项")
        for w in warnings[:3]:
            print(f"      {w.get('等级', '')} {w.get('类型', '')}: {w.get('指标', '')}")
    else:
        print("   ⚠️  无基金数据，跳过风险分析")
except Exception as e:
    print(f"   ❌ 风险分析失败: {e}")

# 测试5: 持仓分析
print("\n5️⃣  测试持仓分析引擎...")
try:
    analyzer_pf = PortfolioAnalyzer()

    # 模拟几个持仓
    mock_holdings = [
        {
            "基金代码": "110011",
            "基金名称": "易方达中小盘混合",
            "总投入(元)": 20000,
            "持有份额": 8000,
            "当前净值(元)": 2.5,
            "当前市值(元)": 20000,
            "盈亏(元)": 0,
            "盈亏比例(%)": 0,
            "当日涨跌幅(%)": 0.5,
            "收益率": detail.get("收益率", {}) if detail else {},
            "基金类型": detail.get("基金类型", "") if detail else "",
            "基金规模(亿)": detail.get("基金规模(亿)", 0) if detail else 0,
        }
    ]

    result = analyzer_pf.analyze_portfolio(mock_holdings)
    print(f"   ✅ 持仓分析完成:")
    print(f"      总投入: {result.get('总投入(元)', 0):,.2f}元")
    print(f"      整体评价: {result.get('整体评价', {}).get('收益评价', '')}")
    print(f"      集中度: {result.get('集中度分析', {}).get('集中度等级', '')}")
except Exception as e:
    print(f"   ❌ 持仓分析失败: {e}")

# 测试6: Agent 消息处理
print("\n6️⃣  测试Agent消息处理...")
try:
    test_config = {
        "portfolios": {
            "default_user": {
                "funds": [
                    {"code": "110011", "name": "易方达中小盘混合", "cost": 20000, "shares": 8000},
                ]
            }
        },
        "report": {"language": "zh", "show_recommendations": True, "recommend_count": 5},
        "algorithm": {"weights": {
            "recent_1m": 0.08, "recent_3m": 0.12, "recent_6m": 0.15,
            "recent_1y": 0.20, "recent_3y": 0.15,
            "max_drawdown_neg": 0.10, "volatility_neg": 0.05,
            "manager_stability": 0.05, "fund_rating": 0.05, "size_score": 0.05,
        }},
    }

    agent = FundAgent(test_config)

    # 测试帮助
    reply = agent.process_message("帮助")
    print(f"   ✅ 帮助指令: 成功回复 ({len(reply)} 字符)")

    # 测试查询
    reply = agent.process_message("110011")
    print(f"   ✅ 基金查询: 成功回复 ({len(reply)} 字符)")

    # 测试搜索
    reply = agent.process_message("搜索 白酒")
    print(f"   ✅ 基金搜索: 成功回复 ({len(reply)} 字符)")

    # 测试报告（可能因网络问题部分失败，但可以测试流程）
    reply = agent.process_message("报告")
    if "❌" not in reply[:5]:
        print(f"   ✅ 报告生成: 成功 ({len(reply)} 字符)")
    else:
        print(f"   ⚠️  报告生成: 可能因数据问题部分失败")
        print(f"      回复: {reply[:100]}...")

except Exception as e:
    print(f"   ❌ Agent测试失败: {e}")
    import traceback
    traceback.print_exc()

# 测试7: 推荐算法
print("\n7️⃣  测试推荐算法...")
try:
    recommender = FundRecommender()

    # 模拟一些基金数据
    mock_funds = [
        {"基金代码": "000001", "基金名称": "华夏成长混合", "基金类型": "混合型",
         "基金规模(亿)": 50, "近1月": 5.2, "近3月": 12.5, "近6月": 18.3,
         "近1年": 25.6, "近3年": 45.2, "日涨跌幅": 0.5, "最大回撤": -12.3,
         "基金经理列表": [{"任职天数": 800}], "基金评级": "★★★★",
         "收益率": {"近1月": 5.2, "近3月": 12.5, "近6月": 18.3, "近1年": 25.6, "近3年": 45.2, "日涨跌幅": 0.5}},
        {"基金代码": "110011", "基金名称": "易方达中小盘混合", "基金类型": "混合型",
         "基金规模(亿)": 150, "近1月": 3.8, "近3月": 8.2, "近6月": 15.1,
         "近1年": 22.3, "近3年": 52.8, "日涨跌幅": -0.3, "最大回撤": -18.5,
         "基金经理列表": [{"任职天数": 1200}], "基金评级": "★★★★★",
         "收益率": {"近1月": 3.8, "近3月": 8.2, "近6月": 15.1, "近1年": 22.3, "近3年": 52.8, "日涨跌幅": -0.3}},
    ]

    recs = recommender.recommend(mock_funds, top_n=5)
    if recs:
        summary = recommender.get_recommendation_summary(recs)
        print(f"   ✅ 推荐算法正常，生成了 {len(recs)} 条推荐")
        for r in summary[:3]:
            print(f"      {r.get('基金名称','')} - 评分: {r.get('综合评分', 0):.1f}")
    else:
        print("   ⚠️  推荐算法未能生成推荐（可能是数据不足）")

except Exception as e:
    print(f"   ❌ 推荐算法测试失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 50)
print("📋 测试完成！")
print("=" * 50)
print("\n启动方式:")
print("  python main.py              # 控制台模式")
print("  python main.py --wechat     # 微信交互模式")
print("  python main.py --send-report # 生成报告并发送微信")
