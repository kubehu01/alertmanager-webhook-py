#!/bin/bash
# 测试脚本：模拟Alertmanager发送告警通知
# 支持企业微信、飞书、钉钉

# 默认配置
ROBOT_TYPE="qywechat"  # 默认机器人类型：qywechat/feishu/dingtalk
KEY=""                 # key（可选，不提供则使用配置文件）
TEST_TYPE="firing"      # 默认测试类型

# 各平台消息长度限制（字符数）
QYWECHAT_MAX_LENGTH=4096
FEISHU_MAX_LENGTH=8000
DINGTALK_MAX_LENGTH=5000

# 解析参数
parse_args() {
    # 检查是否请求帮助
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        show_help
        exit 0
    fi
    
    # 解析参数
    while [[ $# -gt 0 ]]; do
        case "$1" in
            qywechat|feishu|dingtalk)
                ROBOT_TYPE="$1"
                shift
                ;;
            firing|resolved|f|r|long|length)
                TEST_TYPE="$1"
                shift
                ;;
            *)
                # 其他参数作为key
                KEY="$1"
                shift
                ;;
        esac
    done
}

# 生成ISO格式的时间戳（UTC）
get_iso_timestamp() {
    # 尝试不同的date命令格式
    if date -u +"%Y-%m-%dT%H:%M:%S.000Z" >/dev/null 2>&1; then
        # GNU date (Linux)
        date -u +"%Y-%m-%dT%H:%M:%S.000Z"
    elif date -u +"%Y-%m-%dT%H:%M:%SZ" >/dev/null 2>&1; then
        # BSD date (Mac)
        date -u +"%Y-%m-%dT%H:%M:%SZ"
    else
        # 备用方案：使用Python生成（如果可用）
        python3 -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())" 2>/dev/null || \
        python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat())" 2>/dev/null || \
        echo "$(date -u +"%Y-%m-%dT%H:%M:%S")Z"
    fi
}

TIMESTAMP=$(get_iso_timestamp)

# 测试触发告警
test_firing_alert() {
    local base_url="http://127.0.0.1:9095/${ROBOT_TYPE}"
    local status="firing"
    
    echo "测试触发告警..."
    echo "机器人类型: ${ROBOT_TYPE}"
    if [[ -n "$KEY" ]]; then
        echo "Key: ${KEY}"
        local full_url="${base_url}?key=${KEY}"
        echo "请求URL: ${full_url}"
    else
        echo "使用配置文件中的key"
        local full_url="${base_url}"
        echo "请求URL: ${full_url}"
    fi
    echo ""
    
    # 构建curl命令
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "{
            \"alerts\": [
                {
                    \"status\": \"${status}\",
                    \"labels\": {
                        \"alertname\": \"机器宕机监测\",
                        \"instance\": \"10.180.48.2\",
                        \"job\": \"node_exporter\",
                        \"serverity\": \"warning\"
                    },
                    \"annotations\": {
                        \"description\": \"机器:10.180.48.2 所属 job:node_exporter 宕机超过1分钟，请检查！\",
                        \"summary\": \"机器发生宕机\"
                    },
                    \"startsAt\": \"${TIMESTAMP}\",
                    \"fingerprint\": \"02f13394997e5211\"
                }
            ]
        }" \
        "$full_url"
    
    echo ""
    echo ""
}

# 测试超长消息（触发告警）
test_long_firing_alert() {
    local base_url="http://127.0.0.1:9095/${ROBOT_TYPE}"
    local status="firing"
    
    # 根据机器人类型确定目标长度（超过限制）
    local target_length=0
    case "$ROBOT_TYPE" in
        qywechat)
            target_length=$((QYWECHAT_MAX_LENGTH + 1000))  # 超过4096，设置为5096
            ;;
        feishu)
            target_length=$((FEISHU_MAX_LENGTH + 1000))    # 超过8000，设置为9000
            ;;
        dingtalk)
            target_length=$((DINGTALK_MAX_LENGTH + 1000))  # 超过5000，设置为6000
            ;;
    esac
    
    echo "测试超长消息触发告警..."
    echo "机器人类型: ${ROBOT_TYPE}"
    case "$ROBOT_TYPE" in
        qywechat)
            echo "描述长度: 约 5596 字符（超过企业微信限制 4096 字符）"
            echo "渲染后预计: 约 5900 字符，将被分割为 2 条消息"
            ;;
        feishu)
            echo "描述长度: 约 9500 字符（超过飞书限制 8000 字符）"
            echo "渲染后预计: 约 9800 字符，将被分割为 2 条消息"
            ;;
        dingtalk)
            echo "描述长度: 约 6500 字符（超过钉钉限制 5000 字符）"
            echo "渲染后预计: 约 6800 字符，将被分割为 2 条消息"
            ;;
    esac
    echo "预期行为: 消息将被自动分割为多条发送，每条消息会显示序号 (1/2), (2/2) 等"
    if [[ -n "$KEY" ]]; then
        echo "Key: ${KEY}"
        local full_url="${base_url}?key=${KEY}"
        echo "请求URL: ${full_url}"
    else
        echo "使用配置文件中的key"
        local full_url="${base_url}"
        echo "请求URL: ${full_url}"
    fi
    echo ""
    
    # 使用Python生成JSON数据（更可靠的方法）
    # 注意：需要考虑模板渲染后的实际长度
    # 模板会添加标题、项目、级别、次数、时间等信息（约200-300字符）
    # 企业微信还会添加标题行（约30字符）
    # 所以description需要生成足够长的内容，确保最终消息超过限制
    local json_data=$(python3 <<EOF
import json
from datetime import datetime, timezone

# 根据机器人类型确定目标长度（超过限制）
# 考虑模板固定内容约300字符，所以description需要生成：限制长度 + 1500字符
robot_type = "${ROBOT_TYPE}"
if robot_type == "qywechat":
    target_length = 4096 + 1500  # 5596字符，渲染后约5900字符
elif robot_type == "feishu":
    target_length = 8000 + 1500  # 9500字符，渲染后约9800字符
elif robot_type == "dingtalk":
    target_length = 5000 + 1500  # 6500字符，渲染后约6800字符
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
detail_block = "\\n".join(detail_lines)
repeat_count = target_length // len(detail_block) + 1

# 生成超长描述
long_description = base_text + "\\n\\n"
for i in range(repeat_count):
    long_description += f"--- 详细信息块 {i+1} ---\\n"
    long_description += detail_block
    long_description += f"\\n详细信息块 {i+1} 结束\\n\\n"
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
            "status": "${status}",
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

print(json.dumps(data, ensure_ascii=False))
EOF
)
    
    if [[ -z "$json_data" ]]; then
        echo "错误: 无法生成JSON数据，请确保已安装Python3"
        return 1
    fi
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "$json_data" \
        "$full_url"
    
    echo ""
    echo ""
}

# 测试告警恢复
test_resolved_alert() {
    local base_url="http://127.0.0.1:9095/${ROBOT_TYPE}"
    local status="resolved"
    
    echo "测试告警恢复..."
    echo "机器人类型: ${ROBOT_TYPE}"
    if [[ -n "$KEY" ]]; then
        echo "Key: ${KEY}"
        local full_url="${base_url}?key=${KEY}"
        echo "请求URL: ${full_url}"
    else
        echo "使用配置文件中的key"
        local full_url="${base_url}"
        echo "请求URL: ${full_url}"
    fi
    echo ""
    
    # 构建curl命令
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "{
            \"alerts\": [
                {
                    \"status\": \"${status}\",
                    \"labels\": {
                        \"alertname\": \"机器宕机监测\",
                        \"instance\": \"10.180.48.2\",
                        \"job\": \"node_exporter\",
                        \"serverity\": \"warning\"
                    },
                    \"annotations\": {
                        \"description\": \"机器:10.180.48.2 所属 job:node_exporter 宕机超过1分钟，请检查！\",
                        \"summary\": \"机器发生宕机\"
                    },
                    \"startsAt\": \"${TIMESTAMP}\",
                    \"endsAt\": \"${TIMESTAMP}\",
                    \"fingerprint\": \"02f13394997e5211\"
                }
            ]
        }" \
        "$full_url"
    
    echo ""
    echo ""
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [robot_type] [test_type] [key]"
    echo ""
    echo "参数:"
    echo "  robot_type  机器人类型: qywechat（企业微信）、feishu（飞书）、dingtalk（钉钉），默认为qywechat"
    echo "  test_type   测试类型: firing（触发告警）、resolved（告警恢复）、long（超长消息测试），默认为firing"
    echo "  key         机器人key/token（可选，不提供则使用配置文件中的key）"
    echo ""
    echo "示例:"
    echo "  $0                                          # 测试企业微信触发告警，使用配置文件"
    echo "  $0 qywechat firing                          # 测试企业微信触发告警"
    echo "  $0 feishu resolved                          # 测试飞书告警恢复"
    echo "  $0 dingtalk firing                          # 测试钉钉触发告警"
    echo "  $0 qywechat long                            # 测试企业微信超长消息（自动分割）"
    echo "  $0 feishu long 'your_token_here'           # 测试飞书超长消息，使用指定token"
    echo "  $0 dingtalk long 'your_access_token'       # 测试钉钉超长消息，使用指定access_token"
    echo "  $0 qywechat firing 'your_key_here'         # 测试企业微信，使用指定key"
    echo ""
}

# 主逻辑
main() {
    # 解析参数
    parse_args "$@"
    
    # 根据测试类型执行相应测试
    case "$TEST_TYPE" in
        firing|f)
            test_firing_alert
            ;;
        resolved|r)
            test_resolved_alert
            ;;
        long|length)
            test_long_firing_alert
            ;;
        *)
            echo "错误: 未知的测试类型 '$TEST_TYPE'"
            echo "支持的测试类型: firing, resolved, long"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"


