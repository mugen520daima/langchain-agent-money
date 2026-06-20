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
            self._pool = await aiomysql.create_pool(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 4000)),
                user=self.config.get("user", "root"),
                password=self.config.get("password", ""),
                db=self.config.get("database", "fund_agent"),
                maxsize=int(self.config.get("pool_size", 5)),
                autocommit=True,
                ssl=True,  # TiDB Serverless / 云数据库需要 SSL
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
        
        -- 用户持仓表
        CREATE TABLE IF NOT EXISTS user_portfolios (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50) NOT NULL,
            fund_code VARCHAR(10) NOT NULL,
            fund_name VARCHAR(100),
            cost_amount DECIMAL(20, 4) NOT NULL,
            shares DECIMAL(20, 4) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
