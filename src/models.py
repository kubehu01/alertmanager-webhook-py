"""
数据模型定义
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime


@dataclass
class Alert:
    """告警信息"""
    status: str
    labels: Dict[str, str]
    annotations: Dict[str, str]
    startsAt: datetime
    endsAt: Optional[datetime] = None
    fingerprint: str = ""
    startTime: str = ""
    endTime: str = ""
    count: int = 0


@dataclass
class Notification:
    """Alertmanager通知格式"""
    version: str = ""
    groupKey: str = ""
    status: str = ""
    receiver: str = ""
    groupLabels: Dict[str, str] = field(default_factory=dict)
    commonLabels: Dict[str, str] = field(default_factory=dict)
    externalURL: str = ""
    alerts: List[Alert] = field(default_factory=list)


@dataclass
class QyWeChatMarkdown:
    """企业微信Markdown消息格式"""
    msgtype: str = "markdown"
    markdown: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.markdown:
            self.markdown = {"content": ""}

    def set_content(self, content: str):
        """设置Markdown内容"""
        self.markdown["content"] = content

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "msgtype": self.msgtype,
            "markdown": self.markdown
        }


@dataclass
class FeishuMarkdown:
    """飞书Markdown消息格式"""
    msg_type: str = "interactive"
    card: Dict = field(default_factory=dict)

    def __post_init__(self):
        if not self.card:
            self.card = {
                "config": {
                    "wide_screen_mode": True
                },
                "elements": []
            }

    def set_content(self, content: str):
        """设置Markdown内容"""
        self.card["elements"] = [
            {
                "tag": "div",
                "text": {
                    "tag": "lark_md",
                    "content": content
                }
            }
        ]

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "msg_type": self.msg_type,
            "card": self.card
        }


@dataclass
class DingTalkMarkdown:
    """钉钉Markdown消息格式"""
    msgtype: str = "markdown"
    markdown: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.markdown:
            self.markdown = {
                "title": "告警通知",
                "text": ""
            }

    def set_content(self, content: str, title: str = "告警通知"):
        """设置Markdown内容"""
        self.markdown["title"] = title
        self.markdown["text"] = content

    def to_dict(self) -> dict:
        """转换为字典格式"""
        return {
            "msgtype": self.msgtype,
            "markdown": self.markdown
        }
