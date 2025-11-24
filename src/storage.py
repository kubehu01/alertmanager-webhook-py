"""
存储后端抽象接口和实现（支持 Redis 和 SQLite）
"""
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """存储后端抽象接口"""
    
    @abstractmethod
    def exists(self, fingerprint: str) -> bool:
        """检查告警是否存在"""
        pass
    
    @abstractmethod
    def increment_count(self, fingerprint: str) -> int:
        """增加告警计数，返回新的计数值"""
        pass
    
    @abstractmethod
    def set_start_time(self, fingerprint: str, start_time: str):
        """设置开始时间（仅在首次触发时调用）"""
        pass
    
    @abstractmethod
    def set_alert_info(self, fingerprint: str, alertname: str = None, 
                       summary: str = None, instance: str = None, severity: str = None):
        """设置告警关键信息（仅在首次触发时调用）"""
        pass
    
    @abstractmethod
    def get_start_time(self, fingerprint: str) -> Optional[str]:
        """获取开始时间"""
        pass
    
    @abstractmethod
    def get_alert_info(self, fingerprint: str) -> Dict[str, Optional[str]]:
        """获取告警关键信息，返回字典：{alertname, summary, instance}"""
        pass
    
    @abstractmethod
    def get_alert_count(self, fingerprint: str) -> Optional[int]:
        """获取告警当前计数（不增加计数）"""
        pass
    
    @abstractmethod
    def delete(self, fingerprint: str, ends_at: str = None):
        """删除告警记录"""
        pass
    
    @abstractmethod
    def expire(self, fingerprint: str, ttl: int):
        """设置过期时间（Redis 使用，SQLite 忽略）"""
        pass
    
    @abstractmethod
    def delete_expired(self, cutoff_time: Optional[datetime] = None) -> int:
        """
        删除过期的历史记录（仅 SQLite 使用）
        
        Args:
            cutoff_time: 过期时间点，如果为 None 则删除所有已恢复的记录（保留天数为0时）
        """
        pass
    
    @abstractmethod
    def record_send_history(self, fingerprint: str, platform: str, alert_status: str, 
                           send_success: bool, error_message: str = None,
                           alert_count: int = None, alertname: str = None,
                           summary: str = None, instance: str = None, severity: str = None,
                           webhook_url: str = None):
        """
        记录消息发送历史
        
        Args:
            fingerprint: 告警指纹
            platform: 平台类型（qywechat/feishu/dingtalk）
            alert_status: 告警状态（firing/resolved）
            send_success: 发送是否成功
            error_message: 错误信息（如果发送失败）
            alert_count: 告警次数（仅 firing 状态）
            alertname: 告警名称
            summary: 告警摘要
            instance: 实例信息
            severity: 严重程度
            webhook_url: 完整的 webhook URL
        """
        pass
    
    @abstractmethod
    def close(self):
        """关闭连接"""
        pass


class RedisStorageBackend(StorageBackend):
    """Redis 存储后端实现"""
    
    REDIS_KEY_PREFIX = "alertmanager:alert:"
    ALERT_KEY_TTL = 7 * 24 * 60 * 60  # 7天
    
    def __init__(self, redis_server: str, redis_port: str, 
                 redis_password: str = "", redis_username: str = ""):
        if not REDIS_AVAILABLE:
            raise ImportError("redis 模块未安装，请运行: pip install redis")
        
        self.redis_server = redis_server
        self.redis_port = redis_port
        
        # 处理密码和用户名
        if redis_password:
            redis_password_str = str(redis_password).strip()
            self.redis_password = redis_password_str if redis_password_str else None
        else:
            self.redis_password = None
        
        if redis_username:
            redis_username_str = str(redis_username).strip()
            self.redis_username = redis_username_str if redis_username_str else None
        else:
            self.redis_username = None
        
        self._redis_pool = None
        self._redis_client = None
    
    def _get_redis_key(self, fingerprint: str) -> str:
        """生成带前缀的 Redis key"""
        return f"{self.REDIS_KEY_PREFIX}{fingerprint}"
    
    def _get_client(self) -> Optional[redis.Redis]:
        """获取Redis客户端（使用连接池）"""
        try:
            if self._redis_pool is None:
                connection_params = {
                    'host': self.redis_server,
                    'port': int(self.redis_port),
                    'decode_responses': True,
                    'socket_connect_timeout': 5,
                    'socket_timeout': 5,
                    'max_connections': 10,
                    'retry_on_timeout': True,
                }
                
                if self.redis_username:
                    connection_params['username'] = self.redis_username
                if self.redis_password:
                    connection_params['password'] = self.redis_password
                
                self._redis_pool = redis.ConnectionPool(**connection_params)
            
            if self._redis_client is None:
                self._redis_client = redis.Redis(connection_pool=self._redis_pool)
                self._redis_client.ping()
            else:
                try:
                    self._redis_client.ping()
                except (redis.ConnectionError, redis.TimeoutError):
                    self._redis_client = redis.Redis(connection_pool=self._redis_pool)
                    self._redis_client.ping()
            
            return self._redis_client
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            self._redis_client = None
            return None
    
    def exists(self, fingerprint: str) -> bool:
        """检查告警是否存在"""
        r = self._get_client()
        if not r:
            return False
        try:
            redis_key = self._get_redis_key(fingerprint)
            return r.exists(redis_key) > 0
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return False
    
    def increment_count(self, fingerprint: str) -> int:
        """增加告警计数，返回新的计数值"""
        r = self._get_client()
        if not r:
            return 1
        try:
            redis_key = self._get_redis_key(fingerprint)
            count = r.hincrby(redis_key, "count", 1)
            return int(count) if count else 1
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return 1
    
    def set_start_time(self, fingerprint: str, start_time: str):
        """设置开始时间（仅在首次触发时调用）"""
        r = self._get_client()
        if not r:
            return
        try:
            redis_key = self._get_redis_key(fingerprint)
            r.hset(redis_key, "startTime", start_time)
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
    
    def set_alert_info(self, fingerprint: str, alertname: str = None, 
                       summary: str = None, instance: str = None, severity: str = None):
        """设置告警关键信息（仅在首次触发时调用）"""
        r = self._get_client()
        if not r:
            return
        try:
            redis_key = self._get_redis_key(fingerprint)
            pipeline = r.pipeline()
            
            if alertname:
                pipeline.hset(redis_key, "alertname", alertname)
            if summary:
                pipeline.hset(redis_key, "summary", summary)
            if instance:
                pipeline.hset(redis_key, "instance", instance)
            if severity:
                pipeline.hset(redis_key, "severity", severity)
            
            pipeline.execute()
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
    
    def get_start_time(self, fingerprint: str) -> Optional[str]:
        """获取开始时间"""
        r = self._get_client()
        if not r:
            return None
        try:
            redis_key = self._get_redis_key(fingerprint)
            return r.hget(redis_key, "startTime")
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return None
    
    def get_alert_info(self, fingerprint: str) -> Dict[str, Optional[str]]:
        """获取告警关键信息"""
        r = self._get_client()
        if not r:
            return {"alertname": None, "summary": None, "instance": None, "alertname": None}
        try:
            redis_key = self._get_redis_key(fingerprint)
            pipeline = r.pipeline()
            pipeline.hget(redis_key, "summary")
            pipeline.hget(redis_key, "instance")
            pipeline.hget(redis_key, "alertname")
            results = pipeline.execute()
            
            return {
                "summary": results[0],
                "instance": results[1],
                "alertname": results[2],
            }
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return {"alertname": None, "summary": None, "instance": None}
    
    def get_alert_count(self, fingerprint: str) -> Optional[int]:
        """获取告警当前计数（不增加计数）"""
        r = self._get_client()
        if not r:
            return None
        try:
            redis_key = self._get_redis_key(fingerprint)
            count_str = r.hget(redis_key, "count")
            if count_str:
                return int(count_str)
            return None
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
            return None
    
    def delete(self, fingerprint: str, ends_at: str = None):
        """删除告警记录"""
        r = self._get_client()
        if not r:
            return
        try:
            redis_key = self._get_redis_key(fingerprint)
            r.delete(redis_key)
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
    
    def expire(self, fingerprint: str, ttl: int):
        """设置过期时间"""
        r = self._get_client()
        if not r:
            return
        try:
            redis_key = self._get_redis_key(fingerprint)
            r.expire(redis_key, ttl)
        except Exception as e:
            logger.error(f"Redis操作失败: {e}")
    
    def delete_expired(self, cutoff_time: Optional[datetime] = None) -> int:
        """删除过期的历史记录（Redis 不支持，返回 0）"""
        # Redis 使用 TTL 自动过期，不需要手动清理
        return 0
    
    def record_send_history(self, fingerprint: str, platform: str, alert_status: str, 
                           send_success: bool, error_message: str = None,
                           alert_count: int = None, alertname: str = None,
                           summary: str = None, instance: str = None, severity: str = None,
                           webhook_url: str = None):
        """记录消息发送历史（Redis 可选实现，主要用于 SQLite）"""
        # Redis 主要用于状态管理，发送历史记录主要在 SQLite 中实现
        # 如果需要，可以在这里实现 Redis 的发送历史记录
        pass
    
    def close(self):
        """关闭连接"""
        if self._redis_client:
            try:
                self._redis_client.close()
            except Exception as e:
                logger.warning(f"关闭Redis客户端时出错: {e}")
            finally:
                self._redis_client = None
        
        if self._redis_pool:
            try:
                self._redis_pool.disconnect()
            except Exception as e:
                logger.warning(f"关闭Redis连接池时出错: {e}")
            finally:
                self._redis_pool = None


class SQLiteStorageBackend(StorageBackend):
    """SQLite 存储后端实现（方案二：多记录设计）"""
    
    # 中国时区（CST，UTC+8）
    CST = timezone(timedelta(hours=8))
    
    def __init__(self, db_path: str):
        # 如果路径是相对路径，转换为绝对路径（基于当前工作目录）
        if not os.path.isabs(db_path):
            self.db_path = os.path.abspath(db_path)
        else:
            self.db_path = db_path
        self.conn = None
        self.lock = threading.Lock()  # 用于线程安全
        self._init_database()
    
    def _get_cst_timestamp(self) -> str:
        """获取当前 CST 时区的时间戳字符串（格式：YYYY-MM-DD HH:MM:SS）"""
        return datetime.now(self.CST).strftime('%Y-%m-%d %H:%M:%S')
    
    def _init_database(self):
        """初始化数据库和表结构"""
        # 确保数据库目录存在
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # 连接数据库
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # 使用 DELETE 模式（兼容 NFS 等网络文件系统）
        self.conn.execute("PRAGMA journal_mode = DELETE")
        self.conn.execute("PRAGMA synchronous = NORMAL")
        self.conn.execute("PRAGMA cache_size = -64000")  # 64MB
        self.conn.execute("PRAGMA foreign_keys = ON")
        
        # 创建表结构（多记录设计）
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fingerprint TEXT NOT NULL,
                status TEXT NOT NULL,
                count INTEGER NOT NULL DEFAULT 1,
                start_time TEXT NOT NULL,
                resolved_at TIMESTAMP,
                ends_at TEXT,
                alertname TEXT,
                summary TEXT,
                instance TEXT,
                severity TEXT,
                platform TEXT,
                send_status TEXT,
                send_error TEXT,
                last_sent_at TIMESTAMP,
                webhook_url TEXT,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                CHECK(status IN ('firing', 'resolved')),
                CHECK(count > 0),
                CHECK(platform IN ('qywechat', 'feishu', 'dingtalk') OR platform IS NULL),
                CHECK(send_status IN ('success', 'failed') OR send_status IS NULL)
            )
        """)
        
        # 先创建基础索引（不依赖新字段）
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_fingerprint ON alerts(fingerprint)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON alerts(status)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_resolved_at ON alerts(resolved_at)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_created_at ON alerts(created_at)
        """)
        
        # 为现有表添加新字段（如果表已存在但字段不存在）
        # 必须先添加字段，再创建索引，否则会报错
        try:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN platform TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        
        try:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN send_status TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        
        try:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN send_error TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        
        try:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN last_sent_at TIMESTAMP")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        
        try:
            self.conn.execute("ALTER TABLE alerts ADD COLUMN webhook_url TEXT")
        except sqlite3.OperationalError:
            pass  # 字段已存在
        
        # 创建新字段的索引（在字段添加之后）
        try:
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_platform ON alerts(platform)
            """)
        except sqlite3.OperationalError:
            pass  # 索引可能已存在或字段不存在
        
        try:
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_send_status ON alerts(send_status)
            """)
        except sqlite3.OperationalError:
            pass  # 索引可能已存在或字段不存在
        
        try:
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_last_sent_at ON alerts(last_sent_at)
            """)
        except sqlite3.OperationalError:
            pass  # 索引可能已存在或字段不存在
        
        self.conn.commit()
        logger.info(f"SQLite 数据库初始化完成: {self.db_path}")
    
    def exists(self, fingerprint: str) -> bool:
        """检查告警是否存在（检查是否有 firing 状态的记录）"""
        with self.lock:
            try:
                cursor = self.conn.execute(
                    "SELECT COUNT(*) FROM alerts WHERE fingerprint = ? AND status = 'firing'",
                    (fingerprint,)
                )
                return cursor.fetchone()[0] > 0
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                return False
    
    def increment_count(self, fingerprint: str) -> int:
        """增加告警计数（查找最新的 firing 记录，如果不存在则创建）"""
        with self.lock:
            try:
                # 查找最新的 firing 记录
                cursor = self.conn.execute(
                    "SELECT id, count FROM alerts WHERE fingerprint = ? AND status = 'firing' ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                
                if row:
                    # 更新现有记录
                    new_count = row['count'] + 1
                    current_time = self._get_cst_timestamp()
                    self.conn.execute(
                        "UPDATE alerts SET count = ?, updated_at = ? WHERE id = ?",
                        (new_count, current_time, row['id'])
                    )
                    self.conn.commit()
                    return new_count
                else:
                    # 创建新记录（首次触发）
                    current_time = self._get_cst_timestamp()
                    self.conn.execute(
                        """
                        INSERT INTO alerts (fingerprint, status, count, start_time, resolved_at, created_at, updated_at)
                        VALUES (?, 'firing', 1, ?, NULL, ?, ?)
                        """,
                        (fingerprint, current_time, current_time, current_time)
                    )
                    self.conn.commit()
                    return 1
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                self.conn.rollback()
                return 1
    
    def set_start_time(self, fingerprint: str, start_time: str):
        """设置开始时间（更新最新的 firing 记录）"""
        with self.lock:
            try:
                current_time = self._get_cst_timestamp()
                # 先找到最新的 firing 记录的 id
                cursor = self.conn.execute(
                    "SELECT id FROM alerts WHERE fingerprint = ? AND status = 'firing' ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                if row:
                    self.conn.execute(
                        "UPDATE alerts SET start_time = ?, updated_at = ? WHERE id = ?",
                        (start_time, current_time, row['id'])
                    )
                    self.conn.commit()
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                self.conn.rollback()
    
    def set_alert_info(self, fingerprint: str, alertname: str = None, 
                       summary: str = None, instance: str = None, severity: str = None):
        """设置告警关键信息（更新最新的 firing 记录）"""
        with self.lock:
            try:
                # 查找最新的 firing 记录
                cursor = self.conn.execute(
                    "SELECT id FROM alerts WHERE fingerprint = ? AND status = 'firing' ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                
                if row:
                    # 只更新非空字段
                    updates = []
                    params = []
                    
                    if alertname:
                        updates.append("alertname = ?")
                        params.append(alertname)
                    if summary:
                        updates.append("summary = ?")
                        params.append(summary)
                    if instance:
                        updates.append("instance = ?")
                        params.append(instance)
                    if severity:
                        updates.append("severity = ?")
                        params.append(severity)
                    
                    if updates:
                        current_time = self._get_cst_timestamp()
                        updates.append("updated_at = ?")
                        params.append(current_time)
                        params.append(row['id'])
                        
                        self.conn.execute(
                            f"UPDATE alerts SET {', '.join(updates)} WHERE id = ?",
                            params
                        )
                        self.conn.commit()
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                self.conn.rollback()
    
    def get_start_time(self, fingerprint: str) -> Optional[str]:
        """获取开始时间（从最新的记录获取）"""
        with self.lock:
            try:
                cursor = self.conn.execute(
                    "SELECT start_time FROM alerts WHERE fingerprint = ? ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                return row['start_time'] if row else None
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                return None
    
    def get_alert_info(self, fingerprint: str) -> Dict[str, Optional[str]]:
        """获取告警关键信息（从最新的记录获取）"""
        with self.lock:
            try:
                cursor = self.conn.execute(
                    "SELECT summary, instance, alertname FROM alerts WHERE fingerprint = ? ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        "summary": row['summary'],
                        "instance": row['instance'],
                        "alertname": row['alertname'],
                    }
                else:
                    return {"alertname": None, "summary": None, "instance": None}
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                return {"alertname": None, "summary": None, "instance": None}
    
    def get_alert_count(self, fingerprint: str) -> Optional[int]:
        """获取告警当前计数（不增加计数，从最新的 firing 记录获取）"""
        with self.lock:
            try:
                cursor = self.conn.execute(
                    "SELECT count FROM alerts WHERE fingerprint = ? AND status = 'firing' ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                return row['count'] if row else None
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                return None
    
    def delete(self, fingerprint: str, ends_at: str = None):
        """删除告警记录（将最新的 firing 记录标记为 resolved）"""
        with self.lock:
            try:
                # 查找最新的 firing 记录
                cursor = self.conn.execute(
                    "SELECT id FROM alerts WHERE fingerprint = ? AND status = 'firing' ORDER BY id DESC LIMIT 1",
                    (fingerprint,)
                )
                row = cursor.fetchone()
                
                if row:
                    # 使用本地时区（CST）的时间戳
                    current_time = self._get_cst_timestamp()
                    
                    # 更新为 resolved 状态
                    if ends_at:
                        self.conn.execute(
                            """
                            UPDATE alerts 
                            SET status = 'resolved', resolved_at = ?, 
                                ends_at = ?, updated_at = ? 
                            WHERE id = ?
                            """,
                            (current_time, ends_at, current_time, row['id'])
                        )
                    else:
                        self.conn.execute(
                            """
                            UPDATE alerts 
                            SET status = 'resolved', resolved_at = ?, updated_at = ? 
                            WHERE id = ?
                            """,
                            (current_time, current_time, row['id'])
                        )
                    self.conn.commit()
            except Exception as e:
                logger.error(f"SQLite操作失败: {e}")
                self.conn.rollback()
    
    def expire(self, fingerprint: str, ttl: int):
        """设置过期时间（SQLite 不支持，忽略）"""
        # SQLite 使用定时清理，不需要 TTL
        pass
    
    def record_send_history(self, fingerprint: str, platform: str, alert_status: str, 
                           send_success: bool, error_message: str = None,
                           alert_count: int = None, alertname: str = None,
                           summary: str = None, instance: str = None, severity: str = None,
                           webhook_url: str = None):
        """记录消息发送历史（更新 alerts 表中的发送信息）"""
        with self.lock:
            try:
                send_status_str = "success" if send_success else "failed"
                
                # 更新最新的告警记录的发送信息
                # 对于 firing 状态，更新最新的 firing 记录
                # 对于 resolved 状态，更新最新的记录（可能是 firing 或 resolved）
                if alert_status == "firing":
                    # 先找到最新的 firing 记录的 id
                    cursor = self.conn.execute("""
                        SELECT id FROM alerts 
                        WHERE fingerprint = ? AND status = 'firing'
                        ORDER BY id DESC LIMIT 1
                    """, (fingerprint,))
                    row = cursor.fetchone()
                    if row:
                        # 更新该记录
                        current_time = self._get_cst_timestamp()
                        self.conn.execute("""
                            UPDATE alerts 
                            SET platform = ?, send_status = ?, send_error = ?, webhook_url = ?, 
                                last_sent_at = ?, updated_at = ?
                            WHERE id = ?
                        """, (platform, send_status_str, error_message, webhook_url, current_time, current_time, row['id']))
                else:
                    # 对于 resolved 状态，更新最新的记录（可能是 firing 或 resolved）
                    cursor = self.conn.execute("""
                        SELECT id FROM alerts 
                        WHERE fingerprint = ?
                        ORDER BY id DESC LIMIT 1
                    """, (fingerprint,))
                    row = cursor.fetchone()
                    if row:
                        # 更新该记录
                        current_time = self._get_cst_timestamp()
                        self.conn.execute("""
                            UPDATE alerts 
                            SET platform = ?, send_status = ?, send_error = ?, webhook_url = ?,
                                last_sent_at = ?, updated_at = ?
                            WHERE id = ?
                        """, (platform, send_status_str, error_message, webhook_url, current_time, current_time, row['id']))
                
                self.conn.commit()
            except Exception as e:
                logger.error(f"记录发送历史失败: {e}")
                self.conn.rollback()
    
    def delete_expired(self, cutoff_time: Optional[datetime] = None, batch_size: int = 1000) -> int:
        """
        删除过期的历史记录（批量删除，避免长时间锁表）
        
        Args:
            cutoff_time: 过期时间点，如果为 None 则删除所有已恢复的记录（保留天数为0时）
            batch_size: 批量删除大小
        """
        with self.lock:
            try:
                total_deleted = 0
                
                while True:
                    # 如果 cutoff_time 为 None，删除所有已恢复的记录
                    if cutoff_time is None:
                        cursor = self.conn.execute(
                            """
                            DELETE FROM alerts 
                            WHERE id IN (
                                SELECT id FROM alerts 
                                WHERE status = 'resolved'
                                LIMIT ?
                            )
                            """,
                            (batch_size,)
                        )
                    else:
                        cutoff_str = cutoff_time.strftime('%Y-%m-%d %H:%M:%S')
                        cursor = self.conn.execute(
                            """
                            DELETE FROM alerts 
                            WHERE id IN (
                                SELECT id FROM alerts 
                                WHERE status = 'resolved' AND resolved_at < ?
                                LIMIT ?
                            )
                            """,
                            (cutoff_str, batch_size)
                        )
                    
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    self.conn.commit()
                    
                    # 如果删除数量小于批次大小，说明已删除完毕
                    if deleted < batch_size:
                        break
                    
                    # 短暂休息，避免长时间锁表
                    time.sleep(0.1)
                
                return total_deleted
            except Exception as e:
                logger.error(f"SQLite清理失败: {e}")
                self.conn.rollback()
                return 0
    
    def close(self):
        """关闭连接"""
        if self.conn:
            try:
                self.conn.close()
            except Exception as e:
                logger.warning(f"关闭SQLite连接时出错: {e}")
            finally:
                self.conn = None


