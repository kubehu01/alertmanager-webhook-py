#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：模拟Alertmanager发送告警通知
"""
import requests
from datetime import datetime, timezone

def test_firing_alert():
    """测试触发告警"""
    url = "http://127.0.0.1:9095/qywechat?key=xxxx"
    
    data = {
        "alerts": [
            {
                "status": "firing",
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
    
    response = requests.post(url, json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


def test_resolved_alert():
    """测试告警恢复"""
    url = "http://127.0.0.1:9095/qywechat?key=xxxx"
    
    data = {
        "alerts": [
            {
                "status": "resolved",
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
                "endsAt": datetime.now(timezone.utc).isoformat(),
                "fingerprint": "02f13394997e5211"
            }
        ]
    }
    
    response = requests.post(url, json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.json()}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "resolved":
        print("测试告警恢复...")
        test_resolved_alert()
    else:
        print("测试触发告警...")
        test_firing_alert()

