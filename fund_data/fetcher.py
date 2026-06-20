"""
基金数据获取模块
使用天天基金开放API获取基金数据
"""

import requests
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any


# 请求头，模拟浏览器行为
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://fund.eastmoney.com/",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 请求超时
TIMEOUT = 15


def _request(url: str, params: dict = None, max_retries: int = 3) -> Optional[dict]:
    """发送HTTP请求，带重试机制"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(
                url, params=params, headers=HEADERS, timeout=TIMEOUT
            )
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp
            else:
                print(f"请求失败: HTTP {resp.status_code}, URL: {url}")
        except requests.RequestException as e:
            print(f"请求异常 (尝试 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(1, 3))
    return None


def get_fund_basic_info(fund_code: str) -> Optional[Dict[str, Any]]:
    """获取基金基本信息"""
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    resp = _request(url)
    if not resp:
        return None

    try:
        # 返回格式: jsonpgz({...});
        text = resp.text
        json_str = re.search(r'jsonpgz\((.+)\)', text)
        if json_str:
            data = json.loads(json_str.group(1))
            return {
                "基金代码": data.get("fundcode", fund_code),
                "基金名称": data.get("name", ""),
                "净值日期": data.get("jzrq", ""),
                "单位净值": float(data.get("dwjz", 0)),
                "估算净值": float(data.get("gsz", 0)),
                "估算涨跌幅": float(data.get("gszzl", 0)),
                "实时估算时间": data.get("gztime", ""),
            }
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"解析基金基本信息失败 [{fund_code}]: {e}")
    return None


def _get_fund_detail_from_f10api(fund_code: str) -> Optional[dict]:
    """
    从天天基金F10接口获取基金详细信息
    """
    url = "https://api.fund.eastmoney.com/f10/FundInfo"
    params = {"fundCode": fund_code, "callback": "jQuery"}
    resp = _request(url, params)
    if not resp:
        return None
    try:
        text = resp.text
        json_match = re.search(r'jQuery\d+\((\{.+})\)', text)
        if json_match:
            data = json.loads(json_match.group(1))
            if data.get("ErrCode") == 0:
                info = data.get("Data", {})
                return {
                    "基金类型": info.get("FTYPE", ""),
                    "成立日期": info.get("ESTDATE", ""),
                    "基金规模(亿)": float(info.get("ENDNAV", 0)) if info.get("ENDNAV") else 0,
                    "基金经理": info.get("MANAGER", ""),
                    "基金公司": info.get("COMPANY", ""),
                    "基金代码": info.get("FCODE", fund_code),
                }
    except Exception as e:
        print(f"获取基金F10详情失败 [{fund_code}]: {e}")
    return None


def get_fund_detail(fund_code: str) -> Optional[Dict[str, Any]]:
    """
    获取基金详细信息（名称、类型、规模、成立日期、基金经理等）
    综合多个接口获取数据
    """
    url = f"https://fund.eastmoney.com/pingzhongdata/{fund_code}.js"
    resp = _request(url)
    if not resp:
        return None

    try:
        text = resp.text

        # 提取基金名称和代码
        name_match = re.search(r'fS_name\s*=\s*"([^"]+)"', text)
        code_match = re.search(r'fS_code\s*=\s*"([^"]+)"', text)

        # 尝试从pingzhongdata提取其他字段（新版可能没有这些字段）
        type_match = re.search(r'fS_type\s*=\s*"([^"]+)"', text)
        date_match = re.search(r'fS_date\s*=\s*"([^"]+)"', text)
        scale_match = re.search(r'fS_scale\s*=\s*"?([\d.]+)"?', text)
        mgr_match = re.search(r'fS_manager\s*=\s*"([^"]+)"', text)
        company_match = re.search(r'fS_company\s*=\s*"([^"]+)"', text)

        # 解析历史净值数据 (Data_netWorthTrend)
        nav_data = _parse_nav_data(text)

        # 解析历史累计净值 (Data_ACWorthTrend)
        acnav_data = _parse_acnav_data(text)

        # 解析持仓数据
        positions = _parse_position_data(text)

        # 解析行业分布
        industry_dist = _parse_industry_distribution(text)

        # 解析最大回撤
        max_drawdown = _parse_max_drawdown(text)

        # 如果pingzhongdata缺少类型/规模/经理等信息，从F10 API补充
        extra_info = {}
        if not type_match or not scale_match or not mgr_match:
            f10_info = _get_fund_detail_from_f10api(fund_code)
            if f10_info:
                extra_info = f10_info

        result = {
            "基金代码": fund_code,
            "基金名称": name_match.group(1) if name_match else extra_info.get("基金代码", ""),
            "基金类型": (type_match.group(1) if type_match else "") or extra_info.get("基金类型", ""),
            "成立日期": (date_match.group(1) if date_match else "") or extra_info.get("成立日期", ""),
            "基金规模(亿)": float(scale_match.group(1) if scale_match else extra_info.get("基金规模(亿)", 0)),
            "基金经理": (mgr_match.group(1) if mgr_match else "") or extra_info.get("基金经理", ""),
            "基金公司": (company_match.group(1) if company_match else "") or extra_info.get("基金公司", ""),
            "历史净值": nav_data,
            "历史累计净值": acnav_data,
            "持仓数据": positions,
            "行业分布": industry_dist,
            "最大回撤": max_drawdown,
        }
        return result
    except Exception as e:
        print(f"解析基金详情失败 [{fund_code}]: {e}")
    return None


def _parse_nav_data(text: str) -> List[Dict]:
    """解析历史净值数据"""
    try:
        match = re.search(r'Data_netWorthTrend\s*=\s*(\[[\s\S]*?\])\s*;', text)
        if match:
            raw = match.group(1).replace("null", "0").replace("},]", "}]")
            data = json.loads(raw)
            result = []
            for item in data:
                # 支持对象数组和二维数组格式
                if isinstance(item, dict):
                    ts = item.get("x", 0)
                    if isinstance(ts, (int, float)):
                        ts = ts / 1000
                    else:
                        ts = 0
                    dt = datetime.fromtimestamp(ts) if ts > 0 else datetime.now()
                    result.append({
                        "日期": dt.strftime("%Y-%m-%d"),
                        "单位净值": item.get("y", 0),
                    })
                elif isinstance(item, list) and len(item) >= 2:
                    ts = item[0]
                    if isinstance(ts, (int, float)):
                        ts = ts / 1000
                        dt = datetime.fromtimestamp(ts)
                    else:
                        dt = datetime.now()
                    result.append({
                        "日期": dt.strftime("%Y-%m-%d"),
                        "单位净值": item[1],
                    })
            return result
    except Exception as e:
        print(f"解析历史净值失败: {e}")
    return []


def _parse_acnav_data(text: str) -> List[Dict]:
    """解析历史累计净值"""
    try:
        match = re.search(r'Data_ACWorthTrend\s*=\s*(\[[\s\S]*?\])\s*;', text)
        if match:
            raw = match.group(1)
            # 处理数据中的null
            raw = raw.replace("null", "0")
            raw = raw.replace("},]", "}]")  # 修复尾部逗号
            data = json.loads(raw)
            result = []
            for item in data:
                # 支持两种格式：对象数组 [{x:, y:}] 和 二维数组 [[ts, val]]
                if isinstance(item, dict):
                    ts = item.get("x", 0)
                    if isinstance(ts, (int, float)) and ts > 0:
                        ts = ts / 1000
                    else:
                        ts = 0
                    dt = datetime.fromtimestamp(ts) if ts > 0 else datetime.now()
                    result.append({
                        "日期": dt.strftime("%Y-%m-%d"),
                        "累计净值": float(item.get("y", 0)),
                        "单位净值": float(item.get("unitEquity", 0)) if isinstance(item.get("unitEquity"), (int, float)) else 0,
                    })
                elif isinstance(item, list) and len(item) >= 2:
                    # 二维数组格式 [timestamp, value]
                    ts = item[0]
                    if isinstance(ts, (int, float)):
                        ts = ts / 1000
                        dt = datetime.fromtimestamp(ts)
                    else:
                        dt = datetime.now()
                    result.append({
                        "日期": dt.strftime("%Y-%m-%d"),
                        "累计净值": float(item[1]),
                        "单位净值": 0,
                    })
            return result
    except Exception as e:
        print(f"解析历史累计净值失败: {e}")
    return []


def _parse_position_data(text: str) -> List[Dict]:
    """解析基金持仓数据（前十大重仓股）"""
    try:
        match = re.search(r'Data_stockFundStocks\s*=\s*(\[[\s\S]*?\])\s*;', text)
        if match:
            raw = match.group(1).replace("null", "0").replace("},]", "}]")
            data = json.loads(raw)
            result = []
            for item in data:
                if isinstance(item, dict):
                    result.append({
                        "股票代码": item.get("gpdm", ""),
                        "股票名称": item.get("gpmc", ""),
                        "占净值比例(%)": float(item.get("jzbl", 0) if item.get("jzbl") else 0),
                        "持仓市值(亿)": float(item.get("posMark", 0) if item.get("posMark") else 0),
                    })
            # 按持仓比例排序
            result.sort(key=lambda x: x["占净值比例(%)"], reverse=True)
            return result
    except Exception as e:
        print(f"解析持仓数据失败: {e}")
    return []


def _parse_industry_distribution(text: str) -> List[Dict]:
    """解析行业分布"""
    try:
        match = re.search(r'Data_industryDistribution\s*=\s*(\[[\s\S]*?\])\s*;', text)
        if match:
            raw = match.group(1).replace("null", "0").replace("},]", "}]")
            data = json.loads(raw)
            result = []
            for item in data:
                if isinstance(item, dict):
                    result.append({
                        "行业": item.get("hy", ""),
                        "比例(%)": float(item.get("value", 0) if item.get("value") else 0),
                    })
            return result
    except Exception as e:
        print(f"解析行业分布失败: {e}")
    return []


def _parse_max_drawdown(text: str) -> Optional[float]:
    """解析最大回撤"""
    try:
        # 尝试从基金详情中提取最大回撤
        match = re.search(r'最大回撤[：:]\s*([-\d.]+)%', text)
        if match:
            return float(match.group(1))
        # 备用匹配方式
        match = re.search(r'fS_maxdrawdown\s*=\s*"?([-\d.]+)"?', text)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None


def get_fund_returns(fund_code: str) -> Optional[Dict[str, float]]:
    """
    获取基金各阶段收益率
    接口: 天天基金API
    """
    url = "https://fund.eastmoney.com/api/FundEvaluateAPI.ashx"
    params = {
        "callback": "jQuery",
        "fundcode": fund_code,
    }
    resp = _request(url, params)
    if not resp:
        return None

    try:
        text = resp.text
        # 尝试从返回数据中提取收益率
        # 使用另一个更稳定的接口
        return _get_returns_from_eastmoney(fund_code)
    except Exception as e:
        print(f"获取收益率失败 [{fund_code}]: {e}")
    return None


def _get_returns_from_eastmoney(fund_code: str) -> Optional[Dict[str, float]]:
    """
    使用东方财富基金排行接口获取各阶段收益率
    """
    url = "https://fund.eastmoney.com/api/FundGuV40Api.ashx"
    params = {
        "callback": "jQuery",
        "DataType": "1",
        "Fcodes": fund_code,
        "Random": random.random(),
    }
    resp = _request(url, params)
    if not resp:
        return None

    try:
        text = resp.text
        # 提取JSON数据
        json_match = re.search(r'jQuery\d+\((\{.+})\)', text)
        if not json_match:
            return None
        data = json.loads(json_match.group(1))

        if data.get("ErrCode") != 0:
            return None

        datas = data.get("Data", [])
        if not datas:
            return None

        fund_data = datas[0]
        return {
            "近1月": float(fund_data.get("SYL_JZ", 0)),
            "近3月": float(fund_data.get("SYL_3Y", 0)),
            "近6月": float(fund_data.get("SYL_6Y", 0)),
            "近1年": float(fund_data.get("SYL_1N", 0)),
            "近2年": float(fund_data.get("SYL_2N", 0)),
            "近3年": float(fund_data.get("SYL_3N", 0)),
            "今年以来": float(fund_data.get("SYL_JN", 0)),
            "成立以来": float(fund_data.get("SYL_LN", 0)),
            "日涨跌幅": float(fund_data.get("SYL_DAY", 0)),
            "单位净值": float(fund_data.get("NAV", 0)),
            "累计净值": float(fund_data.get("ACCUM_NAV", 0)),
        }
    except Exception as e:
        print(f"从东方财富接口获取收益率失败 [{fund_code}]: {e}")
    return None


def get_fund_grades(fund_code: str) -> Optional[Dict]:
    """
    获取基金评级信息（晨星、招商等评级）
    """
    url = f"https://api.fund.eastmoney.com/f10/FundRatingNew"
    params = {"fundCode": fund_code, "callback": "jQuery"}
    resp = _request(url, params)
    if not resp:
        return None

    try:
        text = resp.text
        json_match = re.search(r'jQuery\d+\((\{.+})\)', text)
        if json_match:
            data = json.loads(json_match.group(1))
            if data.get("ErrCode") == 0:
                return data.get("Data", {})
    except Exception:
        pass
    return None


def get_fund_realtime_estimate(fund_code: str) -> Optional[Dict[str, Any]]:
    """
    获取基金实时估值
    """
    url = f"https://fundgz.1234567.com.cn/js/{fund_code}.js"
    resp = _request(url)
    if not resp:
        return None

    try:
        text = resp.text
        json_str = re.search(r'jsonpgz\((.+)\)', text)
        if json_str:
            data = json.loads(json_str.group(1))
            return {
                "基金代码": data.get("fundcode", ""),
                "基金名称": data.get("name", ""),
                "估算净值": float(data.get("gsz", 0)),
                "估算涨跌幅": float(data.get("gszzl", 0)),
                "估值时间": data.get("gztime", ""),
                "昨日净值": float(data.get("dwjz", 0)),
                "昨日日期": data.get("jzrq", ""),
            }
    except Exception as e:
        print(f"获取实时估值失败 [{fund_code}]: {e}")
    return None


def get_fund_manager_info(fund_code: str) -> Optional[List[Dict]]:
    """
    获取基金经理信息
    使用天天基金手机端API
    """
    url = f"https://fundmobapi.eastmoney.com/fund/FundManagerInfo"
    params = {
        "FUNDCODE": fund_code,
        "deviceid": "fund_agent",
        "version": "6.4.0",
        "product": "EFund",
    }
    resp = _request(url, params)
    if not resp:
        return None

    try:
        data = resp.json()
        if data.get("ErrCode") == 0:
            managers = data.get("Data", {}).get("Managers", [])
            result = []
            for mgr in managers:
                tenure_days = mgr.get("DAY", 0)
                result.append({
                    "基金经理": mgr.get("MANAGERNAME", ""),
                    "任职时间": mgr.get("STARTDATE", ""),
                    "任职天数": tenure_days,
                    "任职回报(%)": float(mgr.get("RETURN", 0)) if mgr.get("RETURN") else 0,
                    "从业回报(%)": float(mgr.get("MANAGERRETURN", 0)) if mgr.get("MANAGERRETURN") else 0,
                })
            return result
    except Exception as e:
        print(f"获取基金经理信息失败 [{fund_code}]: {e}")
    return None


def search_funds(keyword: str, page_size: int = 20) -> List[Dict]:
    """
    搜索基金
    """
    url = "https://fund.eastmoney.com/js/fundcode_search.js"
    resp = _request(url)
    if not resp:
        return []

    try:
        text = resp.text
        # 提取数组数据
        match = re.search(r'var r = (\[[\s\S]*?\]);', text)
        if not match:
            return []

        all_funds = json.loads(match.group(1))
        results = []
        for fund in all_funds:
            # fund格式: [代码, 拼音, 名称, 类型, 拼音缩写]
            code, _, name, ftype, _ = fund
            if keyword in code or keyword.lower() in name or keyword in ftype:
                results.append({
                    "基金代码": code,
                    "基金名称": name,
                    "基金类型": ftype,
                })
            if len(results) >= page_size:
                break
        return results
    except Exception as e:
        print(f"搜索基金失败: {e}")
    return []


def get_recommended_funds(page: int = 1, page_size: int = 50) -> List[Dict]:
    """
    获取全市场基金列表，用于推荐算法筛选
    """
    url = "https://fund.eastmoney.com/data/fundranking.html"
    params = {
        "callback": "jQuery",
        "page": page,
        "size": page_size,
    }
    # 使用更可靠的接口
    url2 = "https://fund.eastmoney.com/api/FundGuV40Api.ashx"
    params2 = {
        "callback": "jQuery",
        "DataType": "1",
        "SortField": "SYL_JZ",
        "SortDirection": "desc",
        "pageIndex": page,
        "pageSize": page_size,
        "ChannelID": "0",
        "Random": random.random(),
    }
    resp = _request(url2, params2)
    if not resp:
        return []

    try:
        text = resp.text
        json_match = re.search(r'jQuery\d+\((\{.+})\)', text)
        if not json_match:
            return []
        data = json.loads(json_match.group(1))
        if data.get("ErrCode") != 0:
            return []

        datas = data.get("Data", [])
        funds = []
        for item in datas:
            funds.append({
                "基金代码": item.get("FCODE", ""),
                "基金名称": item.get("SHORTNAME", ""),
                "基金类型": item.get("FTYPE", ""),
                "单位净值": float(item.get("NAV", 0)),
                "日涨跌幅": float(item.get("SYL_DAY", 0)),
                "近1月": float(item.get("SYL_JZ", 0)),
                "近3月": float(item.get("SYL_3Y", 0)),
                "近6月": float(item.get("SYL_6Y", 0)),
                "近1年": float(item.get("SYL_1N", 0)),
                "近2年": float(item.get("SYL_2N", 0)),
                "近3年": float(item.get("SYL_3N", 0)),
                "今年以来": float(item.get("SYL_JN", 0)),
                "成立以来": float(item.get("SYL_LN", 0)),
                "基金规模(亿)": float(item.get("ENDNAV", 0)) if item.get("ENDNAV") else 0,
                "基金评级": item.get("RATING", ""),
            })
        return funds
    except Exception as e:
        print(f"获取基金列表失败: {e}")
    return []


# ========== 便捷函数 ==========

def get_fund_comprehensive_info(fund_code: str) -> Dict[str, Any]:
    """
    获取基金综合信息（汇总所有数据）
    """
    result = {"基金代码": fund_code}

    # 基本信息/实时估值
    realtime = get_fund_realtime_estimate(fund_code)
    if realtime:
        result.update(realtime)

    # 详细数据
    detail = get_fund_detail(fund_code)
    if detail:
        for key, val in detail.items():
            if key not in result or not result.get(key):
                result[key] = val

    # 收益率数据
    returns = _get_returns_from_eastmoney(fund_code)
    if returns:
        result["收益率"] = returns

    # 基金经理
    managers = get_fund_manager_info(fund_code)
    if managers:
        result["基金经理列表"] = managers

    return result


def compute_investment_metrics(
    fund_code: str,
    total_cost: float,
    shares: float
) -> Dict[str, Any]:
    """
    计算持仓基金的各项投资指标

    Args:
        fund_code: 基金代码
        total_cost: 总投入成本（元）
        shares: 持有份额

    Returns:
        包含当前市值、盈亏、收益率等指标的字典
    """
    info = get_fund_realtime_estimate(fund_code)
    if not info:
        return {"错误": f"无法获取基金 {fund_code} 的数据"}

    nav = info.get("估算净值", 0) or info.get("昨日净值", 0)
    current_value = shares * nav
    profit = current_value - total_cost
    profit_pct = (profit / total_cost) * 100 if total_cost > 0 else 0

    return {
        "基金代码": fund_code,
        "基金名称": info.get("基金名称", ""),
        "总投入(元)": round(total_cost, 2),
        "持有份额": shares,
        "当前净值(元)": round(nav, 4),
        "当前市值(元)": round(current_value, 2),
        "盈亏(元)": round(profit, 2),
        "盈亏比例(%)": round(profit_pct, 2),
        "当日涨跌幅(%)": info.get("估算涨跌幅", 0),
        "估值时间": info.get("估值时间", ""),
    }
