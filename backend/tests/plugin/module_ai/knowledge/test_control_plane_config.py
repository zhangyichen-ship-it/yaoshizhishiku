import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.api.v1.module_system.auth.schema import CloudControlPlaneBindSchema
from app.api.v1.module_system.user.model import UserModel
from app.core.exceptions import CustomException
from app.plugin.module_ai.knowledge import control_plane_service
from app.plugin.module_ai.knowledge.model import AiControlPlaneConfigModel
from app.plugin.module_ai.secret import decrypt_secret
from app.utils.hash_bcrpy_util import PwdUtil


def test_cloud_config_status_route_is_public(ai_client) -> None:
    response = ai_client.get("/system/auth/cloud-config/status")

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["available"] is True
    assert set(data) == {"available", "configured", "source"}


def test_control_plane_config_allows_local_endpoint_and_rejects_url_credentials(monkeypatch) -> None:
    monkeypatch.setattr(control_plane_service.settings, "KB_CONTROL_PLANE_TIMEOUT", 10.0)
    config = control_plane_service.build_control_plane_config(
        "http://127.0.0.1:9000/api/v1/platform/client/",
        7,
        "instance-secret",
        source="request",
    )
    assert config.api_url == "http://127.0.0.1:9000/api/v1/platform/client"

    with pytest.raises(CustomException):
        control_plane_service.build_control_plane_config(
            "https://user:password@cloud.example/api",
            7,
            "instance-secret",
            source="request",
        )


@pytest.mark.asyncio
async def test_bind_control_plane_uses_existing_cloud_admin_and_encrypts_credential(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'control-plane.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(UserModel.__table__.create)
        await connection.run_sync(AiControlPlaneConfigModel.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            UserModel(
                username="admin",
                password=PwdUtil.hash_password("admin123"),
                name="Administrator",
                email="admin@example.com",
                is_superuser=True,
                status=0,
            )
        )
        await db.flush()
        monkeypatch.setattr(control_plane_service.settings, "KB_CONTROL_PLANE_TIMEOUT", 10.0)
        monkeypatch.setattr(
            control_plane_service.settings,
            "KB_CONTROL_PLANE_API_URL",
            "http://127.0.0.1:9000/api/v1/platform/client",
        )

        async def fake_list_members(_client):
            return [
                {
                    "user_id": 101,
                    "username": "admin",
                    "name": "Administrator",
                    "role": "owner",
                }
            ]

        updated_call = {}

        async def fail_create_member(_client, _payload, _idempotency_key):
            raise AssertionError("initial binding must not create the cloud administrator")

        async def fake_update_member(_client, user_id, payload):
            updated_call.update(user_id=user_id, payload=payload)
            return {"user_id": user_id, "username": "admin", "name": "Administrator", "role": "owner"}

        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.list_members", fake_list_members)
        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.create_member", fail_create_member)
        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.update_member", fake_update_member)
        data = CloudControlPlaneBindSchema(
            admin_username="admin",
            admin_password="admin123",
            instance_id=7,
            service_credential="instance-secret",
        )

        assert await control_plane_service.bind_control_plane(db, data) == {"configured": True}
        assert updated_call == {
            "user_id": 101,
            "payload": {
                "name": "Administrator",
                "status": 0,
                "desktop_enabled": True,
                "knowledge_enabled": True,
                "model_enabled": True,
            },
        }
        await db.commit()

        record = await db.scalar(select(AiControlPlaneConfigModel))
        assert record is not None
        assert record.encrypted_service_credential != data.service_credential
        assert decrypt_secret(record.encrypted_service_credential) == data.service_credential

        assert await db.scalar(select(func.count(AiControlPlaneConfigModel.id))) == 1

    await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(("cloud_role", "update_allowed"), [("owner", True), ("member", False)])
async def test_bind_control_plane_validates_existing_cloud_admin_role(
    tmp_path,
    monkeypatch,
    cloud_role: str,
    update_allowed: bool,
) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'control-plane-update.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(UserModel.__table__.create)
        await connection.run_sync(AiControlPlaneConfigModel.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            UserModel(
                username="admin",
                password=PwdUtil.hash_password("admin123"),
                name="Administrator",
                email="admin@example.com",
                is_superuser=True,
                status=0,
            )
        )
        db.add(
            AiControlPlaneConfigModel(
                api_url="http://127.0.0.1:9000/api/v1/platform/client",
                instance_id=7,
                encrypted_service_credential=control_plane_service.encrypt_secret("old-secret"),
            )
        )
        await db.flush()
        monkeypatch.setattr(control_plane_service.settings, "KB_CONTROL_PLANE_TIMEOUT", 10.0)

        async def fake_list_members(_client):
            return [
                {
                    "user_id": 101,
                    "username": "admin",
                    "name": "Administrator",
                    "email": "admin@example.com",
                    "role": cloud_role,
                    "status": 0,
                    "desktop_enabled": True,
                    "knowledge_enabled": True,
                    "model_enabled": True,
                }
            ]

        updated_call = {}

        async def fake_update_member(_client, user_id, payload):
            updated_call.update(user_id=user_id, payload=payload)
            return {
                "user_id": user_id,
                "username": "admin",
                "name": "Administrator",
                "email": "admin@example.com",
                "role": "owner",
                "status": 0,
                "desktop_enabled": True,
                "knowledge_enabled": True,
                "model_enabled": True,
            }

        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.list_members", fake_list_members)
        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.update_member", fake_update_member)

        data = CloudControlPlaneBindSchema(
            admin_username="admin",
            admin_password="admin123",
            instance_id=7,
            service_credential="new-secret",
        )

        if update_allowed:
            assert await control_plane_service.bind_control_plane(db, data) == {"configured": True}
            assert updated_call == {
                "user_id": 101,
                "payload": {
                    "name": "Administrator",
                    "status": 0,
                    "desktop_enabled": True,
                    "knowledge_enabled": True,
                    "model_enabled": True,
                },
            }
            await db.commit()

            record = await db.scalar(select(AiControlPlaneConfigModel))
            assert record is not None
            assert decrypt_secret(record.encrypted_service_credential) == data.service_credential
        else:
            with pytest.raises(CustomException, match="企业超管"):
                await control_plane_service.bind_control_plane(db, data)
            assert updated_call == {}
            record = await db.scalar(select(AiControlPlaneConfigModel))
            assert record is not None
            assert decrypt_secret(record.encrypted_service_credential) == "old-secret"

    await engine.dispose()


@pytest.mark.asyncio
async def test_bind_control_plane_rejects_missing_cloud_admin(tmp_path, monkeypatch) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'control-plane-missing.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(UserModel.__table__.create)
        await connection.run_sync(AiControlPlaneConfigModel.__table__.create)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        db.add(
            UserModel(
                username="admin",
                password=PwdUtil.hash_password("admin123"),
                name="Administrator",
                email="admin@example.com",
                is_superuser=True,
                status=0,
            )
        )
        await db.flush()
        monkeypatch.setattr(control_plane_service.settings, "KB_CONTROL_PLANE_TIMEOUT", 10.0)
        monkeypatch.setattr(
            control_plane_service.settings,
            "KB_CONTROL_PLANE_API_URL",
            "http://127.0.0.1:9000/api/v1/platform/client",
        )

        async def fake_list_members(_client):
            return []

        async def fail_create_member(_client, _payload, _idempotency_key):
            raise CustomException(msg="云端员工已存在或幂等键冲突", status_code=409)

        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.list_members", fake_list_members)
        monkeypatch.setattr("app.plugin.module_ai.knowledge.member_client.CloudMemberClient.create_member", fail_create_member)

        data = CloudControlPlaneBindSchema(
            admin_username="admin",
            admin_password="admin123",
            instance_id=7,
            service_credential="instance-secret",
        )

        with pytest.raises(CustomException, match="云面板中未找到对应的企业超管") as exc_info:
            await control_plane_service.bind_control_plane(db, data)
        assert exc_info.value.status_code == 403
        assert await db.scalar(select(func.count(AiControlPlaneConfigModel.id))) == 0

    await engine.dispose()
