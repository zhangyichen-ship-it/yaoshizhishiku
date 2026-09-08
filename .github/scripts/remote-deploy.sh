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

# 国内机器拉 ghcr.io / Docker Hub 往往很慢，分步拉并打印进度，避免看起来像卡死。
docker compose pull mysql redis
docker compose pull backend frontend
docker compose up -d --remove-orphans

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
