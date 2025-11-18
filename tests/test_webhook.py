#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：模拟Alertmanager发送告警通知
支持企业微信、飞书、钉钉
"""
import sys
import requests
from datetime import datetime, timezone

# 测试数据模板
def get_test_data(alert_status="firing"):
    """获取测试数据"""
    data = {
        "alerts": [
            {
                "status": alert_status,
                "labels": {
                    "alertname": "机器宕机监测",
                    "instance": "10.180.48.2",
                    "job": "node_exporter",
                    "serverity": "warning"
                },
                "annotations": {
                    "description": "机器:10.180.48.2 所属 job:node_exporter 宕机超过1分钟，请检查！",
                    "summary": "机器发生宕机"
                },
                "startsAt": datetime.now(timezone.utc).isoformat(),
                "fingerprint": "02f13394997e5211"
            }
        ]
    }
    if alert_status == "resolved":
        data["alerts"][0]["endsAt"] = datetime.now(timezone.utc).isoformat()
    return data


def test_qywechat(alert_status="firing", key=None):
    """测试企业微信"""
    if key:
        url = f"http://127.0.0.1:9095/qywechat?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/qywechat"
    
    data = get_test_data(alert_status)
    response = requests.post(url, json=data)
    print(f"企业微信 - 状态码: {response.status_code}")
    print(f"企业微信 - 响应: {response.json()}")


def test_feishu(alert_status="firing", key=None):
    """测试飞书"""
    if key:
        url = f"http://127.0.0.1:9095/feishu?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/feishu"
    
    data = get_test_data(alert_status)
    response = requests.post(url, json=data)
    print(f"飞书 - 状态码: {response.status_code}")
    print(f"飞书 - 响应: {response.json()}")


def test_dingtalk(alert_status="firing", key=None):
    """测试钉钉"""
    if key:
        url = f"http://127.0.0.1:9095/dingtalk?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/dingtalk"
    
    data = get_test_data(alert_status)
    response = requests.post(url, json=data)
    print(f"钉钉 - 状态码: {response.status_code}")
    print(f"钉钉 - 响应: {response.json()}")


if __name__ == "__main__":
    # 解析参数
    robot_type = "qywechat"  # 默认企业微信
    alert_status = "firing"   # 默认触发告警
    key = None                # 默认使用配置文件
    
    # 解析命令行参数
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i].lower()
        if arg in ["qywechat", "feishu", "dingtalk"]:
            robot_type = arg
        elif arg in ["firing", "resolved"]:
            alert_status = arg
        else:
            # 其他参数作为key
            key = sys.argv[i]
        i += 1
    
    # 执行测试
    status_text = "触发告警" if alert_status == "firing" else "告警恢复"
    print(f"测试{status_text}...")
    print(f"机器人类型: {robot_type}")
    if key:
        print(f"Key: {key}")
    else:
        print("使用配置文件中的key")
    print("")
    
    if robot_type == "qywechat":
        test_qywechat(alert_status, key)
    elif robot_type == "feishu":
        test_feishu(alert_status, key)
    elif robot_type == "dingtalk":
        test_dingtalk(alert_status, key)
    else:
        print(f"错误: 未知的机器人类型 '{robot_type}'")
        print("支持的机器人类型: qywechat, feishu, dingtalk")

