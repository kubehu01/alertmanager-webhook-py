"""
企业微信消息发送模块
"""
import requests
import logging
from typing import Optional

from models import QyWeChatMarkdown

logger = logging.getLogger(__name__)


class QyWeChatSender:
    """企业微信消息发送器"""
    
    def __init__(self, webhook_key: str):
        self.webhook_key = webhook_key
        self.webhook_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={webhook_key}"
    
    def send(self, message: QyWeChatMarkdown) -> bool:
        """
        发送消息到企业微信
        
        Args:
            message: 企业微信Markdown消息对象
            
        Returns:
            bool: 发送是否成功
        """
        if not self.webhook_key:
            logger.warning("企业微信key未配置")
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

