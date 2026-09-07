from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomException

from .model import AppDataAuditModel, AppResourceAclModel, AppResourceModel
from .schema import AppResourceAclInput, AppResourceCreateSchema, AppResourcePatchSchema


@dataclass(frozen=True, slots=True)
class AppDataPrincipal:
    tenant_id: str | None
    subject_id: str
    membership_id: str | None
    space_id: str
    customer_instance_id: str
    roles: tuple[str, ...]
    session_id: str
    app_id: str
    scopes: tuple[dict[str, object], ...]


def principal_from_claims(claims: dict[str, object]) -> AppDataPrincipal:
    try:
        scopes = claims["scopes"]
        roles = claims.get("roles", [])
        if not isinstance(scopes, list) or not isinstance(roles, list):
            raise TypeError
        return AppDataPrincipal(
            tenant_id=str(claims.get("tenant_id")) if claims.get("tenant_id") is not None else None,
            subject_id=str(claims["subject_id"]),
            membership_id=str(claims["membership_id"]) if claims.get("membership_id") is not None else None,
            space_id=str(claims["space_id"]),
            customer_instance_id=str(claims["customer_instance_id"]),
            roles=tuple(str(role) for role in roles),
            session_id=str(claims["session_id"]),
            app_id=str(claims["app_id"]),
            scopes=tuple(item for item in scopes if isinstance(item, dict)),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CustomException(msg="App Data 身份响应格式错误", status_code=502) from exc


class AppDataService:
    def __init__(self, db: AsyncSession, principal: AppDataPrincipal):
        self.db = db
        self.principal = principal

    def _ensure_app(self, app_id: str, resource_type: str) -> None:
        if app_id != self.principal.app_id:
            raise CustomException(msg="App Data 应用空间不匹配", status_code=403)
        if not resource_type or len(resource_type) > 128:
            raise CustomException(msg="资源类型不合法", status_code=422)
        if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._/-" for char in resource_type):
            raise CustomException(msg="资源类型不合法", status_code=422)

    def _ensure_scope(self, resource_type: str, action: str, data_scope: str | None = None) -> None:
        for grant in self.principal.scopes:
            if grant.get("resource_type") != resource_type:
                continue
            actions = grant.get("actions", [])
            scopes = grant.get("scopes", [])
            if action in actions and (data_scope is None or data_scope in scopes):
                return
        raise CustomException(msg="App Data 权限不足", status_code=403)

    async def _acl(self, resource_id: int, permission: str) -> bool:
        grants = (
            await self.db.execute(
                select(AppResourceAclModel).where(
                    AppResourceAclModel.resource_id == resource_id,
                    AppResourceAclModel.is_deleted.is_(False),
                    AppResourceAclModel.permission == permission,
                )
            )
        ).scalars().all()
        return any(
            (grant.subject_type == "USER" and grant.subject_id == self.principal.subject_id)
            or (grant.subject_type == "ROLE" and grant.subject_id in self.principal.roles)
            for grant in grants
        )

    async def _visible(self, resource: AppResourceModel, permission: str = "READ") -> bool:
        if resource.access_policy == "TENANT_SHARED":
            return resource.data_scope == "TENANT"
        if resource.access_policy == "OWNER_ONLY":
            return resource.owner_space_id == self.principal.space_id
        if resource.access_policy == "ACL":
            return await self._acl(resource.id, permission)
        return False

    @staticmethod
    def _output(resource: AppResourceModel) -> dict[str, object]:
        try:
            data = json.loads(resource.payload_json)
        except json.JSONDecodeError:
            data = {}
        return {
            "id": resource.uuid,
            "app_id": resource.app_id,
            "resource_type": resource.resource_type,
            "data_scope": resource.data_scope,
            "access_policy": resource.access_policy,
            "owner_space_id": resource.owner_space_id,
            "data": data if isinstance(data, dict) else {},
            "external_ref": resource.external_ref,
            "schema_version": resource.schema_version,
            "version": resource.version,
            "created_by_subject_id": resource.created_by_subject_id,
            "updated_by_subject_id": resource.updated_by_subject_id,
        }

    async def _audit(self, request_id: str, resource_type: str, action: str, result: str, reason: str, resource_id: str | None = None) -> None:
        self.db.add(
            AppDataAuditModel(
                request_id=request_id,
                app_id=self.principal.app_id,
                resource_type=resource_type,
                resource_id=resource_id,
                actor_subject_id=self.principal.subject_id,
                actor_membership_id=self.principal.membership_id,
                action=action,
                result=result,
                reason_code=reason,
            )
        )

    async def list(self, app_id: str, resource_type: str, request_id: str) -> list[dict[str, object]]:
        self._ensure_app(app_id, resource_type)
        self._ensure_scope(resource_type, "read")
        resources = (
            await self.db.execute(
                select(AppResourceModel).where(
                    AppResourceModel.app_id == self.principal.app_id,
                    AppResourceModel.resource_type == resource_type,
                    AppResourceModel.is_deleted.is_(False),
                ).order_by(AppResourceModel.id.asc())
            )
        ).scalars().all()
        visible = [self._output(resource) for resource in resources if await self._visible(resource)]
        await self._audit(request_id, resource_type, "read", "success", "LIST")
        return visible

    async def get(self, app_id: str, resource_type: str, resource_id: str, request_id: str) -> dict[str, object]:
        self._ensure_app(app_id, resource_type)
        self._ensure_scope(resource_type, "read")
        resource = await self.db.scalar(
            select(AppResourceModel).where(
                AppResourceModel.uuid == resource_id,
                AppResourceModel.app_id == self.principal.app_id,
                AppResourceModel.resource_type == resource_type,
                AppResourceModel.is_deleted.is_(False),
            )
        )
        if not resource or not await self._visible(resource):
            raise CustomException(msg="资源不存在", status_code=404)
        await self._audit(request_id, resource_type, "read", "success", "GET", resource.uuid)
        return self._output(resource)

    async def create(self, app_id: str, resource_type: str, data: AppResourceCreateSchema, request_id: str, idempotency_key: str | None) -> dict[str, object]:
        self._ensure_app(app_id, resource_type)
        self._ensure_scope(resource_type, "create", data.data_scope)
        if data.data_scope == "USER":
            owner_space_id = self.principal.space_id
            if data.access_policy == "TENANT_SHARED":
                raise CustomException(msg="USER 数据不能使用 TENANT_SHARED", status_code=422)
        else:
            owner_space_id = None
            if data.access_policy == "OWNER_ONLY":
                raise CustomException(msg="TENANT 数据不能使用 OWNER_ONLY", status_code=422)
        if data.access_policy == "ACL" and not data.acl:
            raise CustomException(msg="ACL 数据必须至少包含一条授权", status_code=422)
        if idempotency_key:
            existing = await self.db.scalar(
                select(AppResourceModel).where(
                    AppResourceModel.app_id == self.principal.app_id,
                    AppResourceModel.idempotency_key == idempotency_key,
                    AppResourceModel.is_deleted.is_(False),
                )
            )
            if existing:
                return self._output(existing)
        resource = AppResourceModel(
            app_id=self.principal.app_id,
            resource_type=resource_type,
            data_scope=data.data_scope,
            access_policy=data.access_policy,
            owner_space_id=owner_space_id,
            payload_json=json.dumps(data.data, ensure_ascii=False, sort_keys=True),
            external_ref=data.external_ref,
            schema_version=data.schema_version,
            version=1,
            idempotency_key=idempotency_key,
            created_by_subject_id=self.principal.subject_id,
            updated_by_subject_id=self.principal.subject_id,
        )
        self.db.add(resource)
        await self.db.flush()
        if data.access_policy == "ACL":
            acl = list(data.acl)
            if not any(item.subject_type == "USER" and item.subject_id == self.principal.subject_id for item in acl):
                acl.append(AppResourceAclInput(subject_type="USER", subject_id=self.principal.subject_id, permission="WRITE"))
            for item in acl:
                if item.subject_type == "USER" and item.subject_id != self.principal.subject_id:
                    raise CustomException(msg="当前 Token 不能替其他用户创建 ACL", status_code=403)
                self.db.add(
                    AppResourceAclModel(
                        resource_id=resource.id,
                        subject_type=item.subject_type,
                        subject_id=item.subject_id,
                        permission=item.permission,
                        granted_by_subject_id=self.principal.subject_id,
                    )
                )
        await self._audit(request_id, resource_type, "create", "success", "CREATE", resource.uuid)
        await self.db.flush()
        return self._output(resource)

    async def update(self, app_id: str, resource_type: str, resource_id: str, data: AppResourcePatchSchema, request_id: str, if_match: str | None) -> dict[str, object]:
        self._ensure_app(app_id, resource_type)
        self._ensure_scope(resource_type, "update")
        resource = await self.db.scalar(
            select(AppResourceModel).where(
                AppResourceModel.uuid == resource_id,
                AppResourceModel.app_id == self.principal.app_id,
                AppResourceModel.resource_type == resource_type,
                AppResourceModel.is_deleted.is_(False),
            )
        )
        if not resource or not await self._visible(resource, "WRITE"):
            raise CustomException(msg="资源不存在", status_code=404)
        if if_match and if_match.strip('"') != str(resource.version):
            raise CustomException(msg="资源版本冲突", status_code=409)
        resource.payload_json = json.dumps(data.data, ensure_ascii=False, sort_keys=True)
        resource.version += 1
        resource.updated_by_subject_id = self.principal.subject_id
        await self._audit(request_id, resource_type, "update", "success", "UPDATE", resource.uuid)
        await self.db.flush()
        return self._output(resource)

    async def delete(self, app_id: str, resource_type: str, resource_id: str, request_id: str) -> None:
        self._ensure_app(app_id, resource_type)
        self._ensure_scope(resource_type, "delete")
        resource = await self.db.scalar(
            select(AppResourceModel).where(
                AppResourceModel.uuid == resource_id,
                AppResourceModel.app_id == self.principal.app_id,
                AppResourceModel.resource_type == resource_type,
                AppResourceModel.is_deleted.is_(False),
            )
        )
        if not resource or not await self._visible(resource, "DELETE"):
            raise CustomException(msg="资源不存在", status_code=404)
        resource.is_deleted = True
        resource.updated_by_subject_id = self.principal.subject_id
        await self._audit(request_id, resource_type, "delete", "success", "DELETE", resource.uuid)
