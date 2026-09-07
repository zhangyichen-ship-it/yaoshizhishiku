from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomException

from ..config import settings  # noqa: F401 - kept as a compatibility patch point for deployments/tests
from .control_plane_service import CloudControlPlaneConfig, get_control_plane_config


@dataclass
class _CircuitState:
    failures: int = 0
    opened_until: float = 0.0
    probe_in_flight: bool = False


_circuit_states: dict[tuple[str, int], _CircuitState] = {}
_circuit_lock = Lock()


def _ensure_circuit_available(key: tuple[str, int]) -> None:
    now = time.monotonic()
    with _circuit_lock:
        state = _circuit_states.setdefault(key, _CircuitState())
        if state.opened_until > now or state.probe_in_flight:
            raise CustomException(msg="云端成员服务暂时熔断，请稍后重试", status_code=503)
        if state.opened_until:
            # One probe is allowed after the recovery window; success closes it.
            state.probe_in_flight = True


def _record_circuit_success(key: tuple[str, int]) -> None:
    with _circuit_lock:
        state = _circuit_states.setdefault(key, _CircuitState())
        state.failures = 0
        state.opened_until = 0.0
        state.probe_in_flight = False


def _record_circuit_failure(key: tuple[str, int]) -> None:
    now = time.monotonic()
    threshold = max(1, int(getattr(settings, "KB_CONTROL_PLANE_CIRCUIT_FAILURE_THRESHOLD", 3)))
    recovery_seconds = max(0.0, float(getattr(settings, "KB_CONTROL_PLANE_CIRCUIT_RECOVERY_SECONDS", 15.0)))
    with _circuit_lock:
        state = _circuit_states.setdefault(key, _CircuitState())
        state.failures += 1
        state.probe_in_flight = False
        if state.failures >= threshold:
            state.opened_until = now + recovery_seconds


def _retry_allowed(method: str, resource: str, path: str, idempotency_key: str | None) -> bool:
    normalized_method = method.upper()
    if normalized_method == "PUT" and resource == "identity" and path == "/password":
        return False
    if normalized_method in {"GET", "HEAD", "OPTIONS", "PUT", "PATCH"}:
        return True
    return normalized_method == "POST" and (
        bool(idempotency_key)
        or (resource == "identity" and path == "/introspect")
        or (resource == "app-data" and path == "/introspect")
    )


class CloudMemberClient:
    """Call only the tenant-bound member API exposed by the cloud panel."""

    def __init__(
        self,
        *,
        db: AsyncSession | None = None,
        config: CloudControlPlaneConfig | None = None,
    ) -> None:
        self.db = db
        self.config = config

    async def _request_config(self) -> tuple[str, int, str, float]:
        config = self.config or await get_control_plane_config(db=self.db)
        if config is None:
            raise CustomException(msg="客户知识库未配置有效的云端成员服务凭证", status_code=503)
        return config.api_url, config.instance_id, config.service_credential, config.timeout

    async def _request(
        self,
        method: str,
        *,
        resource: str,
        path: str,
        payload: dict[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        base_url, instance_id, credential, timeout = await self._request_config()
        circuit_key = (base_url, instance_id)
        _ensure_circuit_available(circuit_key)
        headers = {"Authorization": f"Bearer {credential}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        retry_count = max(0, int(getattr(settings, "KB_CONTROL_PLANE_RETRY_COUNT", 2)))
        retry_backoff = max(0.0, float(getattr(settings, "KB_CONTROL_PLANE_RETRY_BACKOFF", 0.2)))
        max_attempts = 1 + (retry_count if _retry_allowed(method, resource, path, idempotency_key) else 0)
        response: httpx.Response | None = None
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
                    response = await client.request(
                        method,
                        f"{base_url}/kb-instances/{instance_id}/{resource}{path}",
                        headers=headers,
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(min(2.0, retry_backoff * (2**attempt)))
                    continue
                _record_circuit_failure(circuit_key)
                raise CustomException(msg="云端成员服务请求超时", status_code=503) from exc
            except httpx.RequestError as exc:
                if attempt + 1 < max_attempts:
                    await asyncio.sleep(min(2.0, retry_backoff * (2**attempt)))
                    continue
                _record_circuit_failure(circuit_key)
                raise CustomException(msg="云端成员服务不可达", status_code=503) from exc

            if response.status_code < 500 or attempt + 1 >= max_attempts:
                break
            await asyncio.sleep(min(2.0, retry_backoff * (2**attempt)))

        assert response is not None
        if response.is_success:
            _record_circuit_success(circuit_key)
        elif response.status_code >= 500:
            _record_circuit_failure(circuit_key)

        if response.status_code == 401:
            if resource == "identity" and path == "/login":
                raise CustomException(msg="账号或密码错误", status_code=401)
            if resource == "app-data" and path == "/introspect":
                raise CustomException(msg="云端 App Data 凭证无效或已过期", status_code=401)
            raise CustomException(msg="云端身份凭证无效或已过期" if resource == "identity" else "云端成员服务凭证无效", status_code=401 if resource == "identity" else 503)
        if response.status_code == 400 and resource == "identity" and path == "/password":
            raise CustomException(msg="原密码输入错误", status_code=400)
        if response.status_code == 403:
            if resource == "app-data" and path == "/introspect":
                raise CustomException(msg="当前账号无权访问该 App 数据", status_code=403)
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

    async def get_billing_summary(self) -> dict[str, Any]:
        result = await self._request("GET", resource="billing", path="")
        if not isinstance(result, dict) or result.get("currency") != "CNY":
            raise CustomException(msg="云端额度返回格式错误", status_code=502)
        member_count = result.get("memberCount")
        if not isinstance(member_count, int) or isinstance(member_count, bool) or member_count < 0:
            raise CustomException(msg="云端额度返回格式错误", status_code=502)
        required_numbers = (
            "freeLimitCny",
            "freeUsedCny",
            "freeRemainingCny",
            "paidBalanceCny",
            "totalAvailableCny",
        )
        if any(not isinstance(result.get(key), (int, float)) for key in required_numbers):
            raise CustomException(msg="云端额度返回格式错误", status_code=502)
        return result

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

    @staticmethod
    def _validate_access_result(result: Any) -> dict[str, Any]:
        if not isinstance(result, dict):
            raise CustomException(msg="云端知识库授权返回格式错误", status_code=502)
        keys = result.get("knowledge_base_keys", [])
        if not isinstance(keys, list) or any(not isinstance(key, str) or not key.strip() for key in keys):
            raise CustomException(msg="云端知识库授权返回格式错误", status_code=502)
        return result

    async def get_member_access(self, user_id: int) -> dict[str, Any]:
        result = await self._request("GET", resource="members", path=f"/{user_id}/knowledge-bases")
        return self._validate_access_result(result)

    async def set_member_access(
        self,
        user_id: int,
        *,
        resources: list[dict[str, Any]],
        knowledge_base_keys: list[str],
    ) -> dict[str, Any]:
        result = await self._request(
            "PUT",
            resource="members",
            path=f"/{user_id}/knowledge-bases",
            payload={"resources": resources, "knowledge_base_keys": knowledge_base_keys},
        )
        return self._validate_access_result(result)

    async def login_member(self, identity: str, password: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            resource="identity",
            path="/login",
            payload={"identity": identity, "password": password},
        )
        if not isinstance(result, dict) or not isinstance(result.get("user"), dict) or not isinstance(result.get("identity_token"), str) or not isinstance(result.get("refresh_token"), str):
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

    async def introspect_app_data_token(self, access_token: str) -> dict[str, Any]:
        result = await self._request(
            "POST",
            resource="app-data",
            path="/introspect",
            payload={"access_token": access_token},
        )
        if not isinstance(result, dict):
            raise CustomException(msg="云端 App Data 身份服务返回格式错误", status_code=502)
        required = ("app_id", "subject_id", "space_id", "session_id", "scopes")
        if any(not isinstance(result.get(key), (str, list)) for key in required):
            raise CustomException(msg="云端 App Data 身份服务返回格式错误", status_code=502)
        if not isinstance(result.get("scopes"), list):
            raise CustomException(msg="云端 App Data 权限声明格式错误", status_code=502)
        return result

    async def change_password(
        self,
        identity_token: str,
        old_password: str,
        new_password: str,
    ) -> dict[str, Any]:
        result = await self._request(
            "PUT",
            resource="identity",
            path="/password",
            payload={
                "identity_token": identity_token,
                "old_password": old_password,
                "new_password": new_password,
            },
        )
        if not isinstance(result, dict) or result.get("changed") is not True:
            raise CustomException(msg="云端身份服务返回格式错误", status_code=502)
        return result
