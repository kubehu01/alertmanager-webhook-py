"""
历史记录清理调度器（自己实现，后台线程）
"""
import threading
import time
import logging
from datetime import datetime, timedelta

try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    PYTZ_AVAILABLE = False

logger = logging.getLogger(__name__)


class CleanupScheduler:
    """清理调度器：每天指定时间执行清理任务"""
    
    def __init__(self, storage_backend, retention_days: int, cleanup_time: str, timezone_str: str):
        """
        初始化清理调度器
        
        Args:
            storage_backend: 存储后端实例（需要实现 delete_expired 方法）
            retention_days: 保留天数
            cleanup_time: 清理时间（格式：HH:MM，如 "05:00"）
            timezone_str: 时区字符串（如 "Asia/Shanghai"）
        """
        self.storage = storage_backend
        self.retention_days = retention_days
        self.cleanup_time = cleanup_time
        self.running = True
        
        # 设置时区
        if PYTZ_AVAILABLE:
            try:
                self.timezone = pytz.timezone(timezone_str)
            except Exception as e:
                logger.warning(f"时区设置失败 {timezone_str}，使用系统时区: {e}")
                self.timezone = pytz.UTC
        else:
            logger.warning("pytz 未安装，使用系统时区。建议安装: pip install pytz")
            self.timezone = None
    
    def _get_now(self) -> datetime:
        """获取当前时间（带时区）"""
        if self.timezone:
            return datetime.now(self.timezone)
        else:
            return datetime.now()
    
    def calculate_next_run_time(self) -> datetime:
        """计算下次执行时间"""
        now = self._get_now()
        hour, minute = map(int, self.cleanup_time.split(':'))
        
        # 今天的执行时间
        if self.timezone:
            today_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        else:
            today_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # 如果今天的时间已过，则明天执行
        if today_run <= now:
            next_run = today_run + timedelta(days=1)
        else:
            next_run = today_run
        
        return next_run
    
    def cleanup_expired_records(self):
        """清理过期记录"""
        try:
            # 如果保留天数为0，表示不保留任何历史记录（删除所有已恢复的记录）
            if self.retention_days == 0:
                logger.info("保留天数为0，删除所有已恢复的历史记录")
                deleted_count = self.storage.delete_expired(None)
            else:
                # 计算过期时间点
                now = self._get_now()
                cutoff_time = now - timedelta(days=self.retention_days)
                
                logger.info(f"开始清理历史记录: 删除 {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} 之前的记录")
                
                # 执行清理
                deleted_count = self.storage.delete_expired(cutoff_time)
            
            logger.info(f"历史记录清理完成: 删除了 {deleted_count} 条过期记录")
            
            return deleted_count
        except Exception as e:
            logger.error(f"历史记录清理失败: {e}", exc_info=True)
            return 0
    
    def run(self):
        """后台线程主循环"""
        if self.retention_days == 0:
            logger.info(f"清理调度器已启动: 每天 {self.cleanup_time} 执行，不保留历史记录")
        else:
            logger.info(f"清理调度器已启动: 每天 {self.cleanup_time} 执行，保留 {self.retention_days} 天")
        
        # 启动时立即执行一次清理（可选）
        # self.cleanup_expired_records()
        
        while self.running:
            try:
                # 计算下次执行时间
                next_run = self.calculate_next_run_time()
                now = self._get_now()
                wait_seconds = (next_run - now).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"下次清理时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')} "
                              f"(等待 {wait_seconds/3600:.1f} 小时)")
                    
                    # 等待到执行时间
                    time.sleep(wait_seconds)
                
                # 执行清理
                self.cleanup_expired_records()
                
            except Exception as e:
                logger.error(f"清理调度器错误: {e}", exc_info=True)
                # 出错后等待1小时再重试
                time.sleep(3600)
    
    def stop(self):
        """停止调度器"""
        self.running = False
        logger.info("清理调度器已停止")

