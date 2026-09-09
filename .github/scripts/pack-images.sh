#!/usr/bin/env bash
set -euo pipefail

# 在 GitHub-hosted runner 上执行：从 GHCR / Docker Hub 拉镜像并打成包。
# 国内服务器再 docker load，避免直接访问 ghcr.io。

REPO_LC="$(printf '%s' "${GITHUB_REPOSITORY}" | tr '[:upper:]' '[:lower:]')"
if [ "${GITHUB_REF_TYPE:-}" = "tag" ]; then
  IMAGE_TAG="${GITHUB_REF_NAME}"
else
  IMAGE_TAG="sha-$(printf '%s' "${GITHUB_SHA}" | cut -c1-7)"
fi

BACKEND_IMAGE="ghcr.io/${REPO_LC}/backend:${IMAGE_TAG}"
FRONTEND_IMAGE="ghcr.io/${REPO_LC}/frontend:${IMAGE_TAG}"
MYSQL_IMAGE="mysql:8.4"
REDIS_IMAGE="redis:7-alpine"
OUT="${GITHUB_WORKSPACE}/yostone-images.tar.gz"

echo "Packing ${BACKEND_IMAGE} ${FRONTEND_IMAGE} ${MYSQL_IMAGE} ${REDIS_IMAGE}"
docker pull "${BACKEND_IMAGE}"
docker pull "${FRONTEND_IMAGE}"
docker pull "${MYSQL_IMAGE}"
docker pull "${REDIS_IMAGE}"
docker save "${BACKEND_IMAGE}" "${FRONTEND_IMAGE}" "${MYSQL_IMAGE}" "${REDIS_IMAGE}" | gzip -1 > "${OUT}"
ls -lh "${OUT}"
