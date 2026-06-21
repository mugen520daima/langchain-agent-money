"""
TiDB 数据库管理器

用于持久化存储基金数据（历史净值、基金详情等）。
从 config.yaml 读取配置后即可启用。
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio
import json
import re


def parse_mysql_url(url: str) -> dict:
    """
    解析 MySQL 连接字符串 URL
    格式: mysql://user:password@host:port/database
    """
    result = {
        "host": "127.0.0.1",
        "port": 4000,
        "user": "root",
        "password": "",
        "database": "test",
    }
    if not url or not url.startswith("mysql://"):
        return result
    
    # 去掉 mysql:// 前缀
    rest = url[8:]
    
    # 解析 user:password@host:port/database
    # user:password@host:port/database
    user_part = rest.split("@")[0] if "@" in rest else rest
    host_part = rest.split("@")[1] if "@" in rest else ""
    
    if ":" in user_part:
        result["user"], result["password"] = user_part.split(":", 1)
    else:
        result["user"] = user_part
    
    if host_part:
        host_db = host_part.split("/", 1)
        host_port = host_db[0]
        if len(host_db) > 1:
            result["database"] = host_db[1]
        
        if ":" in host_port:
            result["host"], result["port"] = host_port.split(":", 1)
            result["port"] = int(result["port"])
        else:
            result["host"] = host_port
    
    return result


class DatabaseManager:
    """
    TiDB 数据库管理器
    
    用于存储和查询：
    - 基金历史净值（走势数据）
    - 基金详情（基本信息、收益率、持仓等）
    - 用户持仓配置
    - 用户画像（风险偏好、职业、收入）
    - 对话历史
    """
    
    def __init__(self, config: dict = None):
        self.config = config or {}
        self._enabled = self.config.get("enabled", False)
        self._pool = None
        self._connected = False
        
        # 如果配置里传了 url，从 url 中解析连接参数
        db_url = self.config.get("url", "")
        if db_url:
            parsed = parse_mysql_url(db_url)
            for key, value in parsed.items():
                if key not in self.config or not self.config.get(key):
                    self.config[key] = value
    
    async def connect(self):
        """连接数据库"""
        if not self._enabled:
            print("ℹ️ 数据库功能未启用（config.database.enabled = false）")
            return False
        
        try:
            import aiomysql
            import ssl
            
            # TiDB Serverless 需要自定义 SSL 上下文
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            self._pool = await aiomysql.create_pool(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 4000)),
                user=self.config.get("user", "root"),
                password=self.config.get("password", ""),
                db=self.config.get("database", "fund_agent"),
                maxsize=int(self.config.get("pool_size", 5)),
                autocommit=True,
                ssl=ctx,
            )
            self._connected = True
            print(f"✅ 数据库连接成功: {self.config.get('host')}:{self.config.get('port')}/{self.config.get('database')}")
            await self._init_tables()
            return True
        except ImportError:
            print("⚠️ aiomysql 未安装，数据库功能不可用。可执行: pip install aiomysql")
            return False
        except Exception as e:
            print(f"❌ 数据库连接失败: {e}")
            return False
    
    async def disconnect(self):
        """断开数据库连接"""
        if self._pool:
            self._pool.close()
            await self._pool.wait_closed()
            self._connected = False
    
    async def _init_tables(self):
        """初始化数据库表结构"""
        if not self._connected or not self._pool:
            return
        
        create_tables_sql = """
        -- 基金基本信息表
        CREATE TABLE IF NOT EXISTS fund_basic_info (
            fund_code VARCHAR(10) PRIMARY KEY,
            fund_name VARCHAR(100) NOT NULL,
            fund_type VARCHAR(50),
            fund_company VARCHAR(100),
            manager_name VARCHAR(50),
            establish_date DATE,
            total_size DECIMAL(20, 4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        
        -- 基金历史净值表
        CREATE TABLE IF NOT EXISTS fund_nav_history (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            fund_code VARCHAR(10) NOT NULL,
            nav_date DATE NOT NULL,
            unit_nav DECIMAL(10, 4) NOT NULL,
            acc_nav DECIMAL(10, 4),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE KEY uk_fund_date (fund_code, nav_date),
            INDEX idx_fund_code (fund_code),
            INDEX idx_nav_date (nav_date)
        );
        
        -- 基金收益率表
        CREATE TABLE IF NOT EXISTS fund_returns (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            fund_code VARCHAR(10) NOT NULL,
            return_1m DECIMAL(10, 4),
            return_3m DECIMAL(10, 4),
            return_6m DECIMAL(10, 4),
            return_1y DECIMAL(10, 4),
            return_3y DECIMAL(10, 4),
            return_this_year DECIMAL(10, 4),
            return_since_inception DECIMAL(10, 4),
            max_drawdown DECIMAL(10, 4),
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_fund (fund_code)
        );
        
        -- 用户画像表（风险偏好、职业、收入）
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id VARCHAR(50) PRIMARY KEY,
            risk_type VARCHAR(20) DEFAULT '稳健型' COMMENT '用户风险类型：稳健型、激进型',
            occupation VARCHAR(100) DEFAULT '' COMMENT '职业',
            income_range VARCHAR(50) DEFAULT '' COMMENT '收入范围',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        
        -- 用户持仓表（含实时市值、盈亏率和存储渠道）
        CREATE TABLE IF NOT EXISTS user_portfolios (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            fund_code VARCHAR(10) NOT NULL,
            fund_name VARCHAR(100),
            channel VARCHAR(50) DEFAULT '' COMMENT '存储渠道：支付宝、天天基金、银行等',
            cost_amount DECIMAL(20, 4) NOT NULL COMMENT '用户投入成本（元）',
            current_value DECIMAL(20, 4) DEFAULT 0 COMMENT '当前市值（元）',
            profit_rate DECIMAL(10, 4) DEFAULT 0 COMMENT '盈亏比例（%）',
            shares DECIMAL(20, 4) NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_user_fund (user_id, fund_code)
        );
        """
        
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    for statement in create_tables_sql.split(";"):
                        stmt = statement.strip()
                        if stmt:
                            await cursor.execute(stmt)
            print("✅ 数据库表初始化完成")
        except Exception as e:
            print(f"⚠️ 初始化数据库表失败: {e}")
    
    # ========== 用户画像管理 ==========
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict]:
        """获取用户画像"""
        if not self._connected:
            return None
        
        sql = """
        SELECT user_id, risk_type, occupation, income_range
        FROM user_profiles
        WHERE user_id = %s
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (user_id,))
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "user_id": row[0],
                            "risk_type": row[1] or "稳健型",
                            "occupation": row[2] or "",
                            "income_range": row[3] or "",
                        }
            return None
        except Exception as e:
            print(f"查询用户画像失败: {e}")
            return None
    
    async def save_user_profile(self, user_id: str, risk_type: str = "稳健型",
                                 occupation: str = "", income_range: str = ""):
        """保存或更新用户画像"""
        if not self._connected:
            return
        
        sql = """
        INSERT INTO user_profiles (user_id, risk_type, occupation, income_range)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            risk_type = VALUES(risk_type),
            occupation = VALUES(occupation),
            income_range = VALUES(income_range)
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (user_id, risk_type, occupation, income_range))
        except Exception as e:
            print(f"保存用户画像失败: {e}")
    
    async def update_user_risk_type(self, user_id: str, risk_type: str):
        """更新用户风险类型"""
        if not self._connected:
            return
        sql = """UPDATE user_profiles SET risk_type = %s WHERE user_id = %s"""
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (risk_type, user_id))
        except Exception as e:
            print(f"更新用户风险类型失败: {e}")
    
    # ========== 用户持仓管理（数据库持久化） ==========
    
    async def get_user_portfolios(self, user_id: str) -> Optional[List[Dict]]:
        """获取用户在数据库中的持仓（含当前市值、盈亏率和存储渠道）"""
        if not self._connected:
            return None
        
        sql = """
        SELECT fund_code, fund_name, channel, cost_amount, current_value, profit_rate, shares
        FROM user_portfolios
        WHERE user_id = %s
        ORDER BY updated_at ASC
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (user_id,))
                    rows = await cursor.fetchall()
                    if rows:
                        result = []
                        for row in rows:
                            result.append({
                                "code": row[0],
                                "name": row[1] or "",
                                "channel": row[2] or "",
                                "cost": float(row[3]),
                                "current_value": float(row[4]) if row[4] else float(row[3]),
                                "profit_rate": float(row[5]) if row[5] else 0.0,
                                "shares": float(row[6]),
                            })
                        return result
            return None
        except Exception as e:
            print(f"查询用户持仓失败: {e}")
            return None
    
    async def save_user_portfolio(self, user_id: str, fund_code: str,
                                   fund_name: str, cost_amount: float, 
                                   current_value: float, profit_rate: float, shares: float,
                                   channel: str = ""):
        """保存或更新用户持仓（含当前市值、盈亏率和存储渠道）"""
        if not self._connected:
            return False
        
        sql = """
        INSERT INTO user_portfolios (user_id, fund_code, fund_name, channel, cost_amount, current_value, profit_rate, shares)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            fund_name = VALUES(fund_name),
            channel = VALUES(channel),
            cost_amount = VALUES(cost_amount),
            current_value = VALUES(current_value),
            profit_rate = VALUES(profit_rate),
            shares = VALUES(shares)
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (user_id, fund_code, fund_name, channel, cost_amount, current_value, profit_rate, shares))
            return True
        except Exception as e:
            print(f"保存用户持仓失败: {e}")
            return False
    
    async def delete_user_portfolio(self, user_id: str, fund_code: str):
        """删除用户某支基金持仓"""
        if not self._connected:
            return False
        sql = """DELETE FROM user_portfolios WHERE user_id = %s AND fund_code = %s"""
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (user_id, fund_code))
            return True
        except Exception as e:
            print(f"删除用户持仓失败: {e}")
            return False
    
    # ========== 基金历史净值 ==========
    
    async def get_fund_history(self, fund_code: str, days: int = 365) -> Optional[List[Dict]]:
        """从数据库查询基金历史净值"""
        if not self._connected:
            return None
        
        sql = """
        SELECT nav_date, unit_nav, acc_nav
        FROM fund_nav_history
        WHERE fund_code = %s
        ORDER BY nav_date DESC
        LIMIT %s
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (fund_code, days))
                    rows = await cursor.fetchall()
                    if rows:
                        result = []
                        for row in rows:
                            result.append({
                                "日期": row[0].strftime("%Y-%m-%d") if hasattr(row[0], 'strftime') else str(row[0]),
                                "单位净值": float(row[1]),
                                "累计净值": float(row[2]) if row[2] else 0,
                            })
                        return result
            return None
        except Exception as e:
            print(f"查询历史净值失败: {e}")
            return None
    
    async def save_fund_history(self, fund_code: str, history_data: List[Dict]):
        """保存基金历史净值到数据库"""
        if not self._connected:
            return
        
        sql = """
        INSERT INTO fund_nav_history (fund_code, nav_date, unit_nav, acc_nav)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE unit_nav = VALUES(unit_nav), acc_nav = VALUES(acc_nav)
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    for item in history_data:
                        date_str = item.get("日期", "")
                        unit_nav = item.get("单位净值", 0)
                        acc_nav = item.get("累计净值", 0)
                        await cursor.execute(sql, (fund_code, date_str, unit_nav, acc_nav))
                    print(f"✅ 已保存 {len(history_data)} 条 {fund_code} 历史净值到数据库")
        except Exception as e:
            print(f"保存历史净值失败: {e}")
    
    # ========== 基金基本信息 ==========
    
    async def get_fund_detail(self, fund_code: str) -> Optional[Dict]:
        """从数据库查询基金详情"""
        if not self._connected:
            return None
        
        sql = """
        SELECT fund_code, fund_name, fund_type, fund_company, 
               manager_name, establish_date, total_size
        FROM fund_basic_info
        WHERE fund_code = %s
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (fund_code,))
                    row = await cursor.fetchone()
                    if row:
                        return {
                            "基金代码": row[0],
                            "基金名称": row[1],
                            "基金类型": row[2],
                            "基金公司": row[3],
                            "基金经理": row[4],
                            "成立日期": str(row[5]) if row[5] else "",
                            "规模(亿)": float(row[6]) if row[6] else 0,
                        }
            return None
        except Exception as e:
            print(f"查询基金详情失败: {e}")
            return None
    
    async def save_fund_detail(self, fund_code: str, detail: Dict):
        """保存基金详情到数据库"""
        if not self._connected:
            return
        
        sql = """
        INSERT INTO fund_basic_info (fund_code, fund_name, fund_type, fund_company, 
                                      manager_name, establish_date, total_size)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            fund_name = VALUES(fund_name),
            fund_type = VALUES(fund_type),
            fund_company = VALUES(fund_company),
            manager_name = VALUES(manager_name),
            establish_date = VALUES(establish_date),
            total_size = VALUES(total_size)
        """
        try:
            async with self._pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(sql, (
                        fund_code,
                        detail.get("基金名称", ""),
                        detail.get("基金类型", ""),
                        detail.get("基金公司", ""),
                        detail.get("基金经理", ""),
                        detail.get("成立日期", None),
                        detail.get("基金规模(亿)", 0),
                    ))
        except Exception as e:
            print(f"保存基金详情失败: {e}")


# 全局数据库管理器实例
_db_manager = None


def get_db_manager(config: dict = None) -> DatabaseManager:
    """获取全局数据库管理器"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager
