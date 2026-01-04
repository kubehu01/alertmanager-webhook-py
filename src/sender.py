"""
机器人消息发送模块（支持企业微信、飞书、钉钉）
"""
import requests
import logging
from typing import Optional, List

from models import QyWeChatMarkdown, FeishuMarkdown, DingTalkMarkdown

logger = logging.getLogger(__name__)

# 各平台消息长度限制（字符数）
QYWECHAT_MAX_LENGTH = 4096  # 企业微信Markdown消息content字段限制
FEISHU_MAX_LENGTH = 8000    # 飞书卡片消息content字段限制（保守估计）
DINGTALK_MAX_LENGTH = 5000  # 钉钉Markdown消息text字段限制


def _split_content(content: str, max_length: int, reserve_for_prefix: int = 50, total_parts: int = 1) -> List[str]:
    """
    智能分割消息内容，尽量在换行符处分割
    
    Args:
        content: 原始消息内容
        max_length: 最大长度限制
        reserve_for_prefix: 为前缀标识符预留的空间（如 "(1/2)" 等）
        total_parts: 预计分割的总数（用于计算标识符长度，如果未知则使用最大值）
        
    Returns:
        分割后的消息列表
    """
    # 标识符格式: "**(1/2)**\n\n" 
    # 计算最大可能的标识符长度：假设最多99条消息，标识符为 "**(99/99)**\n\n" = 13字符
    # 但为了安全，我们使用更大的预留值
    if total_parts > 1:
        # 计算实际标识符长度（例如 "**(1/2)**\n\n" = 11字符）
        max_prefix_len = len(f"**({total_parts}/{total_parts})**\n\n")
    else:
        # 如果不知道总数，使用最大可能值
        max_prefix_len = len("**(99/99)**\n\n")  # 13字符
    
    # 为了更安全，考虑以下因素：
    # 1. 标识符长度（约15字符）
    # 2. JSON序列化可能转义字符（如\n变成\\n，增加长度）
    # 3. Markdown/HTML特殊字符可能被特殊计算
    # 4. 企业微信可能对某些字符有特殊计算方式
    # 所以预留更多空间，确保安全
    prefix_max_length = max(max_prefix_len, 50)  # 增加到50字符的预留空间
    
    # 实际可用长度 = 最大长度 - 标识符长度
    # 确保添加标识符后不会超过限制
    effective_length = max_length - prefix_max_length
    
    if len(content) <= max_length:
        return [content]
    
    parts = []
    remaining = content
    
    while len(remaining) > effective_length:
        # 尝试在换行符处分割（在换行符之前分割，不包含换行符）
        # 搜索范围：0 到 effective_length（不包含effective_length位置）
        split_pos = remaining.rfind('\n', 0, effective_length)
        
        # 如果找不到换行符，尝试在空格处分割
        if split_pos == -1:
            split_pos = remaining.rfind(' ', 0, effective_length)
        
        # 如果还是找不到合适的分割点，直接按有效长度分割
        if split_pos == -1:
            split_pos = effective_length
        
        # 提取当前部分（严格限制在effective_length内）
        # 注意：split_pos可能等于effective_length，此时part长度正好是effective_length
        part = remaining[:split_pos]
        
        # 严格确保part长度不超过effective_length
        if len(part) > effective_length:
            part = part[:effective_length]
            split_pos = effective_length
            logger.warning(f"分割出的part长度超过effective_length {effective_length}，已强制截断到 {len(part)}")
        
        # 更新剩余内容（跳过分割符，如果有的话）
        if split_pos < len(remaining):
            # 如果split_pos位置是换行符或空格，跳过它
            if remaining[split_pos] in ['\n', ' ']:
                remaining = remaining[split_pos + 1:]
            else:
                # 否则从split_pos开始（不跳过字符）
                remaining = remaining[split_pos:]
        else:
            remaining = ""
        
        # 确保part不为空
        if part:
            parts.append(part)
        else:
            # 如果part为空，说明有问题，强制截断remaining
            logger.warning(f"分割出的part为空，强制截断remaining")
            part = remaining[:effective_length]
            remaining = remaining[effective_length:]
            if part:
                parts.append(part)
    
    # 添加剩余内容
    if remaining:
        parts.append(remaining)
    
    return parts


class QyWeChatSender:
    """企业微信消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"):
        """
        初始化企业微信发送器
        
        Args:
            key: 企业微信机器人key（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("企业微信key不能为空")
        self.key = key
        base_url = webhook_base_url.rstrip('?')
        self.webhook_url = f"{base_url}?key={key}"
    
    def send(self, message: QyWeChatMarkdown) -> bool:
        """
        发送消息到企业微信
        
        Args:
            message: 企业微信Markdown消息对象
            
        Returns:
            bool: 发送是否成功（所有分割消息都发送成功才返回True）
        """
        if not self.webhook_url:
            logger.warning("企业微信webhook URL未配置")
            return False
        
        if not message or not message.markdown.get("content"):
            logger.warning("消息内容为空，跳过发送")
            return False
        
        content = message.markdown.get("content", "")
        
        # 先估算需要分割的数量（用于计算标识符长度）
        estimated_parts = (len(content) // (QYWECHAT_MAX_LENGTH - 30)) + 1 if len(content) > QYWECHAT_MAX_LENGTH else 1
        
        # 检查消息长度，如果超限则分割
        content_parts = _split_content(content, QYWECHAT_MAX_LENGTH, total_parts=estimated_parts)
        
        if len(content_parts) > 1:
            logger.info(f"消息长度 {len(content)} 字符超过限制 {QYWECHAT_MAX_LENGTH}，将分割为 {len(content_parts)} 条消息发送")
            # 记录每个part的长度用于调试
            for idx, p in enumerate(content_parts, 1):
                logger.debug(f"分割后的part {idx} 长度: {len(p)} 字符")
        
        # 发送所有分割后的消息
        all_success = True
        for i, part in enumerate(content_parts, 1):
            try:
                # 创建新的消息对象
                part_message = QyWeChatMarkdown()
                
                # 如果是分割消息，添加标识
                if len(content_parts) > 1:
                    # 先计算实际标识符长度
                    prefix = f"**({i}/{len(content_parts)})**\n\n"
                    prefix_len = len(prefix)
                    
                    # 记录原始part长度
                    original_part_len = len(part)
                    
                    # 计算最大允许的part长度（必须严格小于限制）
                    max_part_length = QYWECHAT_MAX_LENGTH - prefix_len
                    
                    # 如果part超过最大允许长度，截断它
                    if len(part) > max_part_length:
                        logger.warning(f"消息片段 {i}/{len(content_parts)} 原始长度 {len(part)} 超过可用长度 {max_part_length}，将截断")
                        part = part[:max_part_length]
                    
                    # 组合最终内容
                    final_content = prefix + part
                    final_length = len(final_content)
                    
                    # 最终严格检查（必须小于等于限制）
                    if final_length > QYWECHAT_MAX_LENGTH:
                        # 如果还是超限，进一步截断part
                        excess = final_length - QYWECHAT_MAX_LENGTH
                        part = part[:len(part) - excess]
                        final_content = prefix + part
                        final_length = len(final_content)
                        logger.warning(f"消息片段 {i}/{len(content_parts)} 截断后长度: {final_length} 字符")
                    
                    # 再次检查（绝对不允许超过）
                    if len(final_content) > QYWECHAT_MAX_LENGTH:
                        logger.error(f"消息片段 {i}/{len(content_parts)} 最终长度 {len(final_content)} 仍超过限制 {QYWECHAT_MAX_LENGTH}，跳过发送")
                        logger.error(f"详细信息: part长度={len(part)}, prefix长度={prefix_len}, 原始part长度={original_part_len}")
                        all_success = False
                        continue
                    
                    # 记录详细信息用于调试
                    logger.info(f"消息片段 {i}/{len(content_parts)}: part长度={len(part)}, prefix长度={prefix_len}, 最终长度={final_length}")
                    
                    part_message.set_content(final_content)
                else:
                    part_message.set_content(part)
                
                # 检查多种长度计算方式
                # 企业微信可能按UTF-8字节长度、JSON序列化长度或其他方式计算
                import json
                message_dict = part_message.to_dict()
                content_in_json = message_dict.get("markdown", {}).get("content", "")
                original_length = len(content_in_json)
                
                # 检查UTF-8字节长度（中文字符占3字节）
                utf8_byte_length = len(content_in_json.encode('utf-8'))
                
                # 检查JSON序列化后的content长度
                json_content_str = json.dumps(content_in_json, ensure_ascii=False)
                json_content_length = len(json_content_str) - 2  # 减去两边的引号
                
                logger.debug(f"消息片段 {i}/{len(content_parts)} 原始长度: {original_length}, UTF-8字节长度: {utf8_byte_length}, JSON序列化长度: {json_content_length}")
                
                # 企业微信可能按UTF-8字节长度计算，所以需要确保UTF-8字节长度不超过4096
                # 循环截断直到UTF-8字节长度符合要求
                max_iterations = 20  # 最多尝试20次
                iteration = 0
                safe_byte_max_length = QYWECHAT_MAX_LENGTH - 10  # 留出10字节的安全余量
                
                while utf8_byte_length > safe_byte_max_length and iteration < max_iterations:
                    iteration += 1
                    logger.warning(f"消息片段 {i}/{len(content_parts)} UTF-8字节长度 {utf8_byte_length} 超过安全限制 {safe_byte_max_length}，第{iteration}次截断")
                    
                    # 计算需要截断的字符数
                    # UTF-8字节长度和原始字符长度的比例（中文字符占3字节，英文占1字节）
                    if original_length > 0:
                        byte_ratio = utf8_byte_length / original_length
                    else:
                        byte_ratio = 2.0  # 默认比例（假设主要是中文）
                    
                    # 计算需要截断的原始字符数
                    excess = utf8_byte_length - safe_byte_max_length
                    # 考虑字节比例，需要截断更多原始字符
                    truncate_chars = int(excess / byte_ratio) + 100  # 额外截断100字符确保安全
                    
                    if len(content_in_json) > truncate_chars:
                        new_content = content_in_json[:len(content_in_json) - truncate_chars]
                        part_message.set_content(new_content)
                        # 更新变量并重新计算
                        message_dict = part_message.to_dict()
                        content_in_json = message_dict.get("markdown", {}).get("content", "")
                        original_length = len(content_in_json)
                        utf8_byte_length = len(content_in_json.encode('utf-8'))
                        json_content_str = json.dumps(content_in_json, ensure_ascii=False)
                        json_content_length = len(json_content_str) - 2
                        logger.debug(f"消息片段 {i}/{len(content_parts)} 第{iteration}次截断后: 原始长度={original_length}, UTF-8字节长度={utf8_byte_length}, JSON序列化长度={json_content_length}")
                    else:
                        logger.error(f"消息片段 {i}/{len(content_parts)} 内容太短无法截断，跳过发送")
                        all_success = False
                        break
                
                # 最终检查：确保UTF-8字节长度不超过限制
                if utf8_byte_length > QYWECHAT_MAX_LENGTH:
                    logger.error(f"消息片段 {i}/{len(content_parts)} UTF-8字节长度 {utf8_byte_length} 仍超过限制 {QYWECHAT_MAX_LENGTH}，跳过发送")
                    all_success = False
                    continue
                
                if iteration > 0:
                    logger.info(f"消息片段 {i}/{len(content_parts)} 最终: 原始长度={original_length}, UTF-8字节长度={utf8_byte_length}, JSON序列化长度={json_content_length} (经过{iteration}次截断)")
                
                response = requests.post(
                    self.webhook_url,
                    json=part_message.to_dict(),
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("errcode") == 0:
                    if len(content_parts) > 1:
                        logger.info(f"消息片段 {i}/{len(content_parts)} 发送成功（长度: {len(part_message.markdown.get('content', ''))} 字符）")
                    else:
                        logger.info("消息发送成功")
                else:
                    logger.error(f"消息片段 {i}/{len(content_parts)} 发送失败: {result}")
                    all_success = False
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"发送消息片段 {i}/{len(content_parts)} 时发生网络错误: {e}")
                all_success = False
            except Exception as e:
                logger.error(f"发送消息片段 {i}/{len(content_parts)} 时发生未知错误: {e}", exc_info=True)
                all_success = False
        
        return all_success
    
    def send_firing(self, message: Optional[QyWeChatMarkdown]) -> bool:
        """发送触发告警消息"""
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[QyWeChatMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False


class FeishuSender:
    """飞书消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://open.feishu.cn/open-apis/bot/v2/hook"):
        """
        初始化飞书发送器
        
        Args:
            key: 飞书机器人token（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("飞书key不能为空")
        # 使用基础URL + key组合（飞书的key在路径中）
        base_url = webhook_base_url.rstrip('/')
        self.webhook_url = f"{base_url}/{key}"
    
    def send(self, message: FeishuMarkdown) -> bool:
        """
        发送消息到飞书
        
        Args:
            message: 飞书Markdown消息对象
            
        Returns:
            bool: 发送是否成功（所有分割消息都发送成功才返回True）
        """
        if not message or not message.card.get("elements"):
            logger.warning("消息内容为空，跳过发送")
            return False
        
        # 获取消息内容
        elements = message.card.get("elements", [])
        if not elements or not elements[0].get("text", {}).get("content"):
            logger.warning("消息内容为空，跳过发送")
            return False
        
        content = elements[0]["text"]["content"]
        
        # 检查消息长度，如果超限则分割
        content_parts = _split_content(content, FEISHU_MAX_LENGTH)
        
        if len(content_parts) > 1:
            logger.info(f"消息长度 {len(content)} 字符超过限制 {FEISHU_MAX_LENGTH}，将分割为 {len(content_parts)} 条消息发送")
        
        # 发送所有分割后的消息
        all_success = True
        for i, part in enumerate(content_parts, 1):
            try:
                # 创建新的消息对象
                part_message = FeishuMarkdown()
                
                # 如果是分割消息，添加标识
                if len(content_parts) > 1:
                    prefix = f"**({i}/{len(content_parts)})**\n\n"
                    prefix_len = len(prefix)
                    
                    # 确保part长度加上标识符长度不超过限制
                    max_part_length = FEISHU_MAX_LENGTH - prefix_len
                    if len(part) > max_part_length:
                        logger.warning(f"飞书消息片段 {i}/{len(content_parts)} 原始长度 {len(part)} 超过可用长度 {max_part_length}，将截断")
                        part = part[:max_part_length]
                    
                    final_content = prefix + part
                    
                    # 最终检查（双重保险）
                    if len(final_content) > FEISHU_MAX_LENGTH:
                        logger.error(f"飞书消息片段 {i}/{len(content_parts)} 最终长度 {len(final_content)} 仍超过限制 {FEISHU_MAX_LENGTH}，跳过发送")
                        all_success = False
                        continue
                    
                    part_content = final_content
                else:
                    part_content = part
                
                part_message.set_content(part_content)
                
                response = requests.post(
                    self.webhook_url,
                    json=part_message.to_dict(),
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("code") == 0:
                    if len(content_parts) > 1:
                        logger.info(f"飞书消息片段 {i}/{len(content_parts)} 发送成功（长度: {len(part_content)} 字符）")
                    else:
                        logger.info("飞书消息发送成功")
                else:
                    logger.error(f"飞书消息片段 {i}/{len(content_parts)} 发送失败: {result}")
                    all_success = False
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"发送飞书消息片段 {i}/{len(content_parts)} 时发生网络错误: {e}")
                all_success = False
            except Exception as e:
                logger.error(f"发送飞书消息片段 {i}/{len(content_parts)} 时发生未知错误: {e}", exc_info=True)
                all_success = False
        
        return all_success
    
    def send_firing(self, message: Optional[FeishuMarkdown]) -> bool:
        """发送触发告警消息"""
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[FeishuMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False


class DingTalkSender:
    """钉钉消息发送器"""
    
    def __init__(self, key: str = "", webhook_base_url: str = "https://oapi.dingtalk.com/robot/send"):
        """
        初始化钉钉发送器
        
        Args:
            key: 钉钉机器人access_token（必需）
            webhook_base_url: webhook基础URL（可选，默认官方地址）
        """
        if not key:
            raise ValueError("钉钉key不能为空")
        # 使用基础URL + key组合（钉钉的key是access_token参数）
        base_url = webhook_base_url.rstrip('?')
        self.webhook_url = f"{base_url}?access_token={key}"
    
    def send(self, message: DingTalkMarkdown) -> bool:
        """
        发送消息到钉钉
        
        Args:
            message: 钉钉Markdown消息对象
            
        Returns:
            bool: 发送是否成功（所有分割消息都发送成功才返回True）
        """
        if not message or not message.markdown.get("text"):
            logger.warning("消息内容为空，跳过发送")
            return False
        
        content = message.markdown.get("text", "")
        title = message.markdown.get("title", "告警通知")
        
        # 检查消息长度，如果超限则分割
        content_parts = _split_content(content, DINGTALK_MAX_LENGTH)
        
        if len(content_parts) > 1:
            logger.info(f"消息长度 {len(content)} 字符超过限制 {DINGTALK_MAX_LENGTH}，将分割为 {len(content_parts)} 条消息发送")
        
        # 发送所有分割后的消息
        all_success = True
        for i, part in enumerate(content_parts, 1):
            try:
                # 创建新的消息对象
                part_message = DingTalkMarkdown()
                
                # 如果是分割消息，添加标识
                if len(content_parts) > 1:
                    prefix = f"**({i}/{len(content_parts)})**\n\n"
                    prefix_len = len(prefix)
                    
                    # 确保part长度加上标识符长度不超过限制
                    max_part_length = DINGTALK_MAX_LENGTH - prefix_len
                    if len(part) > max_part_length:
                        logger.warning(f"钉钉消息片段 {i}/{len(content_parts)} 原始长度 {len(part)} 超过可用长度 {max_part_length}，将截断")
                        part = part[:max_part_length]
                    
                    final_content = prefix + part
                    
                    # 最终检查（双重保险）
                    if len(final_content) > DINGTALK_MAX_LENGTH:
                        logger.error(f"钉钉消息片段 {i}/{len(content_parts)} 最终长度 {len(final_content)} 仍超过限制 {DINGTALK_MAX_LENGTH}，跳过发送")
                        all_success = False
                        continue
                    
                    part_content = final_content
                    part_title = f"{title} ({i}/{len(content_parts)})"
                else:
                    part_content = part
                    part_title = title
                
                part_message.set_content(part_content, title=part_title)
                
                response = requests.post(
                    self.webhook_url,
                    json=part_message.to_dict(),
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get("errcode") == 0:
                    if len(content_parts) > 1:
                        logger.info(f"钉钉消息片段 {i}/{len(content_parts)} 发送成功（长度: {len(part_content)} 字符）")
                    else:
                        logger.info("钉钉消息发送成功")
                else:
                    logger.error(f"钉钉消息片段 {i}/{len(content_parts)} 发送失败: {result}")
                    all_success = False
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"发送钉钉消息片段 {i}/{len(content_parts)} 时发生网络错误: {e}")
                all_success = False
            except Exception as e:
                logger.error(f"发送钉钉消息片段 {i}/{len(content_parts)} 时发生未知错误: {e}", exc_info=True)
                all_success = False
        
        return all_success
    
    def send_firing(self, message: Optional[DingTalkMarkdown]) -> bool:
        """发送触发告警消息"""
        return self.send(message) if message else False
    
    def send_resolved(self, message: Optional[DingTalkMarkdown]) -> bool:
        """发送告警恢复消息"""
        return self.send(message) if message else False


