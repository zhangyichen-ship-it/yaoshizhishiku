# syntax=docker/dockerfile:1
#
# 构建（在 frontend/ 目录）：
#   docker build -t yostone-knowledge-frontend .
#
# 容器内 nginx 监听 80，把 /api/v1/ 反代到 compose 服务名 backend:8004。

ARG NODE_IMAGE=node:22-bookworm-slim
ARG NGINX_IMAGE=nginx:1.27-alpine
ARG PNPM_VERSION=10.34.5

FROM ${NODE_IMAGE} AS builder

ARG PNPM_VERSION
ENV HUSKY=0

RUN corepack enable \
    && corepack prepare "pnpm@${PNPM_VERSION}" --activate

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml .npmrc ./
RUN pnpm install --frozen-lockfile

COPY . .
ENV NODE_ENV=production
RUN pnpm build

FROM ${NGINX_IMAGE} AS runtime

ARG VERSION=0.0.0
LABEL org.opencontainers.image.title="yostone-knowledge-frontend" \
      org.opencontainers.image.description="Yostone Knowledge 客户知识库前端" \
      org.opencontainers.image.version="${VERSION}"

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1

STOPSIGNAL SIGQUIT

CMD ["nginx", "-g", "daemon off;"]
