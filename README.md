# Alertmanager Webhook (Python版)

一个用于Alertmanager转发告警信息到企业微信机器人的Webhook服务，使用Python实现。

## 功能特性

1. 支持自定义告警模板
2. 支持对接企业微信机器人
3. 使用Redis记录告警次数和开始时间
4. 区分触发告警(firing)和告警恢复(resolved)状态
5. 支持通过URL参数传递企业微信key，方便在Alertmanager中为不同receiver配置不同的key
6. 支持通过URL参数传递完整的企业微信webhook URL（支持代理）
7. 支持通过URL参数传递webhook基础URL和key（支持代理）
8. 支持在配置文件中配置webhook基础URL（支持代理）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 配置说明

编辑 `config/config.yaml` 配置文件（可复制 `config/config.yaml.example` 并重命名）：

```yaml
# 企业微信机器人key
qywechatKey: your_webhook_key_here

# Webhook基础URL（可选）
# 不配置则使用默认官方地址: https://qyapi.weixin.qq.com/cgi-bin/webhook/send
# 如果使用正向代理，可以配置代理地址，例如: https://proxy.example.com:58443/cgi-bin/webhook/send
webhookBaseUrl: https://qyapi.weixin.qq.com/cgi-bin/webhook/send

# Redis配置
redisServer: 127.0.0.1
redisPort: 6379
redisPassword:  # 如果Redis设置了密码，请填写

# 日志配置
logFileDir: logs  # 日志目录，为空则默认为logs目录
logFilePath: alertmanager-webhook.log  # 日志文件名，为空则默认为alertmanager-webhook.log

# 服务监听配置
port: 9095
host: 0.0.0.0
```

## 使用方法

### 1. 启动服务

```bash
# 方式一：使用服务管理脚本（推荐，Linux/Mac）
bash service.sh start        # 启动服务
bash service.sh stop         # 停止服务
bash service.sh restart      # 重启服务
bash service.sh status       # 查看服务状态
bash service.sh help         # 查看帮助信息

# 方式二：直接使用Python
python src/app.py                          # 使用默认配置文件路径
python src/app.py -c config/config.yaml    # 指定配置文件路径
```

### 2. 在Alertmanager中配置webhook

编辑 `alertmanager.yml`：

**方式一：使用配置文件中的key和baseUrl（默认方式）**

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
      - url: 'http://127.0.0.1:9095/qywechat?key=xxx'
        send_resolved: true
```

**方式三：通过URL参数传递完整的企业微信webhook URL（最高优先级，支持代理）**

```yaml
receivers:
  - name: 'custom-receiver'
    webhook_configs:
      # 使用官方地址
      - url: 'http://127.0.0.1:9095/qywechat?url=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx'
        send_resolved: true
      
  - name: 'proxy-receiver'
    webhook_configs:
      # 使用代理地址（推荐使用此方式配置代理）
      - url: 'http://127.0.0.1:9095/qywechat?url=https://proxy.example.com:58443/cgi-bin/webhook/send?key=xxx'
        send_resolved: true
```

> **优先级说明**：
> 1. URL参数 `url`（完整URL，最高优先级，支持代理）
> 2. URL参数 `baseUrl` + `key`（基础URL + key，支持代理）
> 3. URL参数 `key`（仅key，使用配置文件中的baseUrl或默认）
> 4. 配置文件中的 `qywechatKey` + `webhookBaseUrl`（最低优先级）
>
> **使用场景**：
> - **方式一**：适合统一配置，所有receiver使用相同的企业微信机器人
> - **方式二**：适合不同receiver使用不同的企业微信机器人，但都使用相同的webhook地址（官方或代理）
> - **方式三**：适合需要完全自定义webhook URL的场景，包括使用代理（推荐使用此方式配置代理）

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
}' http://127.0.0.1:9095/qywechat?key=xxxx
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
├── src/                # 源代码目录
│   ├── __init__.py
│   ├── app.py          # 主程序
│   ├── config.py       # 配置管理
│   ├── models.py       # 数据模型
│   ├── transformer.py  # 消息转换器
│   └── sender.py       # 企业微信发送模块
├── config/             # 配置文件目录
│   └── config.yaml.example  # 配置示例文件
├── template/           # 模板目录
│   └── alert.tmpl      # 告警模板
├── logs/               # 日志目录（自动创建）
│   └── .gitkeep        # 保留目录结构
├── tests/              # 测试目录
│   ├── test_webhook.py # Python测试脚本
│   └── test_webhook.sh # Shell测试脚本
├── requirements.txt    # 依赖包
├── service.sh           # 服务管理脚本（支持start/stop/restart/status）
└── README.md           # 说明文档
```

## 注意事项

1. 需要先启动Redis服务
2. 确保企业微信机器人webhook key配置正确
3. 配置文件需要放在 `config/` 目录下，或通过 `-c` 参数指定路径
4. 模板文件位于 `template/` 目录下
5. 日志文件默认写入 `logs/` 目录，程序会自动创建该目录

## 健康检查

```bash
curl http://127.0.0.1:9095/health
```

## 测试

### 使用Python测试脚本

```bash
# 测试触发告警
python tests/test_webhook.py

# 测试告警恢复
python tests/test_webhook.py resolved
```

### 使用Shell测试脚本

```bash
# 测试触发告警（使用默认key）
bash tests/test_webhook.sh

# 测试触发告警（使用指定key）
bash tests/test_webhook.sh your_key_here

# 测试告警恢复（使用指定key）
bash tests/test_webhook.sh your_key_here resolved

# 查看帮助信息
bash tests/test_webhook.sh --help
```

