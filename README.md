# Alertmanager Webhook (Python版)

一个用于Alertmanager转发告警信息到企业微信、飞书、钉钉机器人的Webhook服务，使用Python实现。

## 功能特性

1. 支持自定义告警模板
2. **支持多种机器人平台**：企业微信、飞书、钉钉
3. **灵活的存储后端**：支持 Redis 或 SQLite（默认 SQLite，无需额外服务）
4. **告警状态管理**：记录告警次数、开始时间和关键信息
5. **历史记录管理**：SQLite 模式下支持可配置的历史记录保留和自动清理
6. 区分触发告警(firing)和告警恢复(resolved)状态
7. 支持通过URL参数传递key，方便在Alertmanager中为不同receiver配置不同的机器人
8. 支持在配置文件中配置key和baseUrl（支持代理场景）
9. 统一使用key方式，简化配置，更好地支持代理场景

## 安装依赖

### 方式一：直接安装（本地运行）

```bash
pip install -r requirements.txt
```

### 方式二：Docker 部署（推荐）

使用 Docker Compose 一键部署：

```bash
# 1. 复制配置文件
cp config/config.yaml.example config/config.yaml

# 2. 编辑配置文件，设置企业微信key等参数
# 编辑 config/config.yaml，修改以下配置：
#   - qywechatKey: 你的企业微信机器人key
#   - useStorage: sqlite  # 默认使用 SQLite，无需 Redis 服务
#     或
#   - useStorage: redis  # 使用 Redis，需要配置 redisServer: redis（docker-compose服务名）

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker-compose logs -f webhook

# 5. 查看服务状态
docker-compose ps

# 6. 停止服务
docker-compose down

# 7. 重启服务
docker-compose restart webhook
```

**Docker 配置说明**：
- 配置文件路径：`config/config.yaml`（需要从 `config/config.yaml.example` 复制并修改）
- **存储后端**：
  - 默认使用 SQLite（`useStorage: sqlite`），无需 Redis 服务，数据保存在 `logs/alerts.db`
  - 如需使用 Redis，设置 `useStorage: redis`，并在配置文件中设置 `redisServer: redis`（docker-compose 中的服务名）
- 日志文件：挂载到 `./logs` 目录
- 端口映射：`9095:9095`（Webhook服务）
- 如果使用 Redis：`6379:6379`（Redis服务），数据保存在 Docker volume `redis-data` 中

## 配置说明

编辑 `config/config.yaml` 配置文件（可复制 `config/config.yaml.example` 并重命名）：

```yaml
# 企业微信机器人配置（可选）
# 配置企业微信的key，如不配置也可以在请求接口的时候通过 ?key=xxxx 来指定
qywechatKey: your_webhook_key_here

# Webhook基础URL（可选）
# 不配置则使用默认官方地址: https://qyapi.weixin.qq.com/cgi-bin/webhook/send
# 如果使用正向代理，可以配置代理地址，例如: https://proxy.example.com:58443/cgi-bin/webhook/send
qywechatBaseUrl: https://qyapi.weixin.qq.com/cgi-bin/webhook/send

# 飞书机器人配置（可选）
# 配置飞书的token，如不配置也可以在请求接口的时候通过 ?key=xxxx 来指定
feishuKey: your_webhook_token_here

# Webhook基础URL（可选）
# 不配置则使用默认官方地址: https://open.feishu.cn/open-apis/bot/v2/hook
# 如果使用正向代理，可以配置代理地址，例如: https://proxy.example.com:58443/open-apis/bot/v2/hook
feishuBaseUrl: https://open.feishu.cn/open-apis/bot/v2/hook

# 钉钉机器人配置（可选）
# 配置钉钉的access_token，如不配置也可以在请求接口的时候通过 ?key=xxxx 来指定
dingtalkKey: your_access_token_here

# Webhook基础URL（可选）
# 不配置则使用默认官方地址: https://oapi.dingtalk.com/robot/send
# 如果使用正向代理，可以配置代理地址，例如: https://proxy.example.com:58443/robot/send
dingtalkBaseUrl: https://oapi.dingtalk.com/robot/send

# 存储配置
useStorage: sqlite  # 存储类型，支持 "redis" 或 "sqlite"，默认为 "sqlite"

# Redis配置（当 useStorage=redis 时生效）
redisServer: 127.0.0.1  # Docker部署时改为 redis
redisPort: 6379
redisPassword:  # 如果Redis设置了密码，请填写
redisUsername:  # Redis 6.0+ ACL用户名（可选），如果Redis使用ACL且不是default用户，需要配置

# SQLite配置（当 useStorage=sqlite 时生效）
sqliteDbPath: logs/alerts.db  # SQLite 数据库路径，默认为 logs/alerts.db

# 历史记录保留配置（仅当 useStorage=sqlite 时生效）
historyRetention:
  days: 30  # 保留天数，默认 30 天；设置为 0 表示不保留历史记录（删除所有已恢复的记录）
  cleanupTime: "05:00"  # 清理时间（24小时制），默认 05:00（凌晨5点）
  timezone: "Asia/Shanghai"  # 时区，默认 Asia/Shanghai

# 日志配置
logFileDir: logs  # 日志目录，为空则默认为logs目录
logFilePath: alertmanager-webhook.log  # 日志文件名，为空则默认为alertmanager-webhook.log

# 服务监听配置
port: 9095
host: 0.0.0.0
```

## 使用方法

### 1. 启动服务

**方式一：Docker Compose（推荐）**

```bash
# 启动服务（默认使用 SQLite，无需 Redis）
docker-compose up -d

# 如需使用 Redis，确保 docker-compose.yml 中包含 Redis 服务
# 启动所有服务（包括Redis）
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f webhook

# 停止服务
docker-compose down

# 重启服务
docker-compose restart webhook
```

**方式二：使用服务管理脚本（Linux/Mac）**

```bash
bash service.sh start        # 启动服务
bash service.sh stop         # 停止服务
bash service.sh restart      # 重启服务
bash service.sh status       # 查看服务状态
bash service.sh help         # 查看帮助信息
```

**方式三：直接使用Python**

```bash
python src/app.py                          # 使用默认配置文件路径
python src/app.py -c config/config.yaml    # 指定配置文件路径
```

### 2. 在Alertmanager中配置webhook

编辑 `alertmanager.yml`：

#### 企业微信配置

**方式一：使用URL参数传递key（推荐）**

```yaml
receivers:
  - name: 'default-receiver'
    webhook_configs:
      - url: 'http://127.0.0.1:9095/qywechat?key=xxx'
        send_resolved: true
```

**方式二：使用配置文件中的key**

```yaml
receivers:
  - name: webhook
    webhook_configs:
      - url: 'http://127.0.0.1:9095/qywechat'
        send_resolved: true
```

> **企业微信优先级说明**：
> 1. URL参数 `key`（使用配置文件中的baseUrl或默认baseUrl，支持代理）
> 2. 配置文件中的 `qywechatKey`（最低优先级）

#### 飞书配置

**方式一：使用URL参数传递key（推荐）**

```yaml
receivers:
  - name: 'feishu-receiver'
    webhook_configs:
      - url: 'http://127.0.0.1:9095/feishu?key=xxx'
        send_resolved: true
```

**方式二：使用配置文件中的key**

```yaml
receivers:
  - name: feishu-receiver
    webhook_configs:
      - url: 'http://127.0.0.1:9095/feishu'
        send_resolved: true
```

> **飞书优先级说明**：
> 1. URL参数 `key`（使用配置文件中的baseUrl或默认baseUrl，支持代理）
> 2. 配置文件中的 `feishuKey`（最低优先级）

#### 钉钉配置

**方式一：使用URL参数传递key（推荐）**

```yaml
receivers:
  - name: 'dingtalk-receiver'
    webhook_configs:
      - url: 'http://127.0.0.1:9095/dingtalk?key=xxx'
        send_resolved: true
```

**方式二：使用配置文件中的key**

```yaml
receivers:
  - name: dingtalk-receiver
    webhook_configs:
      - url: 'http://127.0.0.1:9095/dingtalk'
        send_resolved: true
```

> **钉钉优先级说明**：
> 1. URL参数 `key`（使用配置文件中的baseUrl或默认baseUrl，支持代理）
> 2. 配置文件中的 `dingtalkKey`（最低优先级）

### 3. 测试接口

使用curl测试：

**企业微信（使用key）：**
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
}' "http://127.0.0.1:9095/qywechat?key=your_key_here"
```

**飞书（使用key）：**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
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
}' "http://127.0.0.1:9095/feishu?key=your_token_here"
```

**钉钉（使用key）：**
```bash
curl -X POST -H "Content-Type: application/json" -d '{
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
}' "http://127.0.0.1:9095/dingtalk?key=your_access_token_here"
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
│   ├── sender.py       # 消息发送模块
│   ├── storage.py      # 存储后端（Redis/SQLite）
│   └── cleanup_scheduler.py  # 历史记录清理调度器
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
├── Dockerfile          # Docker镜像构建文件
├── docker-compose.yml  # Docker Compose编排文件
├── .dockerignore       # Docker构建忽略文件
├── service.sh          # 服务管理脚本（支持start/stop/restart/status）
└── README.md           # 说明文档
```

## 注意事项

1. **存储后端配置**：
   - **SQLite（默认，推荐）**：
     - 无需额外服务，开箱即用
     - 数据文件保存在 `logs/alerts.db`（默认路径）
     - 支持历史记录保留和自动清理（每天凌晨5点执行）
     - 保留天数设置为 0 表示不保留历史记录
   - **Redis（可选）**：
     - Docker部署：Redis会自动启动，配置文件中 `redisServer` 应设置为 `redis`
     - 本地部署：需要先启动Redis服务，配置文件中 `redisServer` 设置为 `127.0.0.1`
     - **Redis认证**：
       - 如果Redis只设置了密码（requirepass），只需配置 `redisPassword`
       - 如果Redis使用了ACL（Redis 6.0+），需要同时配置 `redisUsername` 和 `redisPassword`
       - 如果Redis使用ACL的default用户，可以不配置 `redisUsername`，只配置 `redisPassword` 即可
   - **存储类型验证**：如果配置了无效的存储类型，会自动设置为 `sqlite` 并记录警告日志
2. **机器人配置**：
   - 企业微信：需要配置 `qywechatKey` 和 `qywechatBaseUrl`（可选），或通过URL参数传递 `key`
   - 飞书：需要配置 `feishuKey` 和 `feishuBaseUrl`（可选），或通过URL参数传递 `key`
   - 钉钉：需要配置 `dingtalkKey` 和 `dingtalkBaseUrl`（可选），或通过URL参数传递 `key`
   - 所有机器人统一使用key方式，baseUrl支持代理场景
3. 配置文件需要放在 `config/` 目录下，或通过 `-c` 参数指定路径
4. 模板文件位于 `template/` 目录下
5. 日志文件默认写入 `logs/` 目录，程序会自动创建该目录
6. **Docker部署**：需要先创建 `config/config.yaml` 配置文件（从 `config/config.yaml.example` 复制）
7. **消息格式**：不同机器人平台对Markdown格式的支持略有差异，程序会自动适配
8. **历史记录清理**：SQLite 模式下，清理任务会在每天指定时间（默认凌晨5点）自动执行，清理过期的历史记录

## 健康检查

```bash
curl http://127.0.0.1:9095/health
```

## 测试

### 使用Python测试脚本

```bash
# 测试企业微信触发告警（使用配置文件中的key）
python tests/test_webhook.py qywechat firing

# 测试企业微信触发告警（使用指定key）
python tests/test_webhook.py qywechat firing your_key_here

# 测试飞书告警恢复（使用指定token）
python tests/test_webhook.py feishu resolved your_token_here

# 测试钉钉触发告警（使用指定access_token）
python tests/test_webhook.py dingtalk firing your_access_token_here
```

### 使用Shell测试脚本

```bash
# 测试企业微信触发告警（使用配置文件中的key）
bash tests/test_webhook.sh qywechat firing

# 测试企业微信触发告警（使用指定key）
bash tests/test_webhook.sh qywechat firing your_key_here

# 测试飞书告警恢复（使用指定token）
bash tests/test_webhook.sh feishu resolved your_token_here

# 测试钉钉触发告警（使用指定access_token）
bash tests/test_webhook.sh dingtalk firing your_access_token_here

# 查看帮助信息
bash tests/test_webhook.sh --help
```

