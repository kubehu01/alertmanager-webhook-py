# Alertmanager Webhook (Python版)

一个用于Alertmanager转发告警信息到企业微信机器人的Webhook服务，使用Python实现。

## 功能特性

1. 支持自定义告警模板
2. 支持对接企业微信机器人
3. 使用Redis记录告警次数和开始时间
4. 区分触发告警(firing)和告警恢复(resolved)状态
5. 支持通过URL参数传递企业微信key，方便在Alertmanager中为不同receiver配置不同的key

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

编辑 `config.yaml` 配置文件：

```yaml
# 企业微信机器人key（必须配置）
qywechatKey: your_webhook_key_here

# Redis配置
redisServer: 127.0.0.1
redisPort: 6379
redisPassword:  # 如果Redis设置了密码，请填写

# 日志配置
logFileDir:   # 日志目录，为空则使用程序运行目录
logFilePath: alertmanager-webhook.log

# 服务监听配置
port: 9095
host: 0.0.0.0
```

## 使用方法

### 1. 启动服务

```bash
python app.py -c config.yaml
```

### 2. 在Alertmanager中配置webhook

编辑 `alertmanager.yml`：

**方式一：使用配置文件中的key（默认方式）**

```yaml
receivers:
  - name: webhook
    webhook_configs:
      - url: 'http://127.0.0.1:9095/qywechat'
```

**方式二：通过URL参数传递key（推荐，支持不同receiver使用不同的key）**

```yaml
receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://127.0.0.1:9095/qywechat?key=0a8a0d1a-8287-490f-85dd-4e144fe7cedc'
        send_resolved: true
```

> **注意**：如果URL中包含`key`参数，将优先使用URL参数中的key；如果URL中没有`key`参数，则使用配置文件中的key。这样既支持统一配置，也支持为不同receiver配置不同的企业微信机器人。

### 3. 测试接口

使用curl测试：

```bash
curl -X POST -H "Content-Type: application/json" -d '{
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
}' http://127.0.0.1:9095/qywechat
```

## 自定义模板

编辑 `template/alert.tmpl` 文件来自定义告警消息格式。

模板使用Jinja2语法，可用变量：
- `alert.status`: 告警状态 (firing/resolved)
- `alert.labels`: 告警标签字典
- `alert.annotations`: 告警注释字典
- `alert.count`: 告警次数（仅firing状态）
- `alert.startTime`: 开始时间
- `alert.endTime`: 结束时间（仅resolved状态）

## 项目结构

```
alertmanager-webhook-python/
├── app.py              # 主程序
├── config.py           # 配置管理
├── models.py           # 数据模型
├── transformer.py      # 消息转换器
├── sender.py           # 企业微信发送模块
├── config.yaml         # 配置文件
├── requirements.txt    # 依赖包
├── template/
│   └── alert.tmpl      # 告警模板
└── README.md           # 说明文档
```

## 注意事项

1. 需要先启动Redis服务
2. 确保企业微信机器人webhook key配置正确
3. 模板文件路径相对于程序运行目录

## 健康检查

```bash
curl http://127.0.0.1:9095/health
```

## 测试

使用Python测试脚本：

```bash
# 测试触发告警
python test_webhook.py

# 测试告警恢复
python test_webhook.py resolved
```

