from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.exceptions import CustomException

from ..config import settings


class CloudMemberClient:
    """Call only the tenant-bound member API exposed by the cloud panel."""

    def _request_config(self) -> tuple[str, int, str, float]:
        base_url = settings.KB_CONTROL_PLANE_API_URL.strip().rstrip("/")
        parsed = urlparse(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise CustomException(msg="客户知识库未配置有效的云端成员服务地址", status_code=503)

        instance_id = settings.KB_CONTROL_PLANE_INSTANCE_ID
        credential = settings.KB_CONTROL_PLANE_SERVICE_CREDENTIAL.strip()
        if not instance_id or instance_id <= 0 or not credential or len(credential) > 256:
            raise CustomException(msg="客户知识库未配置有效的云端成员服务凭证", status_code=503)

        timeout = settings.KB_CONTROL_PLANE_TIMEOUT
        if timeout <= 0 or timeout > 60:
            raise CustomException(msg="客户知识库云端成员服务超时配置无效", status_code=503)
        return base_url, instance_id, credential, timeout

    async def _request(
        self,
        method: str,
        *,
        resource: str,
        path: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        base_url, instance_id, credential, timeout = self._request_config()
        headers = {"Authorization": f"Bearer {credential}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                response = await client.request(
                    method,
                    f"{base_url}/kb-instances/{instance_id}/{resource}{path}",
                    headers=headers,
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise CustomException(msg="云端成员服务请求超时", status_code=503) from exc
        except httpx.RequestError as exc:
            raise CustomException(msg="云端成员服务不可达", status_code=503) from exc

        if response.status_code == 401:
            if resource == "identity" and path == "/login":
                raise CustomException(msg="账号或密码错误", status_code=401)
            raise CustomException(msg="云端身份凭证无效或已过期" if resource == "identity" else "云端成员服务凭证无效", status_code=401 if resource == "identity" else 503)
        if response.status_code == 403:
            raise CustomException(msg="当前账号未开通知识库或已被停用" if resource == "identity" else "云端成员服务拒绝当前实例", status_code=403 if resource == "identity" else 503)
        if response.status_code == 404:
            raise CustomException(msg="云端成员接口不存在或实例配置错误", status_code=502)
        if response.status_code == 409:
            raise CustomException(msg="云端员工已存在或幂等键冲突", status_code=409)
        if response.status_code == 422:
            raise CustomException(msg="云端员工参数不合法", status_code=422)
        if response.status_code >= 500:
            raise CustomException(msg="云端成员服务暂时不可用", status_code=503)
        if not response.is_success:
            raise CustomException(msg="云端成员服务请求失败", status_code=502)

        try:
            result = response.json()
        except ValueError as exc:
            raise CustomException(msg="云端成员服务返回格式错误", status_code=502) from exc
        if not isinstance(result, dict) or result.get("success") is not True:
            raise CustomException(msg="云端成员服务返回失败", status_code=502)
        return result.get("data")

    async def list_members(self) -> list[dict[str, Any]]:
        result = await self._request("GET", resource="members", path="")
        if not isinstance(result, list) or any(not isinstance(item, dict) for item in result):
            raise CustomException(msg="云端员工目录返回格式错误", status_code=502)
        return result

    async def get_embedding_config(self) -> dict[str, str]:
        result = await self._request("GET", resource="embedding-config", path="")
        if not isinstance(result, dict):
            raise CustomException(msg="云端向量模型配置返回格式错误", status_code=502)
        provider = result.get("provider")
        model = result.get("model")
        base_url = result.get("base_url", "")
        if provider not in {"local", "openai"} or not isinstance(model, str) or not model.strip():
            raise CustomException(msg="云端向量模型配置格式错误", status_code=502)
        if not isinstance(base_url, str) or (provider == "openai" and not base_url.strip()):
            raise CustomException(msg="云端向量模型地址配置格式错误", status_code=502)
        return {"provider": provider, "model": model.strip(), "base_url": base_url.strip()}

    async def create_member(self, payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
        result = await self._request("POST", resource="members", path="", payload=payload, idempotency_key=idempotency_key)
        if not isinstance(result, dict):
            raise CustomException(msg="云端员工返回格式错误", status_code=502)
        return result

    async def update_member(self, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        result = await self._request("PATCH", resource="members", path=f"/{user_id}", payload=payload)
        if not isinstance(result, dict):
            raise CustomException(msg="云端员工返回格式错误", status_code=502)
        return result

    async def login_member(self, identity: str, password: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            resource="identity",
            path="/login",
            payload={"identity": identity, "password": password},
        )
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("user"), dict)
            or not isinstance(result.get("identity_token"), str)
            or not isinstance(result.get("refresh_token"), str)
        ):
            raise CustomException(msg="云端身份服务返回格式错误", status_code=502)
        return result

    async def refresh_identity(self, refresh_token: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            resource="identity",
            path="/refresh",
            payload={"refresh_token": refresh_token},
        )
        if not isinstance(result, dict) or not isinstance(result.get("user"), dict) or not isinstance(result.get("identity_token"), str):
            raise CustomException(msg="云端身份服务返回格式错误", status_code=502)
        return result

    async def introspect_identity(self, identity_token: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            resource="identity",
            path="/introspect",
            payload={"identity_token": identity_token},
        )
        if not isinstance(result, dict):
            raise CustomException(msg="云端身份服务返回格式错误", status_code=502)
        return result
