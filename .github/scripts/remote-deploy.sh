#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH=/www/wwwroot/yaoshizhishiku
IMAGE_ARCHIVE="${IMAGE_ARCHIVE:-/tmp/yostone-images.tar.gz}"
cd "$DEPLOY_PATH"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 $DEPLOY_PATH/.env（来自模板）。请尽快改成生产密码，不要长期使用示例值。"
fi

REPO_LC="$(printf '%s' "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')"
if [ "${GITHUB_REF_TYPE:-}" = "tag" ]; then
  IMAGE_TAG="$GITHUB_REF_NAME"
else
  IMAGE_TAG="sha-$(printf '%s' "$GITHUB_SHA" | cut -c1-7)"
fi
export BACKEND_IMAGE="ghcr.io/${REPO_LC}/backend:${IMAGE_TAG}"
export FRONTEND_IMAGE="ghcr.io/${REPO_LC}/frontend:${IMAGE_TAG}"

echo "Deploying $BACKEND_IMAGE and $FRONTEND_IMAGE"

if [ -f "$IMAGE_ARCHIVE" ]; then
  echo "从 GitHub runner 传来的镜像包加载（不访问 ghcr.io）"
  gzip -dc "$IMAGE_ARCHIVE" | docker load
  rm -f "$IMAGE_ARCHIVE"
  export PULL_POLICY=never
else
  if [ -z "${GHCR_TOKEN:-}" ]; then
    echo "缺少镜像包，且没有 GHCR_TOKEN，无法部署。"
    exit 1
  fi
  export PULL_POLICY=always
  echo "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USERNAME" --password-stdin

  pull_with_retry() {
    services="$*"
    attempt=1
    max_attempts=8
    while [ "$attempt" -le "$max_attempts" ]; do
      echo "Pull attempt ${attempt}/${max_attempts}: ${services}"
      if docker compose pull ${services}; then
        return 0
      fi
      echo "拉取失败，20 秒后重试。"
      sleep 20
      attempt=$((attempt + 1))
    done
    echo "多次拉取仍失败：${services}"
    return 1
  }

  pull_with_retry mysql redis
  pull_with_retry backend frontend
fi

docker compose up -d --no-build --remove-orphans

container_status() {
  docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$1" 2>/dev/null || echo missing
}

wait_healthy() {
  name="$1"
  i=1
  while [ "$i" -le 36 ]; do
    status="$(container_status "$name")"
    echo "$name: $status ($i/36)"
    if [ "$status" = "healthy" ]; then
      return 0
    fi
    sleep 5
    i=$((i + 1))
  done
  return 1
}

if ! wait_healthy yostone-backend || ! wait_healthy yostone-frontend; then
  echo "健康检查失败，最近日志："
  docker compose ps -a
  docker compose logs --tail=120
  exit 1
fi

docker compose ps
echo "Deploy finished."
