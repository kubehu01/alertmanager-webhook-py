#!/bin/bash
# 测试脚本：模拟Alertmanager发送告警通知

# 默认配置
WEBHOOK_URL="http://127.0.0.1:9095/qywechat"
KEY="xxxx"  # 默认key
TEST_TYPE="firing"  # 默认测试类型

# 解析参数（在main函数中处理，这里先定义）
parse_args() {
    # 检查是否请求帮助
    if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]]; then
        show_help
        exit 0
    fi
    
    # 如果第一个参数是firing/resolved，则作为test_type；否则作为key
    if [[ "$1" == "firing" ]] || [[ "$1" == "resolved" ]] || [[ "$1" == "f" ]] || [[ "$1" == "r" ]]; then
        TEST_TYPE="$1"
    elif [[ -n "$1" ]]; then
        KEY="$1"
        # 如果第二个参数存在，作为test_type
        if [[ -n "$2" ]]; then
            TEST_TYPE="$2"
        fi
    fi
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
    echo "测试触发告警..."
    echo "URL: ${WEBHOOK_URL}?key=${KEY}"
    echo ""
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "{
            \"alerts\": [
                {
                    \"status\": \"firing\",
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
        "${WEBHOOK_URL}?key=${KEY}"
    
    echo ""
    echo ""
}

# 测试告警恢复
test_resolved_alert() {
    echo "测试告警恢复..."
    echo "URL: ${WEBHOOK_URL}?key=${KEY}"
    echo ""
    
    curl -X POST \
        -H "Content-Type: application/json" \
        -d "{
            \"alerts\": [
                {
                    \"status\": \"resolved\",
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
        "${WEBHOOK_URL}?key=${KEY}"
    
    echo ""
    echo ""
}

# 显示帮助信息
show_help() {
    echo "用法: $0 [key] [test_type]"
    echo ""
    echo "参数:"
    echo "  key       企业微信机器人key（可选，默认为xxxx）"
    echo "  test_type 测试类型: firing（触发告警）或 resolved（告警恢复），默认为firing"
    echo ""
    echo "示例:"
    echo "  $0                                    # 测试触发告警，使用默认key"
    echo "  $0 your_key_here                      # 测试触发告警，使用指定key"
    echo "  $0 your_key_here resolved            # 测试告警恢复，使用指定key"
    echo "  $0 resolved                           # 测试告警恢复，使用默认key"
    echo "  $0 firing                             # 测试触发告警，使用默认key"
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

