"""
机器人消息发送模块（支持企业微信、飞书、钉钉）
"""
import requests
import logging
from typing import Optional

from models import QyWeChatMarkdown, FeishuMarkdown, DingTalkMarkdown

logger = logging.getLogger(__name__)


class QyWeChatSender:
    """企业微信消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"):
        """
        初始化企业微信发送器
        
        Args:
            key: 企业微信机器人key（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("企业微信key不能为空")
        self.key = key
        base_url = webhook_base_url.rstrip('?')
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
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[QyWeChatMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False


class FeishuSender:
    """飞书消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://open.feishu.cn/open-apis/bot/v2/hook"):
        """
        初始化飞书发送器
        
        Args:
            key: 飞书机器人token（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("飞书key不能为空")
        # 使用基础URL + key组合（飞书的key在路径中）
        base_url = webhook_base_url.rstrip('/')
        self.webhook_url = f"{base_url}/{key}"
    
    def send(self, message: FeishuMarkdown) -> bool:
        """
        发送消息到飞书
        
        Args:
            message: 飞书Markdown消息对象
            
        Returns:
            bool: 发送是否成功
        """
        if not message or not message.card.get("elements"):
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
            
            if result.get("code") == 0:
                logger.info("飞书消息发送成功")
                return True
            else:
                logger.error(f"飞书消息发送失败: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"发送飞书消息时发生网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送飞书消息时发生未知错误: {e}", exc_info=True)
            return False
    
    def send_firing(self, message: Optional[FeishuMarkdown]) -> bool:
        """发送触发告警消息"""
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[FeishuMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False


class DingTalkSender:
    """钉钉消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://oapi.dingtalk.com/robot/send"):
        """
        初始化钉钉发送器
        
        Args:
            key: 钉钉机器人access_token（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("钉钉key不能为空")
        # 使用基础URL + key组合（钉钉的key是access_token参数）
        base_url = webhook_base_url.rstrip('?')
        self.webhook_url = f"{base_url}?access_token={key}"
    
    def send(self, message: DingTalkMarkdown) -> bool:
        """
        发送消息到钉钉
        
        Args:
            message: 钉钉Markdown消息对象
            
        Returns:
            bool: 发送是否成功
        """
        if not message or not message.markdown.get("text"):
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
                logger.info("钉钉消息发送成功")
                return True
            else:
                logger.error(f"钉钉消息发送失败: {result}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"发送钉钉消息时发生网络错误: {e}")
            return False
        except Exception as e:
            logger.error(f"发送钉钉消息时发生未知错误: {e}", exc_info=True)
            return False
    
    def send_firing(self, message: Optional[DingTalkMarkdown]) -> bool:
        """发送触发告警消息"""
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[DingTalkMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False

