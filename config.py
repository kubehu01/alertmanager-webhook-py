"""
配置管理模块
"""
import os
import yaml
from pathlib import Path
from typing import Optional


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
        self.qywechat_key = config_data.get("qywechatKey", "")
        self.redis_server = config_data.get("redisServer", "127.0.0.1")
        self.redis_port = config_data.get("redisPort", "6379")
        self.redis_password = config_data.get("redisPassword", "")
        self.log_file_dir = config_data.get("logFileDir", "")
        self.log_file_path = config_data.get("logFilePath", "alertmanager-webhook.log")
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

