# 🤖 基金报告助手 (Fund Agent)

> 智能基金报告助手，通过控制台或微信与用户交互，提供基金持仓分析、风险评估、基金推荐等功能。

---

## 📋 目录

- [项目概述](#-项目概述)
- [系统架构](#-系统架构)
- [技术栈](#-技术栈)
- [Agent 工作流程](#-agent-工作流程)
- [功能特性](#-功能特性)
- [安装与配置](#-安装与配置)
- [使用指南](#-使用指南)
- [项目结构](#-项目结构)
- [API 文档](#-api-文档)
- [常见问题](#-常见问题)
- [免责声明](#-免责声明)

---

## 🎯 项目概述

**基金报告助手** 是一个基于 langchain 构建的智能基金分析系统，它能够：

| 能力 | 说明 |
|------|------|
| 🔍 **实时数据获取** | 通过天天基金开放 API 实时获取基金净值、估值、收益率等数据 |
| 📊 **持仓分析** | 分析持仓结构、计算盈亏、评价持仓质量、提供操作建议 |
| ⚠️ **风险监控** | 自动检测最大回撤风险、连续下跌、规模异动、业绩突变等 |
| 🎯 **基金推荐** | 基于多因子量化评分模型，从全市场筛选优质基金 |
| 💬 **多端交互** | 支持控制台和微信两种交互方式 |

本项目的核心是一套 **Agent 架构** —— 通过意图识别、数据获取、分析引擎、报告生成的完整链路，将复杂的基金分析工作自动化、智能化。

---

## 🏗 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     🎯 用户交互层                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  📱 微信 Bot   │  │  💻 控制台     │  │  📋 报告推送      │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼──────────────────┼───────────────────┼────────────┘
          │                  │                   │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                     🤖 核心 Agent 层                          │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  意图识别引擎  │───▶│  业务编排器    │───▶│  响应生成器    │  │
│  │  (意图解析)    │    │  (流程调度)    │    │  (报告组装)    │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
└─────────┼──────────────────┼───────────────────┼────────────┘
          │                  │                   │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    ⚙️ 分析引擎层                              │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
│  │  📊 持仓分析引擎 │  │  ⚠️ 风险分析引擎  │  │  🎯 推荐算法引擎 │ │
│  │  Portfolio     │  │  Risk          │  │  Fund          │ │
│  │  Analyzer      │  │  Analyzer      │  │  Recommender   │ │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘ │
└──────────┼──────────────────┼───────────────────┼───────────┘
           │                  │                   │
           ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│                    📡 数据获取层                               │
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │              Data Fetcher (数据获取器)                    │ │
│  │                                                          │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │ │
│  │  │ 实时估值   │ │ 基金详情   │ │ 收益率数据 │ │ 持仓数据   │   │ │
│  │  │ API      │ │ API      │ │ API      │ │ API      │   │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 分层说明

| 层级 | 模块 | 职责 |
|------|------|------|
| **交互层** | `wechat/bot.py`, `main.py`, `start.py` | 接收用户消息，发送响应，支持微信和控制台 |
| **核心层** | `core/agent.py` | 意图识别、业务流程编排、模块协调 |
| **分析层** | `analysis/*.py` | 持仓分析、风险评估、基金推荐算法 |
| **数据层** | `fund_data/fetcher.py` | 从天天基金 API 获取各类基金数据 |
| **报告层** | `report/generator.py` | 格式化输出持仓报告和推荐列表 |

---

## 💻 技术栈

### 核心依赖

| 技术 | 版本 | 用途 |
|------|------|------|
| **Python** | ≥ 3.9 | 开发语言 |
| **requests** | ≥ 2.28 | HTTP 请求，调用天天基金 API |
| **PyYAML** | ≥ 6.0 | 配置文件解析 |
| **NumPy** | ≥ 1.23 | 数值计算，评分模型的 Sigmoid 标准化 |

### 数据获取

项目通过解析天天基金（东方财富）的多个公开 API 获取数据：

```
# 实时估值接口
GET https://fundgz.1234567.com.cn/js/{fund_code}.js
# → {fundcode, name, dwjz, gsz, gszzl, gztime}

# 基金详情接口（含净值历史、持仓数据）
GET https://fund.eastmoney.com/pingzhongdata/{fund_code}.js
# → Data_netWorthTrend, Data_ACWorthTrend, Data_stockFundStocks

# 收益率接口
GET https://fund.eastmoney.com/api/FundGuV40Api.ashx?DataType=1&Fcodes={code}
# → SYL_JZ(近1月), SYL_3Y(近3月), SYL_1N(近1年), ...

# 基金经理接口
GET https://fundmobapi.eastmoney.com/fund/FundManagerInfo?FUNDCODE={code}
# → Managers[{MANAGERNAME, STARTDATE, RETURN, ...}]

# 基金搜索接口
GET https://fund.eastmoney.com/js/fundcode_search.js
# → [[代码, 拼音, 名称, 类型, 拼音缩写], ...]
```

### 数据持久化（TiDB）

项目可选使用 **TiDB Serverless**（兼容 MySQL 协议）持久化存储基金数据：

- **历史净值表** (`fund_nav_history`)：缓存基金净值走势数据，减少 API 调用
- **基金信息表** (`fund_basic_info`)：缓存基金详情和基本信息
- **收益率表** (`fund_returns`)：缓存阶段性收益率数据
- **用户持仓表** (`user_portfolios`)：存储用户持仓配置

数据库表结构详见下文 [数据库表结构](#-数据库表结构)。

### 评分模型

推荐算法基于 **多因子量化评分模型**，使用 NumPy 的 Sigmoid 函数进行标准化：

```
Score = Σ(W_i × S_i)

因子权重:
  ├── 收益因子 (60%): 近1月~近3年加权收益评分
  ├── 风险因子 (20%): 最大回撤 + 波动率评分 (负向)
  ├── 稳定因子 (10%): 经理稳定性 + 基金评级评分
  └── 规模因子 (10%): 适度规模加分(20亿~100亿最优)
```

### 可选依赖

| 技术 | 用途 |
|------|------|
| **itchat** | 微信个人号交互（扫码登录） |
| **rich** | 控制台美化输出 |
| **matplotlib** | 基金走势图可视化 |

---

## 🤖 Agent 工作流程

### 消息处理流程

```
用户输入
    │
    ▼
┌─────────────────────┐
│  1. 意图识别          │  ← 正则表达式匹配
│  _parse_intent()     │
│                      │
│  ├─ "报告"/"持仓"     │  → 报告意图
│  ├─ "000001"         │  → 查询意图
│  ├─ "搜索 白酒"       │  → 搜索意图
│  ├─ "推荐"            │  → 推荐意图
│  └─ "帮助"            │  → 帮助意图
└─────────┬───────────┘
          │
          ▼ (以报告意图为例)
┌─────────────────────┐
│  2. 获取持仓配置       │  ← 从 config.yaml 读取
│  portfolios[user]   │
└─────────┬───────────┘
          │
          ▼ (遍历持仓基金)
┌──────────────────────────────────────────────┐
│  3. 循环获取每支基金数据                        │
│                                              │
│  for fund in funds:                          │
│    ├─ compute_investment_metrics(code, cost)  │  → 计算市值/盈亏
│    ├─ get_fund_comprehensive_info(code)       │  → 获取综合数据
│    └─ risk_analyzer.analyze(info)             │  → 分析风险
└───────────────────┬──────────────────────────┘
                    │
                    ▼
┌─────────────────────┐
│  4. 组合分析          │
│  portfolio_analyzer │  → 持仓集中度、整体评价
│  .analyze_portfolio │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  5. 获取推荐          │
│  recommender        │  → 排除已持仓基金
│  .recommend()       │  → 多因子评分
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  6. 生成报告          │  ← ReportGenerator
│  generate_full_report│  → 格式化文本输出
└─────────┬───────────┘
          │
          ▼
      返回给用户
```

### 意图识别规则

| 用户输入 | 匹配模式 | 对应操作 |
|----------|---------|---------|
| `报告` / `持仓` / `我的基金` | 关键词匹配 | 生成完整持仓分析报告 |
| `000001` / `查询 000001` | 6位数字或"查询"+数字 | 查询单支基金详情 |
| `搜索 新能源` / `找 白酒` | "搜索/找/查找"+关键词 | 搜索相关基金列表 |
| `推荐` / `好基金` | 关键词匹配 | 获取精选基金推荐 |
| `帮助` / `怎么用` | 关键词匹配 | 显示帮助菜单 |

### 缓存策略

Agent 使用字典缓存已查询的基金数据，避免重复请求：

```python
self._fund_cache = {}  # {fund_code: fund_data}

def _get_fund_data(self, fund_code):
    if fund_code in self._fund_cache:
        return self._fund_cache[fund_code]  # 命中缓存
    data = get_fund_comprehensive_info(fund_code)
    self._fund_cache[fund_code] = data      # 写入缓存
    return data
```

---

## ✨ 功能特性

### 📊 持仓分析
- **投入产出计算**：总投入、当前市值、总盈亏、收益率
- **集中度分析**：单支/前3持仓占比、集中度等级评估
- **持仓质量评价**：优质持仓 ✅ / 中等持仓 📊 / 需关注 ⚠️ / 建议止损 ❌
- **操作建议**：基于盈亏比例和中长期评价的综合建议
- **持仓明细**：逐支基金展示盈亏、仓位、当日涨跌幅

### ⚠️ 风险监控

| 风险类型 | 检测方式 | 严重等级 |
|----------|---------|---------|
| 📉 **回撤风险** | 最大回撤超过 15%/25% 阈值 | 🔴高危/🟡预警 |
| 🔄 **经理变更** | 基金经理任职不足180天 | 🟡预警 |
| 📏 **规模风险** | 规模<1亿(迷你) 或 >300亿(巨型) | 🔴高危/🟡预警 |
| 🏭 **行业集中** | 单一行业占比超60% | 🔴高危/🟡预警 |
| 📉 **连续下跌** | 连续5/7个交易日下跌 | 🟡预警/🔴高危 |
| 📊 **业绩突变** | 近1月暴跌超10% | 🔴高危 |
| 🔄 **业绩反转** | 近3年好但近1年差 | 🔴高危 |

### 🎯 基金推荐
- **多因子评分**：收益60% + 风险20% + 稳定10% + 规模10%
- **Sigmoid 标准化**：使用 NumPy 非线性映射将收益率映射到 0-100 分
- **智能排除**：自动过滤用户已持有的基金
- **星级评定**：★★★★★ (≥90) 到 ★☆☆☆☆ (<40)
- **规模偏好**：20亿~100亿规模基金得分最高

---

## 📦 安装与配置

### 环境要求

- Python ≥ 3.9
- pip 包管理器
- 网络连接（访问天天基金 API）

### 安装步骤

```bash
# 1. 进入项目目录
cd fund_agent

# 2. 安装依赖
pip install -r requirements.txt

# 3. 生成配置文件
cp config.yaml.example config.yaml

# 4. 编辑你的持仓信息
#    打开 config.yaml，修改 portfolios 部分
vim config.yaml

# 5. 一键启动
python start.py
```

### 配置说明

编辑 `config.yaml`，主要修改 `portfolios`、`llm` 和 `database` 部分：

```yaml
# 你的持仓基金列表（必填）
portfolios:
  default_user:
    funds:
      - code: "000001"        # 基金代码
        name: "华夏成长混合"   # 基金名称
        cost: 10000           # 你的总投入（元）
        shares: 5000          # 你的持有份额

# LLM 配置（必填）
llm:
  api_key: "your-api-key"    # 通义千问 / 零一万物 API Key
  api_base: "https://dashscope.aliyuncs.com/compatible-mode/v1"
  model: "qwen-plus"         # 推荐 qwen-plus，性价比高
  temperature: 0.8           # 0.0-1.0，猫娘模式建议 0.7-0.9

# 数据库配置（可选，推荐开启）
database:
  enabled: true
  host: "gateway01.ap-southeast-1.prod.aws.tidbcloud.com"
  port: 4000
  user: "your-user.root"
  password: "your-password"
  database: "test"
```

---

## 🚀 使用指南

### 方式一：控制台交互（推荐）

```bash
python start.py
```

启动后界面演示：
```
╔══════════════════════════════════════════════╗
║     🤖  基 金 报 告 助 手                    ║
╠══════════════════════════════════════════════╣
║  支持: 持仓分析 · 风险评估 · 基金推荐       ║
╚══════════════════════════════════════════════╝

支持以下指令：
  📋 输入「报告」→ 生成持仓分析报告
  🔍 输入基金代码 → 查询单支基金详情
  🔎 输入「搜索 xxx」→ 搜索相关基金
  🎯 输入「推荐」→ 获取基金推荐
  ❓ 输入「帮助」→ 查看帮助
  🚪 输入「退出」→ 退出程序

👤 请输入:
```

### 方式二：微信交互（个人微信）

有两种方式可以在个人微信中与"巧克力"聊天：

---

#### 方式 A：微信测试号（推荐，稳定免费）

使用微信官方的**测试号**接口，不需要注册企业，**用你的个人微信关注测试号后，在微信里直接和巧克力对话**。

**📋 配置步骤：**

**第 1 步：开通微信测试号**
1. 打开浏览器访问：https://mp.weixin.qq.com/debug/cgi-bin/sandbox?t=sandbox/login
2. 用手机微信扫码登录
3. 页面会显示 **appID** 和 **appsecret**，复制保存

**第 2 步：启动服务并暴露到公网**
```bash
# 安装内网穿透工具 ngrok（用于让微信能访问到你本机的服务）
# Mac:
brew install ngrok

# 或从官网下载: https://ngrok.com/download
```

启动服务：
```bash
cd ~/fund_agent
bash launch_wechat_test.sh
```

会提示你输入 appID、appsecret 等，按提示输入。

**第 3 步：配置内网穿透**
新开一个终端窗口：
```bash
ngrok http 9000
```
会显示一个公网地址，如 `https://abc123.ngrok.io`

**第 4 步：回填到测试号后台**
1. 回到刚才的测试号页面：https://mp.weixin.qq.com/debug/cgi-bin/sandbox
2. 找到 **接口配置信息** → 点击「修改」
3. URL 填：`https://你的ngrok地址/wechat`（例如 `https://abc123.ngrok.io/wechat`）
4. Token 填你刚才输入的 Token（如 `fundagent123`）
5. 点击提交，显示"配置成功"就 OK 了

**完成！** 用微信扫描测试号页面的二维码，关注测试号，发送消息就能和巧克力聊天了~ 🐱

**注意事项：**
- ngrok 免费版每次启动 URL 会变，需要重新回填
- 如果想永久使用，可以用阿里云/腾讯云等部署（1 行代码都不用改）

---

#### 方式 B：itchat 个人号（已停用）

```bash
python wechat_launcher.py
```

> ⚠️ 注意：Web 微信协议已被腾讯逐步停用，新注册微信号无法使用此方式。

---

### 方式三：生成报告后推送微信

```bash
python start.py --report
```

### 指令大全

| 指令 | 示例 | 说明 |
|------|------|------|
| 基金代码 | `110011` | 查询单支基金的实时净值和阶段收益 |
| 查询基金 | `查询 000001` | 同上，更明确的查询指令 |
| 报告 | `报告` | 生成完整持仓分析报告 |
| 持仓 | `持仓` | 同上 |
| 搜索 | `搜索 白酒` | 搜索名称中包含关键词的基金 |
| 推荐 | `推荐` | 获取精选基金推荐列表 |
| 帮助 | `帮助` | 显示帮助菜单 |

---

## 📁 项目结构

```
fund_agent/
│
├── wechat_launcher.py       # 📱 itchat 微信聊天启动器（已停用）
├── wechat_test_account.py   # 📱 微信测试号 Bot（推荐，无需额外安装）
├── launch_wechat_test.sh    # 📱 微信测试号一键启动脚本
├── botchan/                 # 📱 BotChan 源码（微信测试号 Node.js 版，仅供参考）
├── main.py                 # 🚀 主入口，支持控制台/微信/推送三种模式
├── start.py                # ⚡ 一键启动脚本（推荐新手使用）
├── config.yaml             # ⚙️ 用户配置文件（需自行创建）
├── config.yaml.example     # 📝 配置示例文件
├── test_agent.py           # 🧪 模块功能测试脚本
├── requirements.txt        # 📦 Python 依赖列表
├── README.md               # 📖 本文档
│
├── fund_data/              # 📡 数据获取层
│   ├── __init__.py
│   └── fetcher.py          # 基金数据获取器（API调用+解析）
│
├── analysis/               # ⚙️ 分析引擎层
│   ├── __init__.py
│   ├── risk_analyzer.py    # ⚠️ 风险与异动分析引擎
│   ├── recommender.py      # 🎯 多因子推荐算法引擎
│   └── portfolio_analyzer.py # 📊 持仓综合分析引擎
│
├── core/                   # 🤖 核心层
│   ├── __init__.py
│   ├── agent.py            # 基金 Agent 兼容层（封装 LangChain Agent 或旧版规则引擎）
│   ├── langchain_agent.py  # 🆕 LangChain Agent（猫娘角色 + LLM 驱动）
│   └── tools.py            # 🆕 LangChain 工具集（10 个基金工具）
│
├── db/                     # 🗄️ 数据库层
│   ├── __init__.py
│   └── database.py         # 🆕 TiDB 数据库管理器（持久化存储基金数据）
│
├── report/                 # 📝 报告层
│   ├── __init__.py
│   └── generator.py        # 报告生成器（格式化输出）
│
└── wechat/                 # 💬 交互层
    ├── __init__.py
    └── bot.py              # 微信机器人（基于 itchat）
```

---

## 📖 API 文档

### FundAgent (core/agent.py)

```python
class FundAgent:
    def __init__(self, config: dict = None)
    def process_message(self, message: str, user_id: str = "default_user") -> str
    def update_portfolio(self, user_id: str, code: str, cost: float, shares: float, name: str = "") -> str
    def clear_cache(self)
```

### DataFetcher (fund_data/fetcher.py)

```python
get_fund_basic_info(fund_code: str) -> Dict            # 实时净值/估值
get_fund_comprehensive_info(fund_code: str) -> Dict   # 综合信息
get_fund_realtime_estimate(fund_code: str) -> Dict    # 实时估值
compute_investment_metrics(code, cost, shares) -> Dict  # 持仓计算
search_funds(keyword: str) -> List[Dict]               # 搜索基金
get_recommended_funds(page, size) -> List[Dict]        # 全市场基金列表
```

### RiskAnalyzer (analysis/risk_analyzer.py)

```python
class RiskAnalyzer:
    def analyze(fund_info: Dict) -> List[Dict]       # 全面风险分析
    def summarize_risk_level(warnings: List) -> Dict  # 汇总风险等级
```

### FundRecommender (analysis/recommender.py)

```python
class FundRecommender:
    def score_fund(fund_data: Dict) -> Dict            # 单基金评分
    def recommend(fund_list, top_n, exclude_codes) -> List  # 推荐
    def get_recommendation_summary(recs) -> List       # 生成摘要
```

### ReportGenerator (report/generator.py)

```python
class ReportGenerator:
    def generate_full_report(portfolio, risks, recs, user) -> str    # 完整报告
    def generate_quick_report(fund, holdings, risk, recs) -> str     # 快速查询
    def generate_recommendation_table(recs) -> str                   # 推荐表格
```

---

## ❓ 常见问题

### Q: 启动后提示"未找到配置文件"？
```bash
cp config.yaml.example config.yaml
# 然后编辑 config.yaml 填写你的持仓信息
```

### Q: 微信模式无法登录？
微信模式依赖 itchat 库使用 Web 微信协议。2023年后部分账号可能无法登录 Web 微信。建议使用控制台模式。

### Q: 为什么有些基金数据获取不到？
天天基金 API 在非交易时间可能返回空数据。建议在**交易日 9:30-15:00** 之间使用。

### Q: 如何添加多个用户的持仓？
```yaml
portfolios:
  张三:
    funds:
      - code: "000001"
        name: "华夏成长混合"
        cost: 10000
        shares: 5000
  李四:
    funds:
      - code: "110011"
        name: "易方达优质精选混合(QDII)"
        cost: 20000
        shares: 8000
```

---

## 🗄️ 数据库表结构

项目使用 **TiDB Serverless**（兼容 MySQL 5.7/8.0 协议）作为数据持久化层。首次连接时自动创建以下 4 张表：

### 1️⃣ `fund_basic_info` — 基金基本信息表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `fund_code` | `VARCHAR(10)` | **PK** | 基金代码（6位数字） |
| `fund_name` | `VARCHAR(100)` | NOT NULL | 基金名称 |
| `fund_type` | `VARCHAR(50)` | | 基金类型（股票型/混合型/指数型/债券型等） |
| `fund_company` | `VARCHAR(100)` | | 基金公司 |
| `manager_name` | `VARCHAR(50)` | | 基金经理姓名 |
| `establish_date` | `DATE` | | 成立日期 |
| `total_size` | `DECIMAL(20,4)` | | 基金规模（亿元） |
| `created_at` | `TIMESTAMP` | DEFAULT NOW | 创建时间 |
| `updated_at` | `TIMESTAMP` | ON UPDATE NOW | 更新时间 |

### 2️⃣ `fund_nav_history` — 基金历史净值表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `BIGINT` | **PK** AUTO_INCREMENT | 自增主键 |
| `fund_code` | `VARCHAR(10)` | **INDEX** | 基金代码 |
| `nav_date` | `DATE` | **UNIQUE**(fund_code, nav_date) | 净值日期 |
| `unit_nav` | `DECIMAL(10,4)` | NOT NULL | 单位净值 |
| `acc_nav` | `DECIMAL(10,4)` | | 累计净值 |
| `created_at` | `TIMESTAMP` | DEFAULT NOW | 创建时间 |

**索引**：
- `uk_fund_date` — UNIQUE(`fund_code`, `nav_date`)：防止同一天重复数据
- `idx_fund_code` — INDEX(`fund_code`)：按基金代码快速查询
- `idx_nav_date` — INDEX(`nav_date`)：按日期范围查询

### 3️⃣ `fund_returns` — 基金收益率表

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
| `updated_at` | `TIMESTAMP` | ON UPDATE NOW | 更新时间 |

### 4️⃣ `user_portfolios` — 用户持仓表

| 列名 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `BIGINT` | **PK** AUTO_INCREMENT | 自增主键 |
| `user_id` | `VARCHAR(50)` | **UNIQUE**(user_id, fund_code) | 用户标识 |
| `fund_code` | `VARCHAR(10)` | | 基金代码 |
| `fund_name` | `VARCHAR(100)` | | 基金名称 |
| `cost_amount` | `DECIMAL(20,4)` | NOT NULL | 投入总成本（元） |
| `shares` | `DECIMAL(20,4)` | NOT NULL | 持有份额 |
| `created_at` | `TIMESTAMP` | DEFAULT NOW | 创建时间 |
| `updated_at` | `TIMESTAMP` | ON UPDATE NOW | 更新时间 |

### ER 关系图

```
fund_basic_info          fund_nav_history          fund_returns
      │                       │                        │
      │ 1                      │ N                      │ 1
      │◄──────────────────────►│                        │
      │  fund_code             │  fund_code             │ fund_code
      │                       │                        │
      │ 1                      │                        │
      │◄─────────────────────────────────────────────────│
      │  fund_code                                        fund_code
```

---

## 🤖 LangChain Agent 架构（新版）

项目使用 **LangChain Agent** 驱动 AI 对话式交互。整体架构如下：

```
用户输入（控制台/微信）
        │
        ▼
┌─────────────────────────────┐
│   core/agent.py (兼容层)     │
│                              │
│   ├─ 尝试 → core/langchain_agent.py (LangChain Agent)
│   │          │
│   │          ├─ LLM (通义千问 qwen-plus / 零一万物 yi-lightning 等)
│   │          ├─ System Prompt（傲娇猫娘"巧克力"角色）
│   │          ├─ 10 个工具 (core/tools.py)
│   │          │   ├─ query_fund_history     → 历史净值走势
│   │          │   ├─ query_fund_detail      → 基金详细信息
│   │          │   ├─ query_fund_realtime    → 实时估值
│   │          │   ├─ search_funds_by_keyword → 搜索基金
│   │          │   ├─ get_portfolio_report   → 持仓分析报告
│   │          │   ├─ get_fund_recommendations → 基金推荐
│   │          │   ├─ analyze_fund_risk      → 风险评估
│   │          │   ├─ compare_funds          → 多支基金对比
│   │          │   ├─ calculate_investment   → 定投计算
│   │          │   └─ get_market_overview    → 市场概况
│   │          │
│   │          └─ 多轮对话记忆 (对话历史保留最近20轮)
│   │
│   └─ 失败回退 → 旧版规则引擎（意图匹配 + 硬编码回复）
│
└─────────────────────────────┘
```

### 支持的 LLM 提供商

| 提供商 | API Base | 推荐模型 |
|--------|----------|---------|
| **通义千问（阿里云）** | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`, `qwen-max` |
| **零一万物** | `https://api.lingyiwanwu.com/v1` | `yi-lightning`, `yi-large` |
| **DeepSeek** | `https://api.deepseek.com` | `deepseek-chat` |
| **智谱** | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-plus` |
| **OpenAI** | `https://api.openai.com/v1` | `gpt-4o`, `gpt-4o-mini` |

---

## ⚠️ 免责声明

1. **投资风险提示**：本工具提供的分析和推荐仅供参考，**不构成任何投资建议**。基金投资有风险，决策需谨慎。
2. **数据来源**：数据来源于天天基金（东方财富）公开 API，不保证数据的完整性和实时性。
3. **使用限制**：请合理使用 API 接口，避免高频请求导致 IP 被封。
4. **法律责任**：因使用本工具产生的任何投资盈亏，开发者不承担法律责任。

---

*⭐ 如果这个项目对你有帮助，欢迎 Star 支持！*
