"""
消息转换器：将Alertmanager通知转换为机器人消息格式（支持企业微信、飞书、钉钉）
"""
import os
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple, Union
from jinja2 import Template
import logging

from models import Notification, Alert, QyWeChatMarkdown, FeishuMarkdown, DingTalkMarkdown
from storage import StorageBackend

logger = logging.getLogger(__name__)

# 中国时区
CST = timezone(timedelta(hours=8))


class Transformer:
    """消息转换器"""
    
    # 告警 key 过期时间（7天），防止未恢复的告警导致内存泄漏（仅 Redis 使用）
    ALERT_KEY_TTL = 7 * 24 * 60 * 60  # 7天，单位：秒
    
    def __init__(self, storage_backend: StorageBackend, template_path: str = "template/alert.tmpl"):
        """
        初始化转换器
        
        Args:
            storage_backend: 存储后端实例（Redis 或 SQLite）
            template_path: 模板文件路径
        """
        self.storage = storage_backend
        self.template_path = template_path
    
    def close(self):
        """关闭存储连接"""
        if self.storage:
            self.storage.close()
    
    def _parse_alert(self, alert_data: dict) -> Alert:
        """解析单个告警数据"""
        # 解析时间
        starts_at = datetime.fromisoformat(alert_data["startsAt"].replace("Z", "+00:00"))
        ends_at = None
        if alert_data.get("endsAt"):
            ends_at = datetime.fromisoformat(alert_data["endsAt"].replace("Z", "+00:00"))
        
        alert = Alert(
            status=alert_data["status"],
            labels=alert_data.get("labels", {}),
            annotations=alert_data.get("annotations", {}),
            startsAt=starts_at,
            endsAt=ends_at,
            fingerprint=alert_data.get("fingerprint", "")
        )
        return alert
    
    def _load_template(self) -> Template:
        """加载模板文件"""
        # 处理模板路径
        template_path = self.template_path
        if not os.path.isabs(template_path):
            # 相对路径，从项目根目录查找
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            template_path = os.path.join(base_dir, template_path)
        
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
            return Template(template_content)
        except FileNotFoundError:
            logger.warning(f"模板文件不存在: {template_path}，使用默认模板")
            # 返回默认模板
            default_template = """{% if alert.status == 'firing' %}
**<font color="orange">告警主题: {{ alert.annotations.get('summary', '') }}</font>**
告警项目: {{ alert.labels.get('project_name') or alert.labels.get('project') or '' }}
告警级别: {{ alert.labels.get('serverity') or alert.labels.get('severity') or '' }}
告警次数: {{ alert.count }}
告警详情: {{ alert.annotations.get('description', '') }}
触发时间: {{ alert.startTime }}

{% elif alert.status == 'resolved' %}
**<font color="green">告警主题: {{ alert.annotations.get('summary', '') }}</font>**
告警项目: {{ alert.labels.get('project_name') or alert.labels.get('project') or '' }}
告警详情: {{ alert.annotations.get('description', '') }}
开始时间: {{ alert.startTime }}
恢复时间: {{ alert.endTime }}
{% endif %}"""
            return Template(default_template)
    
    def _format_markdown_for_robot(self, content: str, robot_type: str) -> str:
        """
        根据机器人类型格式化Markdown内容
        
        Args:
            content: 原始Markdown内容
            robot_type: 机器人类型
        
        Returns:
            格式化后的Markdown内容
        """
        if not content:
            return content
        
        # 企业微信和飞书都支持HTML标签，钉钉需要转换
        if robot_type == "dingtalk":
            # 钉钉不支持<font>标签，需要转换为Markdown格式
            # 将 <font color="red">文本</font> 转换为 **文本**
            content = re.sub(r'<font color="red">(.*?)</font>', r'**\1**', content)
            content = re.sub(r'<font color="green">(.*?)</font>', r'**\1**', content)
            content = re.sub(r'<font color="orange">(.*?)</font>', r'**\1**', content)
            # 移除其他HTML标签
            content = re.sub(r'<[^>]+>', '', content)
        
        return content
    
    def transform_to_markdown(self, notification_data: dict, robot_type: str = "qywechat") -> Tuple[Optional[Union[QyWeChatMarkdown, FeishuMarkdown, DingTalkMarkdown]], Optional[Union[QyWeChatMarkdown, FeishuMarkdown, DingTalkMarkdown]]]:
        """
        将Alertmanager通知转换为机器人Markdown消息
        
        Args:
            notification_data: Alertmanager通知数据
            robot_type: 机器人类型，可选值: "qywechat"（企业微信）、"feishu"（飞书）、"dingtalk"（钉钉）
        
        Returns:
            (firing_message, resolved_message): 触发告警消息和恢复告警消息
        """
        try:
            # 解析通知数据
            notification = Notification(
                version=notification_data.get("version", ""),
                groupKey=notification_data.get("groupKey", ""),
                status=notification_data.get("status", ""),
                receiver=notification_data.get("receiver", ""),
                groupLabels=notification_data.get("groupLabels", {}),
                commonLabels=notification_data.get("commonLabels", {}),
                externalURL=notification_data.get("externalURL", ""),
                alerts=[]
            )
            
            # 解析告警列表
            for alert_data in notification_data.get("alerts", []):
                alert = self._parse_alert(alert_data)
                notification.alerts.append(alert)
            
            # 分离firing和resolved告警
            firing_alerts = [a for a in notification.alerts if a.status == "firing"]
            resolved_alerts = [a for a in notification.alerts if a.status == "resolved"]
            
            # 记录日志：聚合告警处理情况
            if len(notification.alerts) > 1:
                logger.info(f"收到聚合告警通知: 总计 {len(notification.alerts)} 个告警, "
                          f"firing: {len(firing_alerts)} 个, resolved: {len(resolved_alerts)} 个")
            
            # 检查是否有重复的fingerprint（理论上不应该发生，但作为安全检查）
            all_fingerprints = [a.fingerprint for a in notification.alerts if a.fingerprint]
            if len(all_fingerprints) != len(set(all_fingerprints)):
                logger.warning(f"检测到重复的fingerprint，可能存在数据不一致风险")
            
            # 加载模板
            template = self._load_template()
            
            # 处理firing告警
            firing_content = ""
            if firing_alerts:
                firing_parts = []
                for alert in firing_alerts:
                    # 格式化开始时间
                    alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 使用存储后端记录告警次数和关键信息
                    fingerprint = alert.fingerprint
                    if fingerprint and self.storage:
                        try:
                            # 检查是否首次触发
                            is_new = not self.storage.exists(fingerprint)
                            
                            # 增加计数
                            alert.count = self.storage.increment_count(fingerprint)
                            
                            # 设置过期时间（仅 Redis 使用）
                            self.storage.expire(fingerprint, self.ALERT_KEY_TTL)
                            
                            # 只在首次触发时设置开始时间和关键信息
                            if is_new:
                                self.storage.set_start_time(fingerprint, alert.startTime)
                                
                                # 存储告警关键信息
                                alertname = alert.labels.get("alertname", "")
                                summary = alert.annotations.get("summary", "")
                                instance = alert.labels.get("instance", "")
                                severity = alert.labels.get("serverity") or alert.labels.get("sereverity") or ""
                                
                                self.storage.set_alert_info(
                                    fingerprint,
                                    alertname=alertname if alertname else None,
                                    summary=summary if summary else None,
                                    instance=instance if instance else None,
                                    severity=severity if severity else None
                                )
                        except Exception as e:
                            logger.error(f"存储操作失败: {e}")
                            alert.count = 1
                    else:
                        alert.count = 1
                    
                    # 渲染模板
                    try:
                        rendered = template.render(alert=alert)
                        firing_parts.append(rendered)
                    except Exception as e:
                        logger.error(f"模板渲染失败: {e}")
                        firing_parts.append(f"告警主题: {alert.annotations.get('summary', '未知')}\n")
                
                firing_content = "\n".join(firing_parts)
            
            # 处理resolved告警
            resolved_content = ""
            if resolved_alerts:
                resolved_parts = []
                for alert in resolved_alerts:
                    fingerprint = alert.fingerprint
                    if fingerprint and self.storage:
                        try:
                            # 优先使用 Alertmanager 的 startsAt（数据源更权威）
                            # 如果 Alertmanager 没有提供，再从存储获取（作为备用）
                            if alert.startsAt:
                                alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                            else:
                                # 从存储获取开始时间（备用方案）
                                start_time = self.storage.get_start_time(fingerprint)
                                if start_time:
                                    alert.startTime = start_time
                                else:
                                    # 如果都没有，使用当前时间
                                    alert.startTime = datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")
                            
                            # 从存储恢复告警关键信息（如果Alertmanager没有发送）
                            alert_info = self.storage.get_alert_info(fingerprint)
                            
                            # 告警主题
                            if not alert.annotations.get("summary") and alert_info.get("summary"):
                                alert.annotations["summary"] = alert_info["summary"]
                            
                            # 告警主机
                            if not alert.labels.get("instance") and alert_info.get("instance"):
                                alert.labels["instance"] = alert_info["instance"]
                            
                            # 告警规则名称
                            if not alert.labels.get("alertname") and alert_info.get("alertname"):
                                alert.labels["alertname"] = alert_info["alertname"]
                            
                            # 格式化结束时间
                            alert.endTime = alert.endsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S") if alert.endsAt else ""
                            
                            # 删除存储中的记录（标记为 resolved）
                            self.storage.delete(fingerprint, ends_at=alert.endTime)
                        except Exception as e:
                            logger.error(f"存储操作失败: {e}")
                            alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                            alert.endTime = alert.endsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S") if alert.endsAt else ""
                    else:
                        alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                        alert.endTime = alert.endsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S") if alert.endsAt else ""
                    
                    # 渲染模板
                    try:
                        rendered = template.render(alert=alert)
                        resolved_parts.append(rendered)
                    except Exception as e:
                        logger.error(f"模板渲染失败: {e}")
                        resolved_parts.append(f"告警主题: {alert.annotations.get('summary', '未知')}\n")
                
                resolved_content = "\n".join(resolved_parts)
            
            # 根据机器人类型构建消息
            robot_type = robot_type.lower()
            
            # 转换Markdown格式（不同机器人支持的格式略有差异）
            firing_content_formatted = self._format_markdown_for_robot(firing_content, robot_type)
            resolved_content_formatted = self._format_markdown_for_robot(resolved_content, robot_type)
            
            firing_message = None
            resolved_message = None
            
            if robot_type == "qywechat":
                # 企业微信
                if firing_content:
                    title = "# <font color=\"red\">触发告警</font>\n"
                    firing_message = QyWeChatMarkdown()
                    firing_message.set_content(title + firing_content)
                
                if resolved_content:
                    title = "# <font color=\"green\">告警恢复</font>\n"
                    resolved_message = QyWeChatMarkdown()
                    resolved_message.set_content(title + resolved_content)
            
            elif robot_type == "feishu":
                # 飞书
                if firing_content:
                    title = "<font color=\"red\">触发告警</font>\n"
                    firing_message = FeishuMarkdown()
                    firing_message.set_content(title + firing_content_formatted)
                
                if resolved_content:
                    title = "<font color=\"green\">告警恢复</font>\n"
                    resolved_message = FeishuMarkdown()
                    resolved_message.set_content(title + resolved_content_formatted)
            
            elif robot_type == "dingtalk":
                # 钉钉
                if firing_content:
                    firing_message = DingTalkMarkdown()
                    firing_message.set_content(firing_content_formatted, title="触发告警")
                
                if resolved_content:
                    resolved_message = DingTalkMarkdown()
                    resolved_message.set_content(resolved_content_formatted, title="告警恢复")
            
            else:
                logger.warning(f"未知的机器人类型: {robot_type}，不支持该类型的请求")
            
            return firing_message, resolved_message
            
        except Exception as e:
            logger.error(f"消息转换失败: {e}", exc_info=True)
            return None, None

