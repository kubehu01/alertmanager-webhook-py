"""
企业微信消息发送模块
"""
import requests
import logging
from typing import Optional
from urllib.parse import urlparse, parse_qs

from models import QyWeChatMarkdown

logger = logging.getLogger(__name__)

# 默认官方webhook基础URL
DEFAULT_WEBHOOK_BASE_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"


class QyWeChatSender:
    """企业微信消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = DEFAULT_WEBHOOK_BASE_URL, webhook_url: str = ""):
        """
        初始化企业微信发送器
        
        Args:
            key: 企业微信机器人key（当webhook_url为空时使用）
            webhook_base_url: webhook基础URL（当webhook_url为空时使用，默认官方地址）
            webhook_url: 完整的webhook URL（优先级最高，如果提供则忽略其他参数）
        """
        if webhook_url:
            # 如果提供了完整URL，直接使用
            self.webhook_url = webhook_url
            # 尝试从URL中提取key用于日志（隐藏敏感信息）
            try:
                parsed = urlparse(webhook_url)
                params = parse_qs(parsed.query)
                if 'key' in params:
                    self.key = params['key'][0]
                else:
                    self.key = "从完整URL中提取"
            except Exception:
                self.key = "从完整URL中提取"
        else:
            # 使用基础URL + key组合
            self.key = key
            # 确保基础URL不以?结尾
            base_url = webhook_base_url.rstrip('?')
            # 组合完整URL，始终使用?拼接key参数
            self.webhook_url = f"{base_url}?key={key}"
    
    def send(self, message: QyWeChatMarkdown) -> bool:
        """
        发送消息到企业微信
        
        Args:
            message: 企业微信Markdown消息对象
            
        Returns:
            bool: 发送是否成功
        """
        if not self.webhook_url:
            logger.warning("企业微信webhook URL未配置")
            return False
        
        # 对于完整URL的情况，key可能为空，这是允许的
        if not self.key and 'key=' not in self.webhook_url:
            logger.warning("企业微信key未配置且URL中未包含key参数")
            return False
        
        if not message or not message.markdown.get("content"):
            logger.warning("消息内容为空，跳过发送")
            return False
        
        try:
            response = requests.post(
                self.webhook_url,
                json=message.to_dict(),
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            response.raise_for_status()
            result = response.json()
            
            if result.get("errcode") == 0:
                logger.info("消息发送成功")
                return True
            else:
                logger.error(f"消息发送失败: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"发送消息时发生网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送消息时发生未知错误: {e}", exc_info=True)
            return False
    
    def send_firing(self, message: Optional[QyWeChatMarkdown]) -> bool:
        """发送触发告警消息"""
        if message:
            return self.send(message)
        return False
    
    def send_resolved(self, message: Optional[QyWeChatMarkdown]) -> bool:
        """发送告警恢复消息"""
        if message:
            return self.send(message)
        return False

