#!/usr/bin/env bash
set -euo pipefail

DEPLOY_PATH=/www/wwwroot/yaoshizhishiku
cd "$DEPLOY_PATH"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "已生成 $DEPLOY_PATH/.env（来自模板）。请尽快改成生产密码，不要长期使用示例值。"
fi
if [ -z "${GHCR_TOKEN:-}" ]; then
  echo "缺少 GitHub Secret GHCR_TOKEN（需要 read:packages 的 PAT）。"
  exit 1
fi

REPO_LC="$(printf '%s' "$GITHUB_REPOSITORY" | tr '[:upper:]' '[:lower:]')"
if [ "${GITHUB_REF_TYPE:-}" = "tag" ]; then
  IMAGE_TAG="$GITHUB_REF_NAME"
else
  IMAGE_TAG="sha-$(printf '%s' "$GITHUB_SHA" | cut -c1-7)"
fi
export BACKEND_IMAGE="ghcr.io/${REPO_LC}/backend:${IMAGE_TAG}"
export FRONTEND_IMAGE="ghcr.io/${REPO_LC}/frontend:${IMAGE_TAG}"
export PULL_POLICY=always

echo "Deploying $BACKEND_IMAGE and $FRONTEND_IMAGE"

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
    echo "拉取失败（常见于国内访问 ghcr.io / Docker Hub 中断），20 秒后重试。"
    sleep 20
    attempt=$((attempt + 1))
  done
  echo "多次拉取仍失败：${services}"
  return 1
}

# 国内机器拉镜像经常 unexpected EOF，失败后重试可续传已下载的层。
pull_with_retry mysql redis
pull_with_retry backend frontend
# 服务器上没有前后端源码，禁止 compose 在 pull 失败时改去本地 build。
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
