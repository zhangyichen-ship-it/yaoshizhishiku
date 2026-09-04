from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.module_system.user.model import UserModel
from app.core.exceptions import CustomException
from app.plugin.module_ai.knowledge.member_service import CustomerMemberService
from app.plugin.module_ai.knowledge.model import (
    KbMemberModel,
    KnowledgeBaseAccessModel,
    KnowledgeBaseModel,
)
from app.plugin.module_ai.knowledge.schema import KnowledgeBaseAccessUpdateSchema


def test_cloud_member_projection_does_not_store_credentials() -> None:
    values = CustomerMemberService._remote_member_values(
        {
            "user_id": 101,
            "username": "alice",
            "name": "Alice",
            "password": "must-not-be-persisted",
        }
    )

    assert "password" not in values
    assert values["cloud_knowledge_enabled"] is False


def test_cloud_kb_admin_permissions_are_local_role_scoped() -> None:
    from app.core.dependencies import _cloud_kb_permission_map

    employee_permissions = _cloud_kb_permission_map(
        SimpleNamespace(local_role="member"),
        {"knowledge_enabled": True, "model_enabled": False},
    )
    owner_permissions = _cloud_kb_permission_map(
        SimpleNamespace(local_role="owner"),
        {"knowledge_enabled": True, "model_enabled": False},
    )

    assert "module_ai:member:create" not in employee_permissions
    assert "module_ai:member:create" in owner_permissions
    assert "module_ai:access:update" in owner_permissions


@pytest.mark.asyncio
async def test_bootstrap_assigns_only_the_configured_customer_owner(tmp_path, monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import member_service as member_service_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'member-bootstrap.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(KbMemberModel.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        monkeypatch.setattr(member_service_module.settings, "KB_BOOTSTRAP_CLOUD_USER_ID", 101)
        service = CustomerMemberService(SimpleNamespace(db=db))
        owner = await service.sync_member(
            {"user_id": 101, "username": "owner", "name": "Owner", "status": 0, "knowledge_enabled": True}
        )
        employee = await service.sync_member(
            {"user_id": 102, "username": "employee", "name": "Employee", "status": 0, "knowledge_enabled": True}
        )

        assert owner.local_role == "owner"
        assert employee.local_role == "member"

    await engine.dispose()


@pytest.mark.asyncio
async def test_cloud_embedding_config_uses_instance_endpoint_without_provider_key(monkeypatch) -> None:
    from app.plugin.module_ai.knowledge import member_client as member_client_module

    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200
        is_success = True

        def json(self):
            return {
                "success": True,
                "data": {
                    "provider": "openai",
                    "model": "text-embedding-3-small",
                    "base_url": "https://embedding.example/v1",
                    "api_key": "must-not-be-used",
                },
            }

    class FakeClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def request(self, method, url, *, headers, json):
            captured.update(method=method, url=url, headers=headers, json=json)
            return FakeResponse()

    monkeypatch.setattr(member_client_module.httpx, "AsyncClient", FakeClient)
    monkeypatch.setattr(member_client_module.settings, "KB_CONTROL_PLANE_API_URL", "https://cloud.example/api")
    monkeypatch.setattr(member_client_module.settings, "KB_CONTROL_PLANE_INSTANCE_ID", 7)
    monkeypatch.setattr(member_client_module.settings, "KB_CONTROL_PLANE_SERVICE_CREDENTIAL", "instance-secret")

    result = await member_client_module.CloudMemberClient().get_embedding_config()

    assert result == {
        "provider": "openai",
        "model": "text-embedding-3-small",
        "base_url": "https://embedding.example/v1",
    }
    assert captured["method"] == "GET"
    assert captured["url"] == "https://cloud.example/api/kb-instances/7/embedding-config"
    assert captured["headers"] == {"Authorization": "Bearer instance-secret"}


@pytest.mark.asyncio
async def test_acl_enforces_cloud_product_grant_and_replaces_access(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'member-access.db'}")
    async with engine.begin() as connection:
        for table in (
            UserModel.__table__,
            KnowledgeBaseModel.__table__,
            KbMemberModel.__table__,
            KnowledgeBaseAccessModel.__table__,
        ):
            await connection.run_sync(table.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        operator = UserModel(username="operator", password="hash", name="Operator")
        member = KbMemberModel(
            cloud_user_id=101,
            username="alice",
            name="Alice",
            cloud_status=0,
            cloud_knowledge_enabled=True,
        )
        first = KnowledgeBaseModel(name="First", is_enabled=True)
        second = KnowledgeBaseModel(name="Second", is_enabled=True)
        db.add_all([operator, member, first, second])
        await db.flush()
        db.add(
            KnowledgeBaseAccessModel(
                member_id=member.id,
                knowledge_base_id=first.id,
                granted_by_id=operator.id,
            )
        )
        await db.commit()

        auth = SimpleNamespace(
            db=db,
            user=SimpleNamespace(
                id=operator.id,
                cloud_user_id=member.cloud_user_id,
                is_superuser=False,
            ),
        )
        service = CustomerMemberService(auth)

        assert await service.accessible_knowledge_base_ids(None) == [first.id]
        with pytest.raises(CustomException) as error:
            await service.accessible_knowledge_base_ids([second.id])
        assert error.value.status_code == 403

        await service.set_access(
            member.cloud_user_id,
            KnowledgeBaseAccessUpdateSchema(knowledge_base_ids=[second.id]),
        )
        await db.commit()

        assert await service.accessible_knowledge_base_ids(None) == [second.id]
        grants = (
            await db.execute(
                select(KnowledgeBaseAccessModel).where(
                    KnowledgeBaseAccessModel.member_id == member.id,
                )
            )
        ).scalars().all()
        assert {grant.knowledge_base_id for grant in grants if not grant.is_deleted} == {second.id}
        assert {grant.knowledge_base_id for grant in grants if grant.is_deleted} == {first.id}

        class EmptyCloudClient:
            async def list_members(self):
                return []

        assert await CustomerMemberService(auth, client=EmptyCloudClient()).list_members() == []
        refreshed_member = await db.scalar(select(KbMemberModel).where(KbMemberModel.id == member.id))
        assert refreshed_member is not None
        assert refreshed_member.cloud_status == 1
        assert refreshed_member.cloud_knowledge_enabled is False

    await engine.dispose()
