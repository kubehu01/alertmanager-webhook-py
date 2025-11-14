"""
消息转换器：将Alertmanager通知转换为企业微信消息格式
"""
import json
import redis
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from jinja2 import Template
import logging

from models import Notification, Alert, QyWeChatMarkdown

logger = logging.getLogger(__name__)

# 中国时区
CST = timezone(timedelta(hours=8))


class Transformer:
    """消息转换器"""
    
    def __init__(self, redis_server: str, redis_port: str, redis_password: str, template_path: str = "template/alert.tmpl"):
        self.redis_server = redis_server
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.template_path = template_path
    
    def _get_redis_client(self) -> Optional[redis.Redis]:
        """获取Redis客户端"""
        try:
            client = redis.Redis(
                host=self.redis_server,
                port=int(self.redis_port),
                password=self.redis_password if self.redis_password else None,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # 测试连接
            client.ping()
            return client
        except Exception as e:
            logger.error(f"Redis连接失败: {e}")
            return None
    
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
        import os
        # 处理模板路径
        template_path = self.template_path
        if not os.path.isabs(template_path):
            # 相对路径，尝试从程序目录查找
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
告警主题: {{ alert.annotations.get('summary', '') }}
告警级别: {{ alert.labels.get('serverity') or alert.labels.get('sereverity') or '' }}
告警次数: {{ alert.count }}
告警主机: {{ alert.labels.get('instance', '') }}
告警详情: {{ alert.annotations.get('description', '') }}
触发时间: {{ alert.startTime }}
{% elif alert.status == 'resolved' %}
告警主题: {{ alert.annotations.get('summary', '') }}
告警主机: {{ alert.labels.get('instance', '') }}
开始时间: {{ alert.startTime }}
恢复时间: {{ alert.endTime }}
{% endif %}"""
            return Template(default_template)
    
    def transform_to_markdown(self, notification_data: dict) -> Tuple[Optional[QyWeChatMarkdown], Optional[QyWeChatMarkdown]]:
        """
        将Alertmanager通知转换为企业微信Markdown消息
        
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
            
            # 获取Redis客户端
            r = self._get_redis_client()
            
            # 加载模板
            template = self._load_template()
            
            # 处理firing告警
            firing_content = ""
            if firing_alerts:
                firing_parts = []
                for alert in firing_alerts:
                    # 格式化开始时间
                    alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 使用Redis记录告警次数和关键信息
                    fingerprint = alert.fingerprint
                    if fingerprint and r:
                        try:
                            # 设置开始时间
                            r.hset(fingerprint, "startTime", alert.startTime)
                            # 增加计数
                            r.hincrby(fingerprint, "count", 1)
                            # 获取计数
                            count = r.hget(fingerprint, "count")
                            alert.count = int(count) if count else 1
                            
                            # 存储告警关键信息（用于resolved时显示）
                            # 只在首次触发时存储，避免覆盖
                            if alert.count == 1:
                                # 存储告警规则名称
                                alertname = alert.labels.get("alertname", "")
                                if alertname:
                                    r.hset(fingerprint, "alertname", alertname)
                                
                                # 存储告警主题
                                summary = alert.annotations.get("summary", "")
                                if summary:
                                    r.hset(fingerprint, "summary", summary)
                                
                                # 存储告警主机
                                instance = alert.labels.get("instance", "")
                                if instance:
                                    r.hset(fingerprint, "instance", instance)
                                
                                # 存储告警级别
                                severity = alert.labels.get("serverity") or alert.labels.get("sereverity") or ""
                                if severity:
                                    r.hset(fingerprint, "severity", severity)
                        except Exception as e:
                            logger.error(f"Redis操作失败: {e}")
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
                    if fingerprint and r:
                        try:
                            # 从Redis获取开始时间
                            start_time = r.hget(fingerprint, "startTime")
                            if start_time:
                                alert.startTime = start_time
                            else:
                                alert.startTime = alert.startsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S")
                            
                            # 从Redis恢复告警关键信息（如果Alertmanager没有发送）
                            # 告警主题
                            if not alert.annotations.get("summary") and r.hget(fingerprint, "summary"):
                                alert.annotations["summary"] = r.hget(fingerprint, "summary")
                            
                            # 告警主机
                            if not alert.labels.get("instance") and r.hget(fingerprint, "instance"):
                                alert.labels["instance"] = r.hget(fingerprint, "instance")
                            
                            # 告警规则名称
                            if not alert.labels.get("alertname") and r.hget(fingerprint, "alertname"):
                                alert.labels["alertname"] = r.hget(fingerprint, "alertname")
                            
                            # 格式化结束时间
                            alert.endTime = alert.endsAt.astimezone(CST).strftime("%Y-%m-%d %H:%M:%S") if alert.endsAt else ""
                            
                            # 删除Redis中的记录
                            r.delete(fingerprint)
                        except Exception as e:
                            logger.error(f"Redis操作失败: {e}")
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
            
            # 构建企业微信消息
            firing_message = None
            if firing_content:
                title = "# <font color=\"red\">触发告警</font>\n"
                firing_message = QyWeChatMarkdown()
                firing_message.set_content(title + firing_content)
            
            resolved_message = None
            if resolved_content:
                title = "# <font color=\"green\">告警恢复</font>\n"
                resolved_message = QyWeChatMarkdown()
                resolved_message.set_content(title + resolved_content)
            
            return firing_message, resolved_message
            
        except Exception as e:
            logger.error(f"消息转换失败: {e}", exc_info=True)
            return None, None

