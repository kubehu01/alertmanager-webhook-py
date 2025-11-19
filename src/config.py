"""
配置管理模块
"""
import os
import yaml
import logging


class Config:
    """配置类"""
    def __init__(self, config_file: str):
        self._load_config(config_file)
    
    def _load_config(self, config_file: str):
        """加载配置文件"""
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"配置文件不存在: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            config_data = yaml.safe_load(f)
        
        if not config_data:
            raise ValueError("配置文件为空或格式错误")
        
        # 读取配置项
        # 企业微信配置
        self.qywechat_key = config_data.get("qywechatKey", "")
        self.qywechat_base_url = config_data.get("qywechatBaseUrl", "https://qyapi.weixin.qq.com/cgi-bin/webhook/send")
        # 飞书配置
        self.feishu_key = config_data.get("feishuKey", "")
        self.feishu_base_url = config_data.get("feishuBaseUrl", "https://open.feishu.cn/open-apis/bot/v2/hook")
        # 钉钉配置
        self.dingtalk_key = config_data.get("dingtalkKey", "")
        self.dingtalk_base_url = config_data.get("dingtalkBaseUrl", "https://oapi.dingtalk.com/robot/send")
        
        # 存储配置
        use_storage_raw = config_data.get("useStorage", "sqlite")
        # 处理空值、None 或空字符串的情况
        if not use_storage_raw or not isinstance(use_storage_raw, str) or not use_storage_raw.strip():
            use_storage = "sqlite"
        else:
            use_storage = use_storage_raw.strip().lower()
        
        # 验证存储类型，如果不是 redis 或 sqlite，则使用 sqlite
        if use_storage not in ["redis", "sqlite"]:
            logger = logging.getLogger(__name__)
            logger.warning(f"无效的存储类型: '{use_storage_raw}'，自动设置为 'sqlite'")
            use_storage = "sqlite"
        
        self.use_storage = use_storage
        
        # Redis配置（当 useStorage=redis 时生效）
        self.redis_server = config_data.get("redisServer", "127.0.0.1")
        self.redis_port = config_data.get("redisPort", "6379")
        self.redis_password = config_data.get("redisPassword", "")
        self.redis_username = config_data.get("redisUsername", "")  # Redis 6.0+ ACL支持
        
        # SQLite配置（当 useStorage=sqlite 时生效）
        self.sqlite_db_path = config_data.get("sqliteDbPath", "logs/alerts.db")
        
        # 历史记录保留配置（仅当 useStorage=sqlite 时生效）
        history_retention = config_data.get("historyRetention", {})
        self.history_retention_days = history_retention.get("days", 30)
        self.history_cleanup_time = history_retention.get("cleanupTime", "05:00")
        self.history_timezone = history_retention.get("timezone", "Asia/Shanghai")
        
        self.log_file_dir = config_data.get("logFileDir", "logs")
        self.log_file_path = config_data.get("logFilePath", "alertmanager-webhook.log")
        # 日志级别配置，支持: DEBUG, INFO, WARNING, ERROR, CRITICAL，默认为 INFO
        log_level_str = config_data.get("logLevel", "INFO").upper()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level_str not in valid_levels:
            logger = logging.getLogger(__name__)
            logger.warning(f"无效的日志级别: '{log_level_str}'，使用默认值 'INFO'")
            log_level_str = "INFO"
        self.log_level = log_level_str
        self.port = config_data.get("port", "9095")
        self.host = config_data.get("host", "127.0.0.1")
        
        # 处理日志文件路径
        if self.log_file_dir:
            self.log_file_path = os.path.join(self.log_file_dir, self.log_file_path)
        else:
            workdir = os.getcwd()
            self.log_file_path = os.path.join(workdir, self.log_file_path)
        
        # 确保日志目录存在
        log_dir = os.path.dirname(self.log_file_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)


