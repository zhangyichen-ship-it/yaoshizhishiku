# syntax=docker/dockerfile:1
#
# 构建（在 backend/ 目录）：
#   docker build -t yostone-knowledge-backend .
# 国内镜像加速示例：
#   docker build --build-arg UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple -t yostone-knowledge-backend .
#
# 运行前必须注入 SECRET_KEY、数据库和 Redis；向量/上传目录请挂卷，避免容器重建丢数据。

ARG PYTHON_IMAGE=python:3.12-slim-bookworm
ARG UV_VERSION=0.9.15

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------------------
# 公共基础层：运行时系统库（onnxruntime/fastembed 需要 libgomp）
# ---------------------------------------------------------------------------
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=UTF-8 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=Asia/Shanghai

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libgomp1 \
        tzdata \
    && ln -snf /usr/share/zoneinfo/${TZ} /etc/localtime \
    && echo ${TZ} > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# 构建层：用 uv 按锁文件安装生产依赖（不含 pytest/ruff）
# ---------------------------------------------------------------------------
FROM base AS builder

ARG UV_INDEX_URL=https://pypi.org/simple

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0 \
    UV_INDEX_URL=${UV_INDEX_URL}

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY main.py alembic.ini banner.txt ./
COPY app ./app
COPY static ./static
COPY env ./env

# 本仓库是 virtual 项目，源码不进 site-packages；再 sync 一次确保锁与源码一致
RUN uv sync --frozen --no-dev

# ---------------------------------------------------------------------------
# 运行层：只带解释器、.venv 和业务代码
# ---------------------------------------------------------------------------
FROM base AS runtime

ARG VERSION=0.0.0
LABEL org.opencontainers.image.title="yostone-knowledge-backend" \
      org.opencontainers.image.description="Yostone Knowledge 客户知识库后端" \
      org.opencontainers.image.version="${VERSION}"

ENV PATH="/app/.venv/bin:${PATH}" \
    ENVIRONMENT=prod \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8004 \
    DEBUG=False \
    ROOT_PATH=/api/v1 \
    LOCAL_EMBEDDING_CACHE_DIR=/app/data/fastembed \
    CHROMA_PERSIST_DIR=/app/data/chroma \
    BM25_INDEX_DIR=/app/data/bm25_index \
    UPLOAD_FILE_PATH=/app/storage/upload

WORKDIR /app

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --home /app --shell /usr/sbin/nologin app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/main.py /app/alembic.ini /app/banner.txt /app/
COPY --from=builder --chown=app:app /app/app /app/app
COPY --from=builder --chown=app:app /app/static /app/static
COPY --from=builder --chown=app:app /app/env /app/env

RUN mkdir -p \
        /app/logs \
        /app/data/chroma \
        /app/data/fastembed \
        /app/data/bm25_index \
        /app/storage/upload \
        /app/storage/knowledge \
        /app/storage/download \
    && chown -R app:app /app/logs /app/data /app/storage

USER app

EXPOSE 8004

# 启动会跑 Alembic 和种子，给足 start-period；存活探针不依赖 DB/Redis
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/common/health/live' % os.environ.get('SERVER_PORT','8004'), timeout=4)"

STOPSIGNAL SIGTERM

CMD ["python", "main.py", "run", "--env=prod"]
