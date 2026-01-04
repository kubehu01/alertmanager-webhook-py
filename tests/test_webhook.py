#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试脚本：模拟Alertmanager发送告警通知
支持企业微信、飞书、钉钉
"""
import sys
import requests
from datetime import datetime, timezone

# 各平台消息长度限制（字符数）
QYWECHAT_MAX_LENGTH = 4096
FEISHU_MAX_LENGTH = 8000
DINGTALK_MAX_LENGTH = 5000

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


def get_long_test_data(robot_type="qywechat", alert_status="firing"):
    """获取超长消息测试数据
    
    注意：需要考虑模板渲染后的实际长度
    模板会添加：标题、项目、级别、次数、时间等信息（约200-300字符）
    企业微信还会添加标题行（约30字符）
    所以description需要生成足够长的内容，确保最终消息超过限制
    """
    # 根据机器人类型确定目标长度（超过限制）
    # 考虑模板固定内容约300字符，所以description需要生成：限制长度 + 1500字符
    if robot_type == "qywechat":
        # 企业微信限制4096，生成5600字符的description，渲染后约5900字符
        target_length = QYWECHAT_MAX_LENGTH + 1500  # 5596字符
    elif robot_type == "feishu":
        # 飞书限制8000，生成9500字符的description，渲染后约9800字符
        target_length = FEISHU_MAX_LENGTH + 1500    # 9500字符
    elif robot_type == "dingtalk":
        # 钉钉限制5000，生成6500字符的description，渲染后约6800字符
        target_length = DINGTALK_MAX_LENGTH + 1500  # 6500字符
    else:
        target_length = 6000
    
    # 生成超长描述文本（模拟真实的告警详情，包含多行信息）
    base_text = "【告警详情】这是一个超长告警描述，用于测试消息长度超限时的自动分割功能。"
    detail_lines = [
        "告警实例: 10.180.48.2",
        "告警服务: node_exporter",
        "告警级别: warning",
        "告警规则: 机器宕机监测",
        "告警描述: 机器宕机超过1分钟，请立即检查服务器状态。",
        "建议操作: 1. 检查服务器是否正常运行 2. 检查网络连接 3. 查看系统日志 4. 联系运维人员",
        "相关指标: CPU使用率、内存使用率、磁盘IO、网络流量等",
        "告警时间: " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    ]
    
    # 生成重复的详细信息块
    detail_block = "\n".join(detail_lines)
    repeat_count = target_length // len(detail_block) + 1
    
    # 生成超长描述
    long_description = base_text + "\n\n"
    for i in range(repeat_count):
        long_description += f"--- 详细信息块 {i+1} ---\n"
        long_description += detail_block
        long_description += f"\n详细信息块 {i+1} 结束\n\n"
        if len(long_description) >= target_length:
            break
    
    # 确保达到目标长度
    if len(long_description) < target_length:
        padding = "这是填充内容，用于确保消息长度达到测试要求。" * ((target_length - len(long_description)) // 20 + 1)
        long_description += padding[:target_length - len(long_description)]
    else:
        long_description = long_description[:target_length]
    
    data = {
        "alerts": [
            {
                "status": alert_status,
                "labels": {
                    "alertname": "超长消息测试告警",
                    "instance": "10.180.48.2",
                    "job": "node_exporter",
                    "serverity": "warning",
                    "project_name": "生产环境"
                },
                "annotations": {
                    "description": long_description,
                    "summary": "超长消息测试 - 用于验证消息自动分割功能（消息长度将超过平台限制）"
                },
                "startsAt": datetime.now(timezone.utc).isoformat(),
                "fingerprint": f"long_test_{int(datetime.now(timezone.utc).timestamp())}"
            }
        ]
    }
    if alert_status == "resolved":
        data["alerts"][0]["endsAt"] = datetime.now(timezone.utc).isoformat()
    
    return data, len(long_description)


def test_qywechat(alert_status="firing", key=None, long_message=False):
    """测试企业微信"""
    if key:
        url = f"http://127.0.0.1:9095/qywechat?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/qywechat"
    
    if long_message:
        data, msg_length = get_long_test_data("qywechat", alert_status)
        print(f"企业微信 - 描述长度: {msg_length} 字符（超过限制 {QYWECHAT_MAX_LENGTH}）")
        print(f"企业微信 - 渲染后预计: 约 {msg_length + 300} 字符，将被分割为多条消息")
        print(f"企业微信 - 预期行为: 消息将被自动分割，每条消息会显示序号 (1/N), (2/N) 等")
    else:
        data = get_test_data(alert_status)
    
    response = requests.post(url, json=data)
    print(f"企业微信 - 状态码: {response.status_code}")
    print(f"企业微信 - 响应: {response.json()}")


def test_feishu(alert_status="firing", key=None, long_message=False):
    """测试飞书"""
    if key:
        url = f"http://127.0.0.1:9095/feishu?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/feishu"
    
    if long_message:
        data, msg_length = get_long_test_data("feishu", alert_status)
        print(f"飞书 - 描述长度: {msg_length} 字符（超过限制 {FEISHU_MAX_LENGTH}）")
        print(f"飞书 - 渲染后预计: 约 {msg_length + 300} 字符，将被分割为多条消息")
        print(f"飞书 - 预期行为: 消息将被自动分割，每条消息会显示序号 (1/N), (2/N) 等")
    else:
        data = get_test_data(alert_status)
    
    response = requests.post(url, json=data)
    print(f"飞书 - 状态码: {response.status_code}")
    print(f"飞书 - 响应: {response.json()}")


def test_dingtalk(alert_status="firing", key=None, long_message=False):
    """测试钉钉"""
    if key:
        url = f"http://127.0.0.1:9095/dingtalk?key={key}"
    else:
        # 使用配置文件中的key
        url = "http://127.0.0.1:9095/dingtalk"
    
    if long_message:
        data, msg_length = get_long_test_data("dingtalk", alert_status)
        print(f"钉钉 - 描述长度: {msg_length} 字符（超过限制 {DINGTALK_MAX_LENGTH}）")
        print(f"钉钉 - 渲染后预计: 约 {msg_length + 300} 字符，将被分割为多条消息")
        print(f"钉钉 - 预期行为: 消息将被自动分割，每条消息会显示序号 (1/N), (2/N) 等")
    else:
        data = get_test_data(alert_status)
    
    response = requests.post(url, json=data)
    print(f"钉钉 - 状态码: {response.status_code}")
    print(f"钉钉 - 响应: {response.json()}")


if __name__ == "__main__":
    # 解析参数
    robot_type = "qywechat"  # 默认企业微信
    alert_status = "firing"   # 默认触发告警
    key = None                # 默认使用配置文件
    long_message = False      # 是否测试超长消息
    
    # 解析命令行参数
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i].lower()
        if arg in ["qywechat", "feishu", "dingtalk"]:
            robot_type = arg
        elif arg in ["firing", "resolved"]:
            alert_status = arg
        elif arg in ["long", "length"]:
            long_message = True
        else:
            # 其他参数作为key
            key = sys.argv[i]
        i += 1
    
    # 执行测试
    if long_message:
        print("测试超长消息（自动分割功能）...")
        print(f"机器人类型: {robot_type}")
        print("预期行为: 消息将被自动分割为多条发送")
    else:
        status_text = "触发告警" if alert_status == "firing" else "告警恢复"
        print(f"测试{status_text}...")
        print(f"机器人类型: {robot_type}")
    
    if key:
        print(f"Key: {key}")
    else:
        print("使用配置文件中的key")
    print("")
    
    if robot_type == "qywechat":
        test_qywechat(alert_status, key, long_message)
    elif robot_type == "feishu":
        test_feishu(alert_status, key, long_message)
    elif robot_type == "dingtalk":
        test_dingtalk(alert_status, key, long_message)
    else:
        print(f"错误: 未知的机器人类型 '{robot_type}'")
        print("支持的机器人类型: qywechat, feishu, dingtalk")


