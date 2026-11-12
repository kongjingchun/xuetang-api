# @File    : Dockerfile
# @Desc    : 后端镜像。基础镜像固定 python:3.12，构建时再次断言版本
# @Author  : xuetang-api
# @Date    : 2026-11-12
# @Update  : 2026-11-12 初始化阶段 0 镜像

FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN python -c "import sys; assert sys.version_info[:2]==(3,12), sys.version"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/bin/sh", "/app/docker/entrypoint.sh"]
CMD ["web"]
