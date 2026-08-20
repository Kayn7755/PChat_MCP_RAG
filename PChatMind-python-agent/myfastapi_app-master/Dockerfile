FROM python:3.11-slim # 基于官方 Python 3.11 精简系统

WORKDIR /app # 容器里工作目录

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# COPY安装依赖
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . . # 	拷贝项目代码

EXPOSE 8000 # 声明服务端口

CMD ["sh", "-c", "uvicorn TouTiaoApp.main:app --host 0.0.0.0 --port ${PORT:-8000}"] # 容器启动时跑 FastAPI

# Docker 是什么（一句话）
# Dockerfile = 菜谱；
# 镜像 = 按菜谱做好的打包好的运行环境(已经准备就绪, 放进服务器就能运行)；容器 = 用镜像跑起来的一个进程(正在运行)。
# 你本机没有厨房（Docker），但可以把菜谱交给云端的厨房去烧。

# 当前的方法是云端构建（你现在 CloudBase）, 本机没有docker, 打包发生在云托管构建机读 Dockerfile
# 流程: git push → 云端 build → 云端 run, 依赖云端构建环境

# 本地 Docker 打包再部署, 需要本机安装Docker, 在电脑中 docker build打包, 把镜像（或镜像 tar / 推到镜像仓库）
# 流程: 本地 build → docker push 到仓库 → 服务器 docker pull & run