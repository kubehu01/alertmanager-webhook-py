#!/bin/bash
# 测试脚本：模拟Alertmanager发送告警通知
# 支持企业微信、飞书、钉钉

# 默认配置
ROBOT_TYPE="qywechat"  # 默认机器人类型：qywechat/feishu/dingtalk
KEY=""                 # key（可选，不提供则使用配置文件）
TEST_TYPE="firing"      # 默认测试类型

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
            firing|resolved|f|r)
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
    echo "  test_type   测试类型: firing（触发告警）或 resolved（告警恢复），默认为firing"
    echo "  key         机器人key/token（可选，不提供则使用配置文件中的key）"
    echo ""
    echo "示例:"
    echo "  $0                                          # 测试企业微信触发告警，使用配置文件"
    echo "  $0 qywechat firing                          # 测试企业微信触发告警"
    echo "  $0 feishu resolved                          # 测试飞书告警恢复"
    echo "  $0 dingtalk firing                          # 测试钉钉触发告警"
    echo "  $0 qywechat firing 'your_key_here'          # 测试企业微信，使用指定key"
    echo "  $0 feishu firing 'your_token_here'         # 测试飞书，使用指定token"
    echo "  $0 dingtalk firing 'your_access_token'     # 测试钉钉，使用指定access_token"
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
        *)
            echo "错误: 未知的测试类型 '$TEST_TYPE'"
            echo "支持的测试类型: firing, resolved"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"

