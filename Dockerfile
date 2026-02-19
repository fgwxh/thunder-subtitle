# 使用Python 3.12作为基础镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 生成requirements.txt并安装依赖
RUN pip install --no-cache-dir pip-tools &&\
    pip-compile pyproject.toml -o requirements.txt &&\
    pip install --no-cache-dir -r requirements.txt &&\
    pip install --no-cache-dir -e .

# 暴露端口8010
EXPOSE 8010

# 设置环境变量
ENV HOST=0.0.0.0
ENV PORT=8010

# 启动命令
CMD ["python", "run_fastapi_ui.py"]