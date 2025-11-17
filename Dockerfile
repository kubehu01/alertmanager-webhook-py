# 使用官方Python运行时作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖,创建日志目录
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ && \
    mkdir -p logs

# 复制应用代码
COPY src/ ./src/
COPY template/ ./template/
COPY config/ ./config/

# 暴露端口
EXPOSE 9095

# 设置启动命令
CMD ["python", "src/app.py", "-c", "config/config.yaml"]
