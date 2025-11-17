#!/bin/bash
# Alertmanager Webhook 服务管理脚本

# 配置
APP_NAME="Alertmanager Webhook"
APP_SCRIPT="src/app.py"
CONFIG_FILE="config/config.yaml"
PID_FILE="alertmanager-webhook.pid"
LOG_FILE="logs/alertmanager-webhook.log"

# 获取PID
get_pid() {
    if [[ -f "$PID_FILE" ]]; then
        cat "$PID_FILE" 2>/dev/null
    fi
}

# 检查服务是否运行
is_running() {
    local pid=$(get_pid)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

# 启动服务
start_service() {
    if is_running; then
        local pid=$(get_pid)
        echo "$APP_NAME 已经在运行中，PID: $pid"
        return 1
    fi
    
    echo "正在启动 $APP_NAME..."
    
    # 检查Python是否可用
    if ! command -v python3 >/dev/null 2>&1; then
        echo "错误: 未找到 python3 命令"
        return 1
    fi
    
    # 检查应用脚本是否存在
    if [[ ! -f "$APP_SCRIPT" ]]; then
        echo "错误: 应用脚本不存在: $APP_SCRIPT"
        return 1
    fi
    
    # 检查配置文件是否存在
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "警告: 配置文件不存在: $CONFIG_FILE，将使用默认配置"
    fi
    
    # 确保日志目录存在
    local log_dir=$(dirname "$LOG_FILE")
    if [[ -n "$log_dir" ]] && [[ ! -d "$log_dir" ]]; then
        mkdir -p "$log_dir"
    fi
    
    # 启动服务
    nohup python3 "$APP_SCRIPT" -c "$CONFIG_FILE" >> "$LOG_FILE" 2>&1 &
    local pid=$!
    
    # 等待一下，检查进程是否成功启动
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
        echo "$pid" > "$PID_FILE"
        echo "$APP_NAME 启动成功，PID: $pid"
        echo "日志文件: $LOG_FILE"
        return 0
    else
        echo "错误: $APP_NAME 启动失败"
        rm -f "$PID_FILE"
        return 1
    fi
}

# 停止服务
stop_service() {
    if ! is_running; then
        echo "$APP_NAME 未运行"
        return 1
    fi
    
    local pid=$(get_pid)
    echo "正在停止 $APP_NAME (PID: $pid)..."
    
    # 尝试优雅停止
    kill "$pid" 2>/dev/null
    
    # 等待进程结束
    local count=0
    while kill -0 "$pid" 2>/dev/null && [[ $count -lt 10 ]]; do
        sleep 1
        count=$((count + 1))
    done
    
    # 如果还在运行，强制杀死
    if kill -0 "$pid" 2>/dev/null; then
        echo "强制停止进程..."
        kill -9 "$pid" 2>/dev/null
        sleep 1
    fi
    
    # 清理PID文件
    if ! kill -0 "$pid" 2>/dev/null; then
        rm -f "$PID_FILE"
        echo "$APP_NAME 已停止"
        return 0
    else
        echo "错误: 无法停止 $APP_NAME"
        return 1
    fi
}

# 重启服务
restart_service() {
    echo "正在重启 $APP_NAME..."
    stop_service
    sleep 1
    start_service
}

# 查看服务状态
status_service() {
    if is_running; then
        local pid=$(get_pid)
        echo "$APP_NAME 正在运行，PID: $pid"
        
        # 显示进程信息
        if command -v ps >/dev/null 2>&1; then
            ps -p "$pid" -o pid,ppid,cmd,etime 2>/dev/null | tail -n +2
        fi
        return 0
    else
        echo "$APP_NAME 未运行"
        return 1
    fi
}

# 显示帮助信息
show_help() {
    echo "用法: $0 {start|stop|restart|status|help}"
    echo ""
    echo "命令:"
    echo "  start    启动服务"
    echo "  stop     停止服务"
    echo "  restart  重启服务"
    echo "  status   查看服务状态"
    echo "  help     显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 start     # 启动服务"
    echo "  $0 stop      # 停止服务"
    echo "  $0 restart   # 重启服务"
    echo "  $0 status    # 查看状态"
    echo ""
}

# 主逻辑
main() {
    case "${1:-help}" in
        start)
            start_service
            ;;
        stop)
            stop_service
            ;;
        restart)
            restart_service
            ;;
        status)
            status_service
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "错误: 未知命令 '$1'"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# 执行主函数
main "$@"
