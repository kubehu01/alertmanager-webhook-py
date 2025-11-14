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
from sender import QyWeChatSender

# 创建Flask应用
app = Flask(__name__)

# 全局变量
config = None
transformer = None
sender = None


def setup_logging(log_file_path: str):
    """配置日志"""
    # 创建日志目录
    log_dir = os.path.dirname(log_file_path)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志格式
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 文件处理器（带轮转）
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(log_format)
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    
    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 设置第三方库日志级别
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


@app.route('/qywechat', methods=['POST'])
def qywechat_webhook():
    """企业微信webhook接口"""
    try:
        # 获取请求数据
        notification_data = request.get_json()
        if not notification_data:
            return jsonify({"error": "请求数据为空"}), 400
        
        # 从URL参数获取key，如果存在则使用URL参数中的key，否则使用配置文件中的key
        url_key = request.args.get('key')
        
        # 统计告警信息用于日志
        alerts = notification_data.get("alerts", [])
        alert_count = len(alerts)
        firing_count = sum(1 for a in alerts if a.get("status") == "firing")
        resolved_count = sum(1 for a in alerts if a.get("status") == "resolved")
        top_status = notification_data.get("status", "mixed" if alert_count > 0 else "empty")
        
        if url_key:
            # 使用URL参数中的key创建新的sender
            current_sender = QyWeChatSender(url_key)
            logging.info(f"收到告警通知 (使用URL参数key: {url_key}): 总计 {alert_count} 个告警 "
                        f"(firing: {firing_count}, resolved: {resolved_count}, 顶层status: {top_status})")
        else:
            # 使用配置文件中的key
            if sender is None:
                return jsonify({"error": "企业微信key未配置，请在URL参数中提供key或在配置文件中配置qywechatKey"}), 400
            current_sender = sender
            config_key = config.qywechat_key if config else "未配置"
            logging.info(f"收到告警通知 (使用配置文件key: {config_key}): 总计 {alert_count} 个告警 "
                        f"(firing: {firing_count}, resolved: {resolved_count}, 顶层status: {top_status})")
        
        # 转换消息
        firing_message, resolved_message = transformer.transform_to_markdown(notification_data)
        
        # 发送消息
        if firing_message:
            current_sender.send_firing(firing_message)
        
        if resolved_message:
            current_sender.send_resolved(resolved_message)
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        logging.error(f"处理请求时发生错误: {e}\n{traceback.format_exc()}")
        return jsonify({"error": str(e)}), 500


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify({"status": "ok"}), 200


def main():
    """主函数"""
    global config, transformer, sender
    
    # 解析命令行参数
    import argparse
    parser = argparse.ArgumentParser(description='Alertmanager Webhook for 企业微信')
    parser.add_argument('-c', '--config', type=str, default='config.yaml',
                        help='配置文件路径 (默认: config.yaml)')
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
    logging.info(f"企业微信Key: {'已配置' if config.qywechat_key else '未配置'}")
    logging.info("=" * 50)
    
    # 初始化转换器
    # 获取模板路径（相对于app.py所在目录）
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "template", "alert.tmpl")
    transformer = Transformer(
        redis_server=config.redis_server,
        redis_port=config.redis_port,
        redis_password=config.redis_password,
        template_path=template_path
    )
    
    # 初始化发送器
    sender = QyWeChatSender(config.qywechat_key)
    
    # 启动Flask应用
    app.run(
        host=config.host,
        port=int(config.port),
        debug=False
    )


if __name__ == '__main__':
    main()


