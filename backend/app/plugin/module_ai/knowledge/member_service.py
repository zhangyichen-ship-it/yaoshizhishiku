from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.base_schema import AuthSchema
from app.core.exceptions import CustomException

from ..config import settings
from .member_client import CloudMemberClient
from .model import KbMemberModel, KnowledgeBaseAccessModel, KnowledgeBaseModel
from .schema import (
    KbMemberCreateSchema,
    KbMemberOutSchema,
    KbMemberUpdateSchema,
    KnowledgeBaseAccessOutSchema,
    KnowledgeBaseAccessUpdateSchema,
)


class CustomerMemberService:
    """Own the local employee projection and customer-side knowledge ACL."""

    def __init__(self, auth: AuthSchema, client: CloudMemberClient | None = None) -> None:
        self.auth = auth
        self.client = client or CloudMemberClient()

    def _db(self):
        db = getattr(self.auth, "db", None)
        if db is None:
            raise CustomException(msg="客户知识库数据库会话不可用")
        return db

    @staticmethod
    def _remote_member_values(data: dict[str, Any]) -> dict[str, Any]:
        try:
            user_id = int(data.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise CustomException(msg="云端员工返回缺少有效用户ID", status_code=502) from exc
        username = str(data.get("username") or "").strip()
        name = str(data.get("name") or "").strip()
        if user_id <= 0 or not username or not name:
            raise CustomException(msg="云端员工返回格式错误", status_code=502)
        try:
            status = int(data.get("status", 1))
        except (TypeError, ValueError) as exc:
            raise CustomException(msg="云端员工状态格式错误", status_code=502) from exc
        if status not in (0, 1):
            raise CustomException(msg="云端员工状态格式错误", status_code=502)
        knowledge_enabled = data.get("knowledge_enabled", False)
        if not isinstance(knowledge_enabled, bool):
            raise CustomException(msg="云端员工权限格式错误", status_code=502)
        return {
            "cloud_user_id": user_id,
            "username": username,
            "name": name,
            "email": str(data["email"]) if data.get("email") else None,
            # Missing grants fail closed instead of silently becoming enabled.
            "cloud_status": status,
            "cloud_knowledge_enabled": knowledge_enabled,
            "last_synced_at": datetime.now(),
            "is_deleted": False,
            "deleted_time": None,
        }

    async def _upsert_member(self, data: dict[str, Any]) -> KbMemberModel:
        db = self._db()
        values = self._remote_member_values(data)
        same_username = (
            await db.execute(
                    select(KbMemberModel).where(
                        KbMemberModel.username == values["username"],
                        KbMemberModel.cloud_user_id != values["cloud_user_id"],
                    )
            )
        ).scalar_one_or_none()
        if same_username:
            raise CustomException(msg="本地员工映射与云端账号冲突", status_code=409)

        member = (
            await db.execute(
                select(KbMemberModel).where(KbMemberModel.cloud_user_id == values["cloud_user_id"])
            )
        ).scalar_one_or_none()
        if member is None:
            member = KbMemberModel(**values)
            db.add(member)
        else:
            for field, value in values.items():
                setattr(member, field, value)
        await db.flush()
        return member

    async def sync_member(self, data: dict[str, Any]) -> KbMemberModel:
        """Persist the minimal local projection returned by the control plane."""
        member = await self._upsert_member(data)
        bootstrap_user_id = settings.KB_BOOTSTRAP_CLOUD_USER_ID
        if (
            bootstrap_user_id
            and bootstrap_user_id > 0
            and member.cloud_user_id == bootstrap_user_id
            and member.cloud_status == 0
            and member.cloud_knowledge_enabled
        ):
            owner_exists = await self._db().scalar(
                select(KbMemberModel.id).where(
                    KbMemberModel.local_role == "owner",
                    KbMemberModel.is_deleted.is_(False),
                )
            )
            if owner_exists is None:
                member.local_role = "owner"
                await self._db().flush()
        return member

    async def _get_member(self, user_id: int) -> KbMemberModel:
        if user_id <= 0:
            raise CustomException(msg="云端用户ID不合法", status_code=422)
        member = (
            await self._db().execute(
                select(KbMemberModel).where(
                    KbMemberModel.cloud_user_id == user_id,
                    KbMemberModel.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if not member:
            raise CustomException(msg="本地员工映射不存在", status_code=404)
        return member

    async def _access_ids_by_member(self, member_ids: list[int]) -> dict[int, list[int]]:
        if not member_ids:
            return {}
        rows = (
            await self._db().execute(
                select(KnowledgeBaseAccessModel.member_id, KnowledgeBaseAccessModel.knowledge_base_id)
                .where(
                    KnowledgeBaseAccessModel.member_id.in_(member_ids),
                    KnowledgeBaseAccessModel.is_deleted.is_(False),
                )
                .order_by(KnowledgeBaseAccessModel.knowledge_base_id.asc())
            )
        ).all()
        result: dict[int, list[int]] = {}
        for member_id, knowledge_base_id in rows:
            result.setdefault(member_id, []).append(knowledge_base_id)
        return result

    @staticmethod
    def _output(member: KbMemberModel, knowledge_base_ids: list[int]) -> KbMemberOutSchema:
        return KbMemberOutSchema(
            id=member.id,
            uuid=member.uuid,
            created_time=member.created_time,
            updated_time=member.updated_time,
            is_deleted=member.is_deleted,
            deleted_time=member.deleted_time,
            user_id=member.cloud_user_id,
            username=member.username,
            name=member.name,
            email=member.email,
            status=member.cloud_status,
            knowledge_enabled=member.cloud_knowledge_enabled,
            local_role=member.local_role,
            knowledge_base_ids=knowledge_base_ids,
        )

    async def list_members(self) -> list[KbMemberOutSchema]:
        remote_members = await self.client.list_members()
        local_members = [await self._upsert_member(item) for item in remote_members]
        remote_user_ids = {item.cloud_user_id for item in local_members}
        stale_query = select(KbMemberModel).where(KbMemberModel.is_deleted.is_(False))
        if remote_user_ids:
            stale_query = stale_query.where(KbMemberModel.cloud_user_id.not_in(remote_user_ids))
        stale_members = (await self._db().execute(stale_query)).scalars().all()
        for member in stale_members:
            member.cloud_status = 1
            member.cloud_knowledge_enabled = False
            member.last_synced_at = datetime.now()
        access_map = await self._access_ids_by_member([item.id for item in local_members])
        # GET normally rolls back its request session.  This endpoint performs
        # an intentional directory projection sync, so persist that projection.
        await self._db().commit()
        return [self._output(item, access_map.get(item.id, [])) for item in local_members]

    async def create_member(self, data: KbMemberCreateSchema, idempotency_key: str | None) -> KbMemberOutSchema:
        key = (idempotency_key or f"kb-member:{data.username}").strip()
        if not key or len(key) > 128:
            raise CustomException(msg="幂等键不合法", status_code=422)
        remote = await self.client.create_member(data.model_dump(mode="json", exclude_none=True), key)
        member = await self._upsert_member(remote)
        return self._output(member, (await self._access_ids_by_member([member.id])).get(member.id, []))

    async def update_member(self, user_id: int, data: KbMemberUpdateSchema) -> KbMemberOutSchema:
        payload = data.model_dump(mode="json", exclude_unset=True)
        if not payload:
            raise CustomException(msg="至少需要修改一项员工信息", status_code=422)
        remote = await self.client.update_member(user_id, payload)
        member = await self._upsert_member(remote)
        return self._output(member, (await self._access_ids_by_member([member.id])).get(member.id, []))

    async def get_access(self, user_id: int) -> KnowledgeBaseAccessOutSchema:
        member = await self._get_member(user_id)
        access_map = await self._access_ids_by_member([member.id])
        return KnowledgeBaseAccessOutSchema(user_id=user_id, knowledge_base_ids=access_map.get(member.id, []))

    async def set_access(self, user_id: int, data: KnowledgeBaseAccessUpdateSchema) -> KnowledgeBaseAccessOutSchema:
        db = self._db()
        member = await self._get_member(user_id)
        normalized_ids: list[int] = []
        for knowledge_base_id in data.knowledge_base_ids:
            if knowledge_base_id <= 0:
                raise CustomException(msg="知识库ID不合法", status_code=422)
            if knowledge_base_id not in normalized_ids:
                normalized_ids.append(knowledge_base_id)

        if normalized_ids:
            existing_base_ids = set(
                (
                    await db.execute(
                        select(KnowledgeBaseModel.id).where(
                            KnowledgeBaseModel.id.in_(normalized_ids),
                            KnowledgeBaseModel.is_deleted.is_(False),
                        )
                    )
                ).scalars().all()
            )
            if existing_base_ids != set(normalized_ids):
                raise CustomException(msg="知识库不存在或无权授权", status_code=404)

        grants = (
            await db.execute(
                select(KnowledgeBaseAccessModel).where(
                    KnowledgeBaseAccessModel.member_id == member.id,
                )
            )
        ).scalars().all()
        grants_by_base = {grant.knowledge_base_id: grant for grant in grants}
        now = datetime.now()
        operator = getattr(self.auth, "user", None)
        operator_id = None if getattr(operator, "auth_source", None) == "cloud_kb" else getattr(operator, "id", None)
        for knowledge_base_id in normalized_ids:
            grant = grants_by_base.get(knowledge_base_id)
            if grant is None:
                db.add(
                    KnowledgeBaseAccessModel(
                        member_id=member.id,
                        knowledge_base_id=knowledge_base_id,
                        granted_by_id=operator_id,
                    )
                )
            else:
                grant.is_deleted = False
                grant.deleted_time = None
                grant.updated_time = now
                grant.granted_by_id = operator_id

        for knowledge_base_id, grant in grants_by_base.items():
            if knowledge_base_id not in normalized_ids and not grant.is_deleted:
                grant.is_deleted = True
                grant.deleted_time = now
                grant.updated_time = now

        await db.flush()
        return KnowledgeBaseAccessOutSchema(user_id=user_id, knowledge_base_ids=normalized_ids)

    async def accessible_knowledge_base_ids(self, ids: list[int] | None) -> list[int] | None:
        """Return IDs allowed by the local ACL, failing closed for employees."""
        normalized = list(dict.fromkeys(ids or []))
        if any(item <= 0 for item in normalized):
            raise CustomException(msg="知识库ID不合法", status_code=422)

        user = getattr(self.auth, "user", None)
        db = getattr(self.auth, "db", None)
        if user is None or db is None:
            # Internal indexing/tests without an authenticated request keep the
            # existing behavior; all HTTP routes have AuthPermission first.
            return normalized if ids is not None else None
        if getattr(user, "is_superuser", False):
            return normalized if ids is not None else None
        if not normalized and ids is not None:
            return []

        raw_cloud_user_id = getattr(user, "cloud_user_id", None)
        try:
            cloud_user_id = int(raw_cloud_user_id)
        except (TypeError, ValueError) as exc:
            raise CustomException(msg="当前会话未绑定云端员工", status_code=403) from exc
        member = (
            await db.execute(
                select(KbMemberModel).where(
                    KbMemberModel.cloud_user_id == cloud_user_id,
                    KbMemberModel.is_deleted.is_(False),
                )
            )
        ).scalar_one_or_none()
        if not member or member.cloud_status != 0 or not member.cloud_knowledge_enabled:
            raise CustomException(msg="当前员工未开通知识库或已被停用", status_code=403)

        allowed_query = (
            select(KnowledgeBaseAccessModel.knowledge_base_id)
            .join(KnowledgeBaseModel, KnowledgeBaseModel.id == KnowledgeBaseAccessModel.knowledge_base_id)
            .where(
                KnowledgeBaseAccessModel.member_id == member.id,
                KnowledgeBaseAccessModel.is_deleted.is_(False),
                KnowledgeBaseModel.is_deleted.is_(False),
                KnowledgeBaseModel.is_enabled.is_(True),
            )
        )
        allowed = set((await db.execute(allowed_query)).scalars().all())
        if ids is not None:
            if allowed != set(normalized) or len(allowed) != len(normalized):
                raise CustomException(msg="知识库不存在或无权访问", status_code=403)
            return normalized
        return sorted(allowed)
