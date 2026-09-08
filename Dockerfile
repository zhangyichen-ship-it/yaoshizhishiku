# syntax=docker/dockerfile:1.7

# This file exposes two production targets:
#   docker build --target backend -t yostone-knowledge-backend .
#   docker build --target frontend -t yostone-knowledge-frontend .

FROM node:22-bookworm-slim AS frontend-deps

ENV COREPACK_ENABLE_DOWNLOAD_PROMPT=0

WORKDIR /build/frontend

RUN corepack enable \
    && corepack prepare pnpm@10.34.5 --activate

# Keep dependency installation in its own layer so source-only changes reuse
# the pnpm store and the installed dependency layer in CI.
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,id=yostone-pnpm-store,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile --ignore-scripts

FROM frontend-deps AS frontend-build

ARG VITE_VERSION=3.0.0
ARG VITE_BASE_URL=/
ARG VITE_APP_BASE_API=/api/v1
ARG VITE_APP_TITLE=Yostone-Knowledge
ARG VITE_APP_ENV=production
ARG VITE_ACCESS_MODE=mixed
ARG VITE_WITH_CREDENTIALS=false
ARG VITE_OPEN_ROUTE_INFO=false
ARG VITE_LOCK_ENCRYPT_KEY=please-change-me
ARG VITE_API_TIMEOUT=60000
ARG VITE_API_URL=/
ARG VITE_API_BASE_URL=/
ARG VITE_APP_WS_ENDPOINT=/api/v1
ARG VITE_DROP_CONSOLE=true

ENV VITE_VERSION=${VITE_VERSION} \
    VITE_BASE_URL=${VITE_BASE_URL} \
    VITE_APP_BASE_API=${VITE_APP_BASE_API} \
    VITE_APP_TITLE=${VITE_APP_TITLE} \
    VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_ACCESS_MODE=${VITE_ACCESS_MODE} \
    VITE_WITH_CREDENTIALS=${VITE_WITH_CREDENTIALS} \
    VITE_OPEN_ROUTE_INFO=${VITE_OPEN_ROUTE_INFO} \
    VITE_LOCK_ENCRYPT_KEY=${VITE_LOCK_ENCRYPT_KEY} \
    VITE_API_TIMEOUT=${VITE_API_TIMEOUT} \
    VITE_API_URL=${VITE_API_URL} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_APP_WS_ENDPOINT=${VITE_APP_WS_ENDPOINT} \
    VITE_DROP_CONSOLE=${VITE_DROP_CONSOLE}

COPY frontend/ ./
RUN pnpm run build

FROM nginx:1.27-alpine AS frontend

# The proxy target is a build argument because the frontend image can be
# connected to a backend container under a different DNS name in each
# environment. The default matches the Docker service name used by CI/CD.
ARG BACKEND_UPSTREAM=backend:8004

COPY frontend/deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN sed -i "s#http://127.0.0.1:8008/#http://${BACKEND_UPSTREAM}/#" \
    /etc/nginx/conf.d/default.conf
COPY --from=frontend-build /build/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1/ || exit 1


FROM python:3.12-slim-bookworm AS backend-build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Most dependencies have wheels, but keeping a compiler in this build stage
# also makes the image build work when a platform-specific wheel is missing.
RUN apt-get update \
    && apt-get install --no-install-recommends -y build-essential libffi-dev \
    && rm -rf /var/lib/apt/lists/* \
    && python -m pip install --no-cache-dir uv

# Install locked third-party dependencies before copying the application so
# normal source changes do not invalidate the expensive dependency layer.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,id=yostone-uv-cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY backend/ ./
RUN --mount=type=cache,id=yostone-uv-cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=prod \
    SERVER_HOST=0.0.0.0 \
    SERVER_PORT=8004 \
    PATH=/app/.venv/bin:$PATH

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system app \
    && useradd --system --gid app --home-dir /app --no-create-home app

COPY --from=backend-build --chown=app:app /app /app

# Runtime data must be writable and must survive image replacement. Mount
# these paths as named volumes or host volumes in the deployment platform.
RUN mkdir -p /app/data/chroma /app/data/bm25_index /app/data/fastembed \
    /app/storage/upload /app/storage/download /app/logs \
    && chown -R app:app /app

VOLUME ["/app/data", "/app/storage", "/app/logs"]

USER app

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=5 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8004/common/health/live', timeout=3)"]

ENTRYPOINT ["python", "main.py"]
CMD ["run", "--env=prod"]
