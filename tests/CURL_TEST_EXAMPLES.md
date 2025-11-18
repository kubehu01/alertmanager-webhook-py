# CURL 测试命令示例

本文档提供了直接使用 `curl` 命令测试 Alertmanager Webhook 的示例。

## 基本格式

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"alerts": [...]}' \
  "http://127.0.0.1:9095/<机器人类型>?key=<key>"
```

## 企业微信测试

### 方式一：使用URL参数指定key（推荐）

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
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
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/qywechat?key=your_key_here"
```

### 方式二：使用配置文件中的key

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
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
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/qywechat"
```

### 测试告警恢复

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
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
        "startsAt": "2024-01-10T11:59:09.775Z",
        "endsAt": "2024-01-10T12:05:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/qywechat?key=your_key_here"
```

## 飞书测试

### 方式一：使用URL参数指定key（推荐）

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/feishu?key=your_token_here"
```

### 方式二：使用配置文件中的key

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/feishu"
```

### 测试告警恢复

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "resolved",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "endsAt": "2024-01-10T12:05:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/feishu?key=your_token_here"
```

## 钉钉测试

### 方式一：使用URL参数指定key（推荐）

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/dingtalk?key=your_access_token_here"
```

### 方式二：使用配置文件中的key

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/dingtalk"
```

### 测试告警恢复

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "resolved",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "endsAt": "2024-01-10T12:05:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/dingtalk?key=your_access_token_here"
```

## 使用代理的示例

如果需要使用代理，请在配置文件中设置对应的baseUrl为代理地址，然后使用key参数：

### 企业微信（通过代理）

在配置文件中设置：
```yaml
qywechatBaseUrl: https://proxy.example.com:58443/cgi-bin/webhook/send
```

然后使用：
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "alerts": [
      {
        "status": "firing",
        "labels": {
          "alertname": "机器宕机监测",
          "instance": "10.180.48.2"
        },
        "annotations": {
          "summary": "机器发生宕机"
        },
        "startsAt": "2024-01-10T11:59:09.775Z",
        "fingerprint": "02f13394997e5211"
      }
    ]
  }' \
  "http://127.0.0.1:9095/qywechat?key=your_key_here"
```

## 简化版本（单行命令）

### 企业微信触发告警（使用key）

```bash
curl -X POST -H "Content-Type: application/json" -d '{"alerts":[{"status":"firing","labels":{"alertname":"测试告警"},"annotations":{"summary":"测试告警"},"startsAt":"2024-01-10T11:59:09.775Z","fingerprint":"test123"}]}' "http://127.0.0.1:9095/qywechat?key=your_key_here"
```

### 飞书触发告警（使用key）

```bash
curl -X POST -H "Content-Type: application/json" -d '{"alerts":[{"status":"firing","labels":{"alertname":"测试告警"},"annotations":{"summary":"测试告警"},"startsAt":"2024-01-10T11:59:09.775Z","fingerprint":"test123"}]}' "http://127.0.0.1:9095/feishu?key=your_token_here"
```

### 钉钉触发告警（使用key）

```bash
curl -X POST -H "Content-Type: application/json" -d '{"alerts":[{"status":"firing","labels":{"alertname":"测试告警"},"annotations":{"summary":"测试告警"},"startsAt":"2024-01-10T11:59:09.775Z","fingerprint":"test123"}]}' "http://127.0.0.1:9095/dingtalk?key=your_access_token_here"
```

## 注意事项

1. **参数优先级**（所有机器人统一）：
   - `?key=xxx` - 最高优先级，使用配置文件中的baseUrl或默认baseUrl，支持代理
   - 配置文件中的 `key` - 最低优先级
2. **代理支持**：如需使用代理，请在配置文件中设置对应的baseUrl为代理地址
3. **时间格式**：`startsAt` 和 `endsAt` 使用 ISO 8601 格式（UTC时间）
4. **端口号**：默认端口是 `9095`，如果修改了配置请相应调整
5. **key说明**：
   - 企业微信：使用机器人的key
   - 飞书：使用机器人的token
   - 钉钉：使用机器人的access_token

## 健康检查

```bash
curl http://127.0.0.1:9095/health
```

