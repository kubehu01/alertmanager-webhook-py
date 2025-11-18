"""
Alertmanager Webhook主程序
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
import traceback

from config import Config
from transformer import Transformer
from sender import QyWeChatSender, FeishuSender, DingTalkSender
from storage import RedisStorageBackend, SQLiteStorageBackend
from cleanup_scheduler import CleanupScheduler
import threading

# 创建Flask应用
app = Flask(__name__)

# 全局变量
config = None
transformer = None
qywechat_sender = None  # 企业微信发送器（用于默认配置）
feishu_sender = None    # 飞书发送器（用于默认配置）
dingtalk_sender = None  # 钉钉发送器（用于默认配置）

# 日志配置标志（使用模块级变量，防止重复配置）
_logging_setup_done = False

def setup_logging(log_file_path: str):
    """配置日志"""
    global _logging_setup_done
    
    # 如果已经配置过，直接返回
    if _logging_setup_done:
        return
    
    # 获取根日志器
    root_logger = logging.getLogger()
    
    # 创建日志目录（使用绝对路径）
    abs_log_file_path = os.path.abspath(log_file_path)
    log_dir = os.path.dirname(abs_log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志格式
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 完全清除所有已有的handler，确保不会重复
    for handler in root_logger.handlers[:]:
        try:
            handler.close()
        except:
            pass
        root_logger.removeHandler(handler)
    root_logger.handlers = []
    
    # 创建文件handler
    file_handler = RotatingFileHandler(
        abs_log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    
    # 只添加文件handler，不添加控制台handler，避免重复输出
    root_logger.addHandler(file_handler)
    
    # 配置根日志器
    root_logger.setLevel(logging.INFO)
    
    # 禁用传播，避免日志向上传播导致重复输出
    root_logger.propagate = False
    
    # 设置第三方库日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    # werkzeug - Flask 使用的 WSGI 工具库，会输出 HTTP 请求日志（如 GET /qywechat HTTP/1.1 200）
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    # urllib3 - requests 底层使用的 HTTP 库，会输出网络请求的详细日志（如连接、请求头等）
    
    # 标记已配置
    _logging_setup_done = True


def _handle_webhook_request(robot_type: str, sender_class, default_sender, robot_name: str, error_message: str):
    """
    处理webhook请求的通用函数
    
    Args:
        robot_type: 机器人类型（qywechat/feishu/dingtalk）
        sender_class: 发送器类
        default_sender: 默认发送器实例（从配置文件加载）
        robot_name: 机器人名称（用于日志）
        error_message: 错误提示信息
    """
    try:
        # 获取请求数据
        notification_data = request.get_json()
        if not notification_data:
            return jsonify({"error": "请求数据为空"}), 400
        
        # 从URL参数获取key
        url_key = request.args.get('key')
        
        # 统计告警信息
        alerts = notification_data.get("alerts", [])
        alert_count = len(alerts)
        firing_count = sum(1 for a in alerts if a.get("status") == "firing")
        resolved_count = sum(1 for a in alerts if a.get("status") == "resolved")
        top_status = notification_data.get("status", "mixed" if alert_count > 0 else "empty")
        
        # 创建或获取sender
        sender = None
        log_message = ""
        
        # 获取配置文件中的baseUrl（如果存在）
        if robot_type == "qywechat":
            config_base_url = config.qywechat_base_url if config else "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"
        elif robot_type == "feishu":
            config_base_url = config.feishu_base_url if config else "https://open.feishu.cn/open-apis/bot/v2/hook"
        elif robot_type == "dingtalk":
            config_base_url = config.dingtalk_base_url if config else "https://oapi.dingtalk.com/robot/send"
        else:
            config_base_url = ""
        
        if url_key:
            # 优先级1: URL参数中的key（使用配置文件中的baseUrl或默认）
            sender = sender_class(key=url_key, webhook_base_url=config_base_url)
            log_message = f"收到告警通知 ({robot_name}, 使用URL参数key: {url_key})"
        else:
            # 优先级2: 使用配置文件中的key
            if default_sender is None:
                return jsonify({"error": error_message}), 400
            sender = default_sender
            log_message = f"收到告警通知 ({robot_name}, 使用配置文件)"
        
        logging.info(f"{log_message}: 总计 {alert_count} 个告警 "
                    f"(firing: {firing_count}, resolved: {resolved_count}, 顶层status: {top_status})")
        
        # 转换消息
        firing_message, resolved_message = transformer.transform_to_markdown(notification_data, robot_type=robot_type)
        
        # 发送消息并记录发送历史
        alerts = notification_data.get("alerts", [])
        
        # 发送 firing 消息
        if firing_message:
            send_success = sender.send_firing(firing_message)
            error_message = None if send_success else "消息发送失败"
            
            # 为每个 firing 告警记录发送历史
            for alert_data in alerts:
                if alert_data.get("status") == "firing":
                    fingerprint = alert_data.get("fingerprint", "")
                    labels = alert_data.get("labels", {})
                    annotations = alert_data.get("annotations", {})
                    
                    # 获取告警信息
                    alertname = labels.get("alertname")
                    summary = annotations.get("summary")
                    instance = labels.get("instance")
                    severity = labels.get("severity")
                    
                    # 获取告警次数（从存储中获取，不增加计数）
                    # 注意：计数已在 transformer 中增加，这里只获取用于记录
                    alert_count = None
                    if fingerprint and transformer.storage:
                        try:
                            alert_count = transformer.storage.get_alert_count(fingerprint)
                        except:
                            pass
                    
                    # 记录发送历史
                    if transformer.storage and fingerprint:
                        try:
                            # 获取 webhook URL
                            webhook_url = getattr(sender, 'webhook_url', None)
                            transformer.storage.record_send_history(
                                fingerprint=fingerprint,
                                platform=robot_type,
                                alert_status="firing",
                                send_success=send_success,
                                error_message=error_message,
                                alert_count=alert_count,
                                alertname=alertname,
                                summary=summary,
                                instance=instance,
                                severity=severity,
                                webhook_url=webhook_url
                            )
                        except Exception as e:
                            logging.warning(f"记录发送历史失败: {e}")
        
        # 发送 resolved 消息
        if resolved_message:
            send_success = sender.send_resolved(resolved_message)
            error_message = None if send_success else "消息发送失败"
            
            # 为每个 resolved 告警记录发送历史
            for alert_data in alerts:
                if alert_data.get("status") == "resolved":
                    fingerprint = alert_data.get("fingerprint", "")
                    labels = alert_data.get("labels", {})
                    annotations = alert_data.get("annotations", {})
                    
                    # 获取告警信息
                    alertname = labels.get("alertname")
                    summary = annotations.get("summary")
                    instance = labels.get("instance")
                    severity = labels.get("severity")
                    
                    # 记录发送历史
                    if transformer.storage and fingerprint:
                        try:
                            # 获取 webhook URL
                            webhook_url = getattr(sender, 'webhook_url', None)
                            transformer.storage.record_send_history(
                                fingerprint=fingerprint,
                                platform=robot_type,
                                alert_status="resolved",
                                send_success=send_success,
                                error_message=error_message,
                                alert_count=None,  # resolved 状态不需要 count
                                alertname=alertname,
                                summary=summary,
                                instance=instance,
                                severity=severity,
                                webhook_url=webhook_url
                            )
                        except Exception as e:
                            logging.warning(f"记录发送历史失败: {e}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logging.error(f"处理请求时发生错误: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/qywechat', methods=['POST'])
def qywechat_webhook():
    """企业微信webhook接口"""
    return _handle_webhook_request(
        robot_type="qywechat",
        sender_class=QyWeChatSender,
        default_sender=qywechat_sender,
        robot_name="企业微信",
        error_message="企业微信key未配置，请在URL参数中提供key或在配置文件中配置qywechatKey"
    )


@app.route('/feishu', methods=['POST'])
def feishu_webhook():
    """飞书webhook接口"""
    return _handle_webhook_request(
        robot_type="feishu",
        sender_class=FeishuSender,
        default_sender=feishu_sender,
        robot_name="飞书",
        error_message="飞书key未配置，请在URL参数中提供key或在配置文件中配置feishuKey"
    )


@app.route('/dingtalk', methods=['POST'])
def dingtalk_webhook():
    """钉钉webhook接口"""
    return _handle_webhook_request(
        robot_type="dingtalk",
        sender_class=DingTalkSender,
        default_sender=dingtalk_sender,
        robot_name="钉钉",
        error_message="钉钉key未配置，请在URL参数中提供key或在配置文件中配置dingtalkKey"
    )

@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    from datetime import datetime
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200


def main():
    """主函数"""
    global config, transformer, qywechat_sender, feishu_sender, dingtalk_sender
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='Alertmanager Webhook for 企业微信')
    parser.add_argument('-c', '--config', type=str, default='config/config.yaml',
                        help='配置文件路径 (默认: config/config.yaml)')
    args = parser.parse_args()
    
    # 加载配置
    try:
        config = Config(args.config)
    except Exception as e:
        print(f"加载配置失败: {e}")
        sys.exit(1)
    
    # 设置日志
    setup_logging(config.log_file_path)
    logging.info("=" * 50)
    logging.info("Alertmanager Webhook 启动")
    logging.info(f"配置文件: {args.config}")
    logging.info(f"监听地址: {config.host}:{config.port}")
    logging.info(f"企业微信配置: {'Key已配置' if config.qywechat_key else '未配置'}")
    logging.info(f"飞书配置: {'Key已配置' if config.feishu_key else '未配置'}")
    logging.info(f"钉钉配置: {'Key已配置' if config.dingtalk_key else '未配置'}")
    logging.info("=" * 50)
    
    # 初始化存储后端
    storage_backend = None
    if config.use_storage == "redis":
        try:
            storage_backend = RedisStorageBackend(
                redis_server=config.redis_server,
                redis_port=config.redis_port,
                redis_password=config.redis_password,
                redis_username=config.redis_username
            )
            logging.info("使用 Redis 存储后端")
        except Exception as e:
            logging.error(f"Redis 初始化失败: {e}，回退到 SQLite")
            config.use_storage = "sqlite"
    
    if config.use_storage == "sqlite":
        # 使用 SQLite
        try:
            storage_backend = SQLiteStorageBackend(db_path=config.sqlite_db_path)
            logging.info(f"使用 SQLite 存储后端: {config.sqlite_db_path}")
        except Exception as e:
            logging.error(f"SQLite 初始化失败: {e}")
            sys.exit(1)
    
    # 确保存储后端已初始化
    if storage_backend is None:
        logging.error("存储后端初始化失败，无法启动服务")
        sys.exit(1)
    
    # 初始化转换器
    # 获取模板路径（相对于项目根目录）
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    template_path = os.path.join(base_dir, "template", "alert.tmpl")
    transformer = Transformer(
        storage_backend=storage_backend,
        template_path=template_path
    )
    
    # 如果使用 SQLite，启动清理调度器
    cleanup_thread = None
    if config.use_storage == "sqlite":
        try:
            cleanup_scheduler = CleanupScheduler(
                storage_backend=storage_backend,
                retention_days=config.history_retention_days,
                cleanup_time=config.history_cleanup_time,
                timezone_str=config.history_timezone
            )
            
            # 启动后台线程
            cleanup_thread = threading.Thread(
                target=cleanup_scheduler.run,
                daemon=True  # 守护线程，主进程退出时自动退出
            )
            cleanup_thread.start()
            
            if config.history_retention_days == 0:
                logging.info(f"历史记录清理任务已启动: 每天 {config.history_cleanup_time} 执行，不保留历史记录")
            else:
                logging.info(f"历史记录清理任务已启动: 每天 {config.history_cleanup_time} 执行，保留 {config.history_retention_days} 天")
        except Exception as e:
            logging.error(f"清理调度器启动失败: {e}", exc_info=True)
    
    # 初始化企业微信发送器（使用配置文件中的key，用于默认配置）
    if config.qywechat_key:
        qywechat_sender = QyWeChatSender(key=config.qywechat_key, webhook_base_url=config.qywechat_base_url)
    
    # 初始化飞书发送器（使用配置文件中的key，用于默认配置）
    if config.feishu_key:
        feishu_sender = FeishuSender(key=config.feishu_key, webhook_base_url=config.feishu_base_url)
    
    # 初始化钉钉发送器（使用配置文件中的key，用于默认配置）
    if config.dingtalk_key:
        dingtalk_sender = DingTalkSender(key=config.dingtalk_key, webhook_base_url=config.dingtalk_base_url)
    
    # 启动Flask应用
    app.run(
        host=config.host,
        port=int(config.port),
        debug=False,
        use_reloader=False  # 禁用reloader，避免重复执行
    )


if __name__ == '__main__':
    main()

