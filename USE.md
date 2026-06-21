# 📋 基金助手 · 完整功能清单

> 傲娇猫娘「巧克力」，你的专属基金小助手喵～ 🐱

---

## 一、🧠 AI 对话引擎（core/）

| 模块 | 文件 | 功能 |
|------|------|------|
| **LangChain Agent** | `core/langchain_agent.py` | LLM 驱动的 AI 对话，傲娇猫娘「巧克力」角色，支持多轮对话记忆（最近 20 轮），基金话题专业模式 + 闲聊撒娇模式自动切换 |
| **14 个基金工具** | `core/tools.py` | 所有基金查询分析功能，通过 LangChain 工具注册，LLM 自动选择调用 |
| **兼容层** | `core/agent.py` | 旧版接口兼容 |

---

## 二、💬 交互方式

| 方式 | 文件 | 说明 |
|------|------|------|
| **控制台对话** | `start.py` | `python start.py` 本地运行直接聊天 |
| **微信测试号** | `wechat_test_account.py` | 部署到 Railway 后，用微信对话 |
| **Railway 云部署** | `railway_start.py` | Railway 自动检测运行，支持环境变量配置 |
| **主入口** | `main.py` | 兼容控制台/微信/报告三种模式 |

---

## 三、📡 数据获取 — 天天基金 API（fund_data/fetcher.py）

| 函数 | 功能 | 返回数据 |
|------|------|---------|
| `get_fund_basic_info` | 基金基础信息 | 代码、名称、类型 |
| `get_fund_detail` | 基金完整详情 | 净值走势、持仓股票、行业分布、最大回撤 |
| `get_fund_realtime_estimate` | 实时估值 | 估算净值、估算涨跌幅、昨日净值 |
| `get_fund_returns` | 阶段收益率 | 近1月/3月/6月/1年/3年/成立以来收益率 |
| `get_fund_grades` | 基金评级 | 各机构评级数据 |
| `get_fund_manager_info` | 基金经理信息 | 经理姓名、任职日期、任职回报 |
| `search_funds` | 基金搜索 | 按关键词搜索、类型筛选 |
| `get_recommended_funds` | 全市场基金列表 | 分页获取全部基金数据 |
| `get_fund_comprehensive_info` | 综合信息聚合 | 将上述数据合并为一个完整字典 |
| `compute_investment_metrics` | 持仓计算 | 投入成本→当前市值、盈亏、盈亏率 |

### 使用的 API 接口

```
实时估值:   GET https://fundgz.1234567.com.cn/js/{code}.js
基金详情:   GET https://fund.eastmoney.com/pingzhongdata/{code}.js
收益率:     GET https://fund.eastmoney.com/api/FundGuV40Api.ashx
基金经理:   GET https://fundmobapi.eastmoney.com/fund/FundManagerInfo
基金搜索:   GET https://fund.eastmoney.com/js/fundcode_search.js
基金列表:   GET https://fund.eastmoney.com/data/fundranking.html
详细信息:   GET https://fundf10.eastmoney.com/FundArchivesDatas.aspx
评级:       GET https://fund.eastmoney.com/api/FundGuV40Api.ashx?DataType=2
```

---

## 四、⚙️ 分析引擎（analysis/）

### 4.1 持仓分析 — `portfolio_analyzer.py`

| 功能 | 说明 |
|------|------|
| **整体概览** | 总投入、总市值、总盈亏、总盈亏率 |
| **逐项明细** | 每支基金的投入、市值、盈亏、盈亏率、当日涨跌幅、仓位占比 |
| **中长期评价** | 基于近3月/6月/1年/3年收益率的综合评分（0-100分） |
| **评级标准** | 优秀（≥80分）、良好（≥60分）、一般（≥40分）、较差（≥20分）、差（<20分） |
| **持仓质量** | 优质持仓 ✅ / 中等持仓 📊 / 需关注 ⚠️ / 建议止损 ❌ |
| **集中度分析** | 前1/前3持仓占比、集中度等级（全仓单支/高度集中/较为集中/适中/分散） |
| **操作建议** | 根据盈亏比例+中长期评价生成个性化建议（加仓/持有/止损/换仓） |
| **整体评价** | 收益评价、持仓质量、趋势判断、建议操作 |

### 4.2 风险分析 — `risk_analyzer.py`

| 风险类型 | 检测条件 | 等级 |
|----------|---------|------|
| **回撤风险** | 最大回撤 > 15%（预警）/ > 25%（高危） | 🔴高危 / 🟡预警 |
| **经理变更风险** | 基金经理任职 < 180 天 | 🟡预警 |
| **规模风险** | 规模 < 1 亿（迷你基金）/ > 300 亿（巨型基金） | 🔴高危 / 🟡预警 |
| **行业集中风险** | 第一重仓行业占比 > 60% | 🔴高危 / 🟡预警 |
| **连续下跌风险** | 连续 7 个交易日下跌（高危）/ 连续 5 个交易下跌（预警） | 🔴高危 / 🟡预警 |
| **业绩突变风险** | 近1月暴跌超 10% | 🔴高危 |
| **业绩反转风险** | 近3年好（> 30%）但近1年差（< -10%） | 🔴高危 |
| **风险等级汇总** | 汇总所有风险项，输出整体风险等级 + 高危/预警/提示数量 | — |

### 4.3 推荐算法 — `recommender.py`

| 维度 | 权重 | 评分因子 |
|------|------|---------|
| **收益因子** | 60% | 近1月 ~ 近3年加权收益，Sigmoid 标准化 |
| **风险因子** | 20% | 最大回撤评分 + 波动率评分（负向指标） |
| **稳定因子** | 10% | 经理任职稳定性 + 基金评级 |
| **规模因子** | 10% | 20亿~100亿规模最优，过大过小扣分 |
| **综合评分** | 100% | 加权求和，输出 0-100 分 + ★~★★★★★ 星级 |

---

## 五、📝 报告生成（report/generator.py）

| 报告类型 | 功能 |
|----------|------|
| `generate_full_report` | 完整持仓报告：概览→明细→风险→推荐→投资寄语 |
| `generate_quick_report` | 单支基金快报：净值→收益率→持仓分析→风险→推荐 |
| `generate_recommendation_table` | 推荐列表表格 |

---

## 六、🗄️ 数据库持久化（db/database.py）— TiDB/MySQL

### 6.1 表结构

#### `user_portfolios` — 用户持仓表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `BIGINT` | **PK** AUTO_INCREMENT | 自增主键 |
| `user_id` | `VARCHAR(50)` | **UNIQUE**(user_id, fund_code) | 用户标识 |
| `fund_code` | `VARCHAR(10)` | | 基金代码 |
| `fund_name` | `VARCHAR(100)` | | 基金名称 |
| `channel` | `VARCHAR(50)` | | 存储渠道（支付宝/天天基金/银行等） |
| `cost_amount` | `DECIMAL(20,4)` | NOT NULL | **用户投入成本（元）** |
| `current_value` | `DECIMAL(20,4)` | DEFAULT 0 | **当前市值（元）** |
| `profit_rate` | `DECIMAL(10,4)` | DEFAULT 0 | **盈亏率（%）** |
| `shares` | `DECIMAL(20,4)` | NOT NULL | **自动计算的持有份额** |
| `updated_at` | `TIMESTAMP` | ON UPDATE NOW | 更新时间 |

#### `fund_basic_info` — 基金基本信息表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `fund_code` | `VARCHAR(10)` | **PK** | 基金代码 |
| `fund_name` | `VARCHAR(100)` | NOT NULL | 基金名称 |
| `fund_type` | `VARCHAR(50)` | | 基金类型 |
| `fund_company` | `VARCHAR(100)` | | 基金公司 |
| `manager_name` | `VARCHAR(50)` | | 基金经理 |
| `establish_date` | `DATE` | | 成立日期 |
| `total_size` | `DECIMAL(20,4)` | | 基金规模（亿元） |

#### `fund_nav_history` — 基金历史净值表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `BIGINT` | **PK** AUTO_INCREMENT | 自增主键 |
| `fund_code` | `VARCHAR(10)` | **INDEX** | 基金代码 |
| `nav_date` | `DATE` | **UNIQUE**(fund_code, nav_date) | 净值日期 |
| `unit_nav` | `DECIMAL(10,4)` | NOT NULL | 单位净值 |
| `acc_nav` | `DECIMAL(10,4)` | | 累计净值 |

#### `fund_returns` — 基金收益率表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `BIGINT` | **PK** AUTO_INCREMENT | 自增主键 |
| `fund_code` | `VARCHAR(10)` | **UNIQUE** | 基金代码 |
| `return_1m` | `DECIMAL(10,4)` | | 近1月收益率（%） |
| `return_3m` | `DECIMAL(10,4)` | | 近3月收益率（%） |
| `return_6m` | `DECIMAL(10,4)` | | 近6月收益率（%） |
| `return_1y` | `DECIMAL(10,4)` | | 近1年收益率（%） |
| `return_3y` | `DECIMAL(10,4)` | | 近3年收益率（%） |
| `return_this_year` | `DECIMAL(10,4)` | | 今年以来收益率（%） |
| `return_since_inception` | `DECIMAL(10,4)` | | 成立以来收益率（%） |
| `max_drawdown` | `DECIMAL(10,4)` | | 最大回撤（%） |

#### `user_profiles` — 用户画像表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `user_id` | `VARCHAR(50)` | **PK** | 用户标识 |
| `risk_type` | `VARCHAR(20)` | DEFAULT '稳健型' | 风险类型：稳健型、激进型 |
| `occupation` | `VARCHAR(100)` | | 职业 |
| `income_range` | `VARCHAR(50)` | | 收入范围 |

### 6.2 操作方法

| 方法 | 功能 |
|------|------|
| `get_user_portfolios` | 查询用户持仓（返回投入/市值/盈亏率/份额/渠道） |
| `save_user_portfolio` | 保存或更新持仓（自动计算市值和盈亏率） |
| `delete_user_portfolio` | 删除持仓 |
| `get_user_profile` | 查询用户画像 |
| `save_user_profile` | 保存或更新用户画像 |
| `update_user_risk_type` | 更新用户风险类型 |
| `get_fund_history` | 从数据库查询历史净值 |
| `save_fund_history` | 保存历史净值到数据库 |
| `get_fund_detail` | 从数据库查询基金详情 |
| `save_fund_detail` | 保存基金详情到数据库 |

---

## 七、🤖 LLM 支持的提供商

| 提供商 | API Base | 推荐模型 |
|--------|----------|---------|
| **通义千问（阿里云）** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| **零一万物** | `https://api.lingyiwanwu.com/v1` | `yi-lightning` |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` |
| **智谱** | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o-mini` |

---

## 八、📋 14 个 LangChain 工具（core/tools.py）

| # | 工具 | 功能 | 输入参数 |
|---|------|------|---------|
| 1 | `query_fund_history` | 查询基金历史净值走势 | fund_code, period(day/week/month) |
| 2 | `query_fund_detail` | 查询基金详细信息 | fund_code |
| 3 | `query_fund_realtime` | 查询基金实时估值 | fund_code |
| 4 | `search_funds_by_keyword` | 按关键词搜索基金 | keyword |
| 5 | `get_portfolio_report` | 生成持仓分析报告 | user_id |
| 6 | `get_fund_recommendations` | 获取基金推荐 | count |
| 7 | `analyze_fund_risk` | 分析基金风险 | fund_code |
| 8 | `compare_funds` | 比较多个基金 | fund_codes(逗号分隔) |
| 9 | `calculate_investment` | 计算定投收益 | fund_code, amount, periods, frequency |
| 10 | `get_market_overview` | 获取市场概况 | category |
| 11 | `update_user_portfolio` | 添加/更新持仓 | user_id, fund_code, cost_amount, channel |
| 12 | `delete_user_portfolio` | 删除持仓 | user_id, fund_code |
| 13 | `get_user_profile_tool` | 查询用户画像 | user_id |
| 14 | `update_user_profile_tool` | 更新用户画像 | user_id, risk_type, occupation, income_range |

---

## 九、持仓管理流程（核心业务逻辑）

```
用户说："我在支付宝买了易方达优质精选，投入了2万块"
  ↓
① 查最新净值：get_fund_realtime_estimate("110011") → 净值 2.5000
② 自动算份额：shares = 20000 / 2.5000 = 8000 份
③ 存入数据库：cost_amount=20000, current_value=20000, profit_rate=0.00, channel="支付宝"
④ 查询时刷新：最新净值 × 8000 份 = 最新市值
⑤ 算盈亏率：(最新市值 - 20000) / 20000 × 100%
```

### 对话示例

```
👤 我在支付宝买了易方达优质精选混合，投入了20000元
🤖 *（竖起耳朵，尾巴晃了晃）* 收到喵！
已保存 易方达优质精选混合 的持仓信息（投入20000.00元）（存储在支付宝）。

👤 我的持仓怎么样了
🤖 *（尾巴得意地晃了晃）* 让巧克力帮你查查喵～
📋 持仓报告：
易方达优质精选混合（支付宝）| 投入20,000元 | 当前市值19,753元 | 盈亏率 -1.23%

👤 最近有什么好基金推荐吗
🤖 *（尾巴得意地翘起来）* 主人终于想起来问基金了喵！
🎯 精选基金推荐：
1. 易方达蓝筹精选混合 | 评分 92.5 ★★★★★
2. 招商中证白酒指数 | 评分 88.3 ★★★★☆
```

---

## 十、项目文件结构

```
fund_agent/
│
├── start.py                 # ⚡ 控制台对话启动脚本（本地测试）
├── railway_start.py         # 🚄 Railway 云部署启动脚本
├── wechat_test_account.py   # 📱 微信测试号 Bot
├── launch_wechat_test.sh    # 📱 微信测试号一键启动脚本
├── main.py                  # 🚀 主入口（控制台/微信/报告）
├── test_agent.py            # 🧪 测试脚本
├── run_wechat_bot.py        # 📱 微信 Bot 启动（备用）
├── wechat_launcher.py       # 📱 旧版微信启动器
├── config.yaml.example      # 📝 配置示例
├── requirements.txt         # 📦 Python 依赖
├── README.md                # 📖 说明文档
├── USE.md                   # 📋 功能清单（本文档）
│
├── core/                    # 🤖 核心层
│   ├── __init__.py
│   ├── langchain_agent.py   # LangChain Agent（猫娘角色 + LLM）
│   ├── agent.py             # 兼容层（封装 LangChain Agent）
│   └── tools.py             # 14 个基金工具
│
├── fund_data/               # 📡 数据获取层
│   ├── __init__.py
│   └── fetcher.py           # 天天基金 API 封装（10+ 函数）
│
├── analysis/                # ⚙️ 分析引擎层
│   ├── __init__.py
│   ├── portfolio_analyzer.py # 持仓分析引擎
│   ├── risk_analyzer.py     # 风险分析引擎（7 种风险检测）
│   └── recommender.py       # 多因子推荐引擎（4 维度评分）
│
├── report/                  # 📝 报告生成层
│   ├── __init__.py
│   └── generator.py         # 3 种报告格式
│
├── db/                      # 🗄️ 数据库层
│   ├── __init__.py
│   └── database.py          # TiDB 数据库管理器（5 张表、10+ 方法）
│
└── wechat/                  # 💬 微信交互层
    ├── __init__.py
    └── bot.py               # 旧版微信 Bot（已停用）
```
