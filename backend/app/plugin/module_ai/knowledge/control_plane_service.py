from __future__ import annotations

import hmac
from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_system.auth.schema import CloudControlPlaneBindSchema
from app.api.v1.module_system.user.model import UserModel
from app.core.database import async_db_session
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.utils.hash_bcrpy_util import PwdUtil

from ..config import settings
from ..secret import decrypt_secret, encrypt_secret
from .model import AiControlPlaneConfigModel

CLOUD_ENTERPRISE_OWNER_ROLE = "owner"


@dataclass(frozen=True, slots=True)
class CloudControlPlaneConfig:
    api_url: str
    instance_id: int
    service_credential: str
    timeout: float
    source: str


def build_control_plane_config(
    api_url: str,
    instance_id: int,
    service_credential: str,
    *,
    source: str,
) -> CloudControlPlaneConfig:
    normalized_url = api_url.strip().rstrip("/")
    if (
        not normalized_url
        or len(normalized_url) > 500
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in normalized_url)
    ):
        raise CustomException(msg="客户知识库未配置有效的云端成员服务地址", status_code=503)
    try:
        parsed = urlparse(normalized_url)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as exc:
        raise CustomException(msg="客户知识库未配置有效的云端成员服务地址", status_code=503) from exc
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or not hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise CustomException(msg="客户知识库未配置有效的云端成员服务地址", status_code=503)

    normalized_credential = service_credential.strip()
    if (
        instance_id <= 0
        or not normalized_credential
        or len(normalized_credential) > 256
        or any(character.isspace() or ord(character) < 32 or ord(character) == 127 for character in normalized_credential)
    ):
        raise CustomException(msg="客户知识库未配置有效的云端成员服务凭证", status_code=503)

    timeout = settings.KB_CONTROL_PLANE_TIMEOUT
    if timeout <= 0 or timeout > 60:
        raise CustomException(msg="客户知识库云端成员服务超时配置无效", status_code=503)
    return CloudControlPlaneConfig(
        api_url=normalized_url,
        instance_id=instance_id,
        service_credential=normalized_credential,
        timeout=timeout,
        source=source,
    )


def _environment_config() -> CloudControlPlaneConfig | None:
    try:
        return build_control_plane_config(
            settings.KB_CONTROL_PLANE_API_URL,
            settings.KB_CONTROL_PLANE_INSTANCE_ID or 0,
            settings.KB_CONTROL_PLANE_SERVICE_CREDENTIAL,
            source="environment",
        )
    except CustomException:
        return None


def _is_cloud_enterprise_owner(member: dict) -> bool:
    return str(member.get("role") or "").strip().casefold() == CLOUD_ENTERPRISE_OWNER_ROLE


async def _database_config(db: AsyncSession) -> CloudControlPlaneConfig | None:
    record = (
        await db.execute(
            select(AiControlPlaneConfigModel)
            .where(AiControlPlaneConfigModel.is_deleted.is_(False))
            .order_by(AiControlPlaneConfigModel.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if record is None:
        return None
    credential = decrypt_secret(record.encrypted_service_credential)
    if credential is None:
        return None
    try:
        return build_control_plane_config(record.api_url, record.instance_id, credential, source="database")
    except CustomException:
        return None


async def get_control_plane_config(db: AsyncSession | None = None) -> CloudControlPlaneConfig | None:
    if db is None:
        try:
            async with async_db_session() as session:
                database_config = await _database_config(session)
        except SQLAlchemyError:
            logger.warning("云面板绑定配置表不可用，回退到环境配置")
            database_config = None
    else:
        try:
            database_config = await _database_config(db)
        except SQLAlchemyError:
            await db.rollback()
            logger.warning("云面板绑定配置表不可用，回退到环境配置")
            database_config = None
    return database_config or _environment_config()


async def authenticate_control_plane_push(
    db: AsyncSession,
    service_credential: str | None,
) -> CloudControlPlaneConfig:
    """Validate the cloud panel's server-to-server push credential."""
    config = await get_control_plane_config(db=db)
    if config is None or not service_credential or not hmac.compare_digest(
        config.service_credential,
        service_credential,
    ):
        raise CustomException(msg="云面板服务凭证无效", code=10401, status_code=401)
    return config


async def bind_control_plane(db: AsyncSession, data: CloudControlPlaneBindSchema) -> dict[str, bool]:
    admin = (
        await db.execute(
            select(
                UserModel.id,
                UserModel.username,
                UserModel.password,
                UserModel.name,
                UserModel.email,
                UserModel.status,
                UserModel.is_superuser,
            ).where(
                UserModel.username == data.admin_username.strip(),
                UserModel.is_deleted.is_(False),
            )
        )
    ).mappings().one_or_none()
    if (
        admin is None
        or admin["status"] != 0
        or not admin["is_superuser"]
        or not PwdUtil.verify_password(data.admin_password, admin["password"])
    ):
        raise CustomException(msg="本地管理员账号或密码错误", code=10401, status_code=401)

    record = (
        await db.execute(
            select(AiControlPlaneConfigModel)
            .order_by(AiControlPlaneConfigModel.id.asc())
            .limit(1)
        )
    ).scalar_one_or_none()
    api_url = record.api_url if record is not None and record.api_url.strip() else settings.KB_CONTROL_PLANE_API_URL
    candidate = build_control_plane_config(
        api_url,
        data.instance_id,
        data.service_credential,
        source="request",
    )
    from .member_client import CloudMemberClient

    client = CloudMemberClient(config=candidate)
    members = await client.list_members()
    member_payload = {
        "username": admin["username"],
        "password": data.admin_password,
        "name": admin["name"],
        "status": admin["status"],
        "desktop_enabled": True,
        "knowledge_enabled": True,
        "model_enabled": True,
    }
    existing_admin = next(
        (
            member
            for member in members
            if str(member.get("username") or "").strip().lower() == str(admin["username"]).strip().lower()
        ),
        None,
    )
    if existing_admin is None:
        raise CustomException(
            msg="云面板中未找到对应的企业超管，请先在云面板创建并设置为企业超管后再绑定",
            status_code=403,
        )

    if existing_admin is not None:
        if not _is_cloud_enterprise_owner(existing_admin):
            raise CustomException(msg="云端绑定账号不是当前企业超管，不能完成绑定", status_code=403)
        try:
            cloud_user_id = int(existing_admin.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise CustomException(msg="云端管理员返回数据无效", status_code=502) from exc
        if cloud_user_id <= 0:
            raise CustomException(msg="云端管理员返回数据无效", status_code=502)
        await client.update_member(
            cloud_user_id,
            {key: value for key, value in member_payload.items() if key not in {"username", "password"}},
        )

    if record is None:
        record = AiControlPlaneConfigModel(
            api_url=candidate.api_url,
            instance_id=candidate.instance_id,
            encrypted_service_credential=encrypt_secret(candidate.service_credential),
        )
        db.add(record)
    else:
        record.api_url = candidate.api_url
        record.instance_id = candidate.instance_id
        record.encrypted_service_credential = encrypt_secret(candidate.service_credential)
        record.is_deleted = False
        record.deleted_time = None
    await db.flush()
    return {"configured": True}
