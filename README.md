# 🐱 基金助手 · 巧克力 (Chocolat)

> 一只傲娇猫娘基金助手，陪你聊基金、管持仓、看趋势～
> 支持 **微信聊天** 和 **控制台对话** 两种使用方式。

---

## ✨ 它能做什么？

| 功能 | 说明 |
|------|------|
| 📋 **持仓管理** | 通过微信对话录入持仓，自动计算份额和盈亏 |
| 📊 **持仓分析** | 生成完整的持仓报告，含盈亏、趋势、风险评估 |
| 🔍 **基金查询** | 实时净值、历史走势、基金详情、收益率 |
| ⚠️ **风险监控** | 自动检测回撤、行业集中、业绩突变等风险 |
| 🎯 **基金推荐** | 基于多因子评分模型，从全市场筛选优质基金 |
| 💬 **智能对话** | 傲娇猫娘人设，专业基金话题 + 日常闲聊撒娇 |

---

## 🚀 快速开始（控制台模式）

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 设置 LLM API Key（推荐通义千问）
export LLM_API_KEY="sk-your-api-key"

# 3. 启动控制台对话
python start.py
```

然后你就可以在控制台和巧克力聊天了：

```
👤 你好呀
👤 帮我查查 016452 这只基金
👤 我的持仓情况
```

---

## 📱 微信模式（推荐）

通过微信和巧克力聊天，需要先部署到云端获取公网地址。

### 1️⃣ 部署到 Railway

[Railway](https://railway.app) 是一个云部署平台，免费额度足够运行本项目。

#### 步骤

**① Fork 项目**
- 打开项目 GitHub 地址，点击右上角 `Fork`
- Fork 到你自己的 GitHub 账号

**② 在 Railway 部署**
- 注册 Railway（用 GitHub 登录）：https://railway.app
- 点击 `New Project` → `Deploy from GitHub repo`
- 选择你 Fork 的项目
- Railway 会自动检测并部署

**③ 设置环境变量**

在 Railway 项目 Dashboard → `Variables` 中设置：

| 环境变量 | 必填 | 说明 | 获取方式 |
|----------|------|------|----------|
| `LLM_API_KEY` | ✅ | 通义千问 API Key | [开通地址](https://help.aliyun.com/zh/model-studio/getting-started/models) |
| `WX_APP_ID` | ✅ | 微信测试号 appID | 见下方步骤 |
| `WX_APP_SECRET` | ✅ | 微信测试号 appSecret | 见下方步骤 |
| `WX_TOKEN` | ❌ | 自定义 Token，默认 `fundagent123` | 自己定 |
| `DATABASE_URL` | ❌ | TiDB 数据库连接串（可选） | 见下方数据库说明 |

**④ 获取公网地址**
- 部署完成后，Railway 会自动分配一个域名
- 格式如：`https://fund-agent-production-xxxx.up.railway.app`
- 复制这个地址，下一步要用

### 2️⃣ 开通微信测试号

**① 打开测试号页面**
- 访问 https://mp.weixin.qq.com/debug/cgi-bin/sandbox
- 用微信扫码登录

**② 获取 appID 和 appSecret**
- 页面顶部会显示 **appID** 和 **appsecret**
- 复制这两个值，填入 Railway 的 `WX_APP_ID` 和 `WX_APP_SECRET` 环境变量

**③ 配置接口信息**
- 在测试号页面找到 **接口配置信息** → 点击「修改」
- URL 填：`https://你的Railway域名/wechat`
- Token 填：你在 Railway 设置的 `WX_TOKEN`（默认 `fundagent123`）
- 点击提交，显示「配置成功」即完成

### 3️⃣ 开始使用

- 用微信扫描测试号页面的二维码，关注测试号
- 发送消息，巧克力就会回复你～

> **提示**：Railway 免费版每月有 500 小时额度，一段时间没访问会休眠。唤醒后第一条消息可能稍慢（几秒）。

### 数据库（可选，推荐配置）

如果设置了 `DATABASE_URL`，持仓数据会持久化到 **TiDB Serverless** 数据库，重启不丢失。

**获取免费的 TiDB Serverless 数据库：**
1. 访问 https://tidbcloud.com 注册
2. 创建 Serverless Tier 集群（免费）
3. 在集群详情页点击 **Connect** → 选择 **General** 连接方式
4. 复制连接字符串，格式如：
   ```
   mysql://username:password@gateway01.ap-southeast-1.prod.aws.tidbcloud.com:4000/test
   ```
5. 在 Railway 设置 `DATABASE_URL` 环境变量

> 如果数据库连接失败，通常是 SSL 的问题。本项目已使用正确的 SSL 配置（`ssl.create_default_context`），连接 TiDB Serverless 无需额外设置。

---

## 💬 聊天示例

**录入持仓：**
```
👤 帮我录入持仓：南方纳斯达克100指数(QDII)A，244.22，支付宝，
   永赢先锋半导体智选混合A目前在支付宝占有金额为632.19
🤖 好啦，巧克力已经帮你记下了喵～
   南方纳斯达克100指数(QDII)A：投入244.22元，持有103.09份。
   永赢先锋半导体智选混合A：投入632.19元，持有227.88份。
   下次买了新基金也要告诉巧克力哦！
```

**查询持仓：**
```
👤 我的持仓情况
🤖 哼，主人终于想起来看自己的持仓了喵～
   …（展示持仓报告：投入、市值、盈亏、趋势分析等）…
   主人可要好好盯着它们喵～
```

**查询基金：**
```
👤 帮我查查 016452
🤖 好的喵～让巧克力看看这只基金的数据～
   南方纳斯达克100指数发起(QDII)A
   最新净值：2.3144
   近3月：+19.12%
   近1年：+27.10%
   近3年：+74.19%
```

**日常闲聊：**
```
👤 今天心情怎么样
🤖 *（猫耳朵抖了抖，尾巴翘得老高）*
   哼！主人终于想起巧克力了喵？
   我才没有一直等着你呢！…（小声）其实等了很久了…
```

---

## 🛠️ 技术架构

```
用户输入（微信 / 控制台）
        │
        ▼
┌─────────────────────────────┐
│   LangChain Agent           │
│   ─ LLM 驱动决策             │
│   ─ 意图识别 → 调用工具       │
│   ─ 多轮对话记忆              │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   基金工具集（14个工具）       │
│   查询 / 分析 / 推荐 / 持仓   │
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   数据获取（天天基金 API）     │
│   ─ 实时估值 + 详情 + 收益率   │
│   ─ 历史净值备用计算方案       │
└─────────────────────────────┘
           │
           ▼
┌─────────────────────────────┐
│   TiDB 数据库（可选）         │
│   ─ 持仓持久化               │
│   ─ 历史净值缓存              │
└─────────────────────────────┘
```

### 技术栈

| 技术 | 用途 |
|------|------|
| Python 3.9+ | 开发语言 |
| LangChain 0.2+ | LLM Agent 框架 |
| ChatOpenAI | LLM 接口（兼容通义千问等） |
| aiomysql | 异步 TiDB 数据库连接 |
| 天天基金 API | 基金数据来源 |
| NumPy | Sigmoid 评分标准化 |

### 支持的 LLM

| 提供商 | API Base |
|--------|----------|
| **通义千问（阿里云）** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| **DeepSeek** | `https://api.deepseek.com` |
| **零一万物** | `https://api.lingyiwanwu.com/v1` |
| **智谱** | `https://open.bigmodel.cn/api/paas/v4` |
| **OpenAI** | `https://api.openai.com/v1` |

---

## 📁 项目结构

```
fund_agent/
│
├── start.py                  # ⚡ 控制台对话启动
├── railway_start.py          # 🚄 Railway 云部署启动
├── wechat_test_account.py    # 📱 微信测试号服务
├── requirements.txt          # 📦 依赖
│
├── core/                     # 🤖 核心层
│   ├── langchain_agent.py    #   LangChain Agent（猫娘角色 + LLM）
│   └── tools.py              #   基金工具集（14个工具）
│
├── fund_data/                # 📡 数据获取
│   └── fetcher.py            #   天天基金 API 封装
│
├── analysis/                 # ⚙️ 分析引擎
│   ├── portfolio_analyzer.py #   持仓分析
│   ├── risk_analyzer.py      #   风险分析
│   └── recommender.py        #   基金推荐算法
│
├── report/                   # 📝 报告生成
│   └── generator.py          #   报告格式化
│
└── db/                       # 🗄️ 数据库
    └── database.py           #   TiDB 数据库管理器
```

---

## ⚠️ 免责声明

1. **不构成投资建议**：本工具提供的分析和推荐仅供参考，基金投资有风险，决策需谨慎。
2. **数据来源**：数据来源于天天基金公开 API，不保证完整性和实时性。
3. **使用限制**：请合理使用 API 接口，避免高频请求导致 IP 被封。

---

*⭐ 如果这个项目对你有帮助，欢迎 Star 支持！*
