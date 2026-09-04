
import hashlib
import json
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Any, NewType

import ua_parser
from fastapi import Request
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.module_system.user.crud import UserCRUD
from app.api.v1.module_system.user.model import UserModel
from app.common.enums import RedisInitKeyConfig
from app.config.setting import settings
from app.core.base_schema import (
    AuthSchema,
    JWTOutSchema,
    JWTPayloadSchema,
    RefreshTokenPayloadSchema,
)
from app.core.client_ip import get_client_ip
from app.core.exceptions import CustomException
from app.core.logger import logger
from app.core.redis_crud import RedisCURD
from app.core.security import (
    CustomOAuth2PasswordRequestForm,
    create_access_token,
    decode_access_token,
)
from app.utils.captcha_util import CaptchaUtil
from app.utils.common_util import get_random_character
from app.utils.hash_bcrpy_util import PwdUtil
from app.utils.ip_local_util import IpLocalUtil

from .schema import (
    AutoLoginTokenSchema,
    AutoLoginUserSchema,
    CaptchaOutSchema,
    LoginSchema,
)

CaptchaKey = NewType("CaptchaKey", str)
CaptchaBase64 = NewType("CaptchaBase64", str)


async def _write_login_log(
    username: str,
    status: int,
    login_ip: str | None = None,
    login_location: str | None = None,
    request_os: str | None = None,
    request_browser: str | None = None,
    msg: str | None = None,
) -> None:
    """写入登录日志（独立 session，避免事务回滚时丢失失败记录）"""
    from app.api.v1.module_system.log.crud import LoginLogCRUD
    from app.api.v1.module_system.log.schema import LoginLogCreateSchema
    from app.core.base_schema import AuthSchema
    from app.core.database import async_db_session

    try:
        async with async_db_session() as session:
            async with session.begin():
                _auth = AuthSchema(db=session, check_data_scope=False)
                await LoginLogCRUD(_auth).create(data=LoginLogCreateSchema(
                    username=username,
                    status=status,
                    login_ip=login_ip,
                    login_location=login_location,
                    request_os=request_os,
                    request_browser=request_browser,
                    msg=msg,
                ))
    except Exception:
        pass  # 登录日志写入失败不影响登录主流程


def _resolve_request_ip(request: Request) -> str:
    """从请求中解析客户端真实 IP"""
    return get_client_ip(request)


def _login_subject_digest(username: str, request_ip: str) -> str:
    """Hash the login subject and trusted client address for Redis keys."""
    subject = f"{username.strip().lower()}\x00{request_ip.strip()}"
    return hashlib.sha256(subject.encode("utf-8")).hexdigest()


def _login_failure_key(username: str, request_ip: str) -> str:
    """Return a Redis key that does not expose raw login input."""
    digest = _login_subject_digest(username, request_ip)
    return f"auth:login:failure:{digest}"


def _login_lock_key(username: str, request_ip: str) -> str:
    """Return the short-lived Redis account-lock key."""
    digest = _login_subject_digest(username, request_ip)
    return f"auth:login:lock:{digest}"


async def _get_login_failure_count(redis: Redis, username: str, request_ip: str) -> int:
    """Read the current failed-login counter for one account/client pair."""
    if await RedisCURD(redis).exists(_login_lock_key(username, request_ip)):
        return settings.LOGIN_MAX_FAILURES
    value = await RedisCURD(redis).get(_login_failure_key(username, request_ip))
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="ignore")
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


async def _record_login_failure(redis: Redis, username: str, request_ip: str) -> int:
    """Increment and expire an account failure counter.

    Redis' atomic ``INCR`` is preferred; the fallback keeps lightweight test
    doubles and nonstandard Redis clients functional.
    """
    key = _login_failure_key(username, request_ip)
    try:
        count = int(await redis.incr(key))
        await redis.expire(key, settings.LOGIN_FAILURE_WINDOW_SECONDS)
        if count >= settings.LOGIN_MAX_FAILURES:
            await RedisCURD(redis).set(
                _login_lock_key(username, request_ip),
                "1",
                expire=settings.LOGIN_LOCK_SECONDS,
            )
        return count
    except (AttributeError, TypeError, ValueError):
        count = await _get_login_failure_count(redis, username, request_ip) + 1
        await RedisCURD(redis).set(key, str(count), expire=settings.LOGIN_FAILURE_WINDOW_SECONDS)
        if count >= settings.LOGIN_MAX_FAILURES:
            await RedisCURD(redis).set(
                _login_lock_key(username, request_ip),
                "1",
                expire=settings.LOGIN_LOCK_SECONDS,
            )
        return count


async def _clear_login_failures(redis: Redis, username: str, request_ip: str) -> None:
    """Clear the account/client failure counter after a successful login."""
    await RedisCURD(redis).delete(
        _login_failure_key(username, request_ip),
        _login_lock_key(username, request_ip),
    )


def _locked_message() -> str:
    """Return the stable client-facing account lock message."""
    return "登录失败次数过多，请稍后再试"


class LoginService:
    """登录认证服务"""

    def __init__(self, auth: AuthSchema | None = None) -> None:
        self.auth = auth

    @classmethod
    async def authenticate_user(
        cls,
        request: Request,
        redis: Redis,
        login_form: CustomOAuth2PasswordRequestForm,
        db: AsyncSession,
    ) -> LoginSchema:
        """用户认证"""
        ua_result = ua_parser.parse(request.headers.get("user-agent"))
        request_ip = _resolve_request_ip(request)
        login_location = await IpLocalUtil.resolve_location_for_log(request_ip)
        _login_os = ua_result.os.family if ua_result.os else "Unknown"
        _login_browser = ua_result.user_agent.family if ua_result.user_agent else "Unknown"
        _login_username = login_form.username

        failure_count = await _get_login_failure_count(redis, _login_username, request_ip)
        if failure_count >= settings.LOGIN_MAX_FAILURES:
            raise CustomException(msg=_locked_message(), status_code=429)

        captcha_required = settings.CAPTCHA_ENABLE or failure_count >= settings.LOGIN_CAPTCHA_AFTER_FAILURES
        if captcha_required:
            if not login_form.captcha_key or not login_form.captcha:
                await _record_login_failure(redis, _login_username, request_ip)
                raise CustomException(msg="验证码不能为空", status_code=429 if failure_count + 1 >= settings.LOGIN_MAX_FAILURES else 400)
            try:
                await CaptchaService.check_captcha(
                    redis=redis,
                    key=login_form.captcha_key,
                    captcha=login_form.captcha,
                )
            except CustomException:
                await _record_login_failure(redis, _login_username, request_ip)
                raise

        auth = AuthSchema(db=db, check_data_scope=False)
        user = await UserCRUD(auth).get(username=login_form.username)

        if not user:
            failure_count = await _record_login_failure(redis, _login_username, request_ip)
            await _write_login_log(
                username=_login_username,
                status=2,
                login_ip=request_ip,
                login_location=login_location,
                request_os=_login_os,
                request_browser=_login_browser,
                msg="用户不存在",
            )
            raise CustomException(
                msg=_locked_message() if failure_count >= settings.LOGIN_MAX_FAILURES else "账号或密码错误",
                status_code=429 if failure_count >= settings.LOGIN_MAX_FAILURES else 401,
            )

        if not PwdUtil.verify_password(plain_password=login_form.password, password_hash=user.password):
            failure_count = await _record_login_failure(redis, _login_username, request_ip)
            await _write_login_log(
                username=_login_username,
                status=2,
                login_ip=request_ip,
                login_location=login_location,
                request_os=_login_os,
                request_browser=_login_browser,
                msg="账号或密码错误",
            )
            raise CustomException(
                msg=_locked_message() if failure_count >= settings.LOGIN_MAX_FAILURES else "账号或密码错误",
                status_code=429 if failure_count >= settings.LOGIN_MAX_FAILURES else 401,
            )
        if user.status == 1:
            await _write_login_log(
                username=_login_username,
                status=2,
                login_ip=request_ip,
                login_location=login_location,
                request_os=_login_os,
                request_browser=_login_browser,
                msg="用户已被停用",
            )
            raise CustomException(msg="用户已被停用")
        await _clear_login_failures(redis, _login_username, request_ip)
        await UserCRUD(auth).update_last_login(id=user.id)

        if not user:
            raise CustomException(msg="用户不存在")
        if not login_form.login_type:
            raise CustomException(msg="登录类型不能为空")

        token = await cls.create_token(
            request=request,
            redis=redis,
            user=user,
            login_type=login_form.login_type,
        )
        user_info = {
            "id": user.id,
            "username": user.username,
            "name": user.name,
            "avatar": user.avatar,
            "is_superuser": user.is_superuser,
        }

        await _write_login_log(
            username=user.username,
            status=1,
            login_ip=request_ip,
            login_location=login_location,
            request_os=_login_os,
            request_browser=_login_browser,
            msg="登录成功",
        )

        return LoginSchema(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_in=token.expires_in,
            token_type=token.token_type,
            user_info=user_info,
        )

    @classmethod
    async def authenticate_cloud_user(
        cls,
        request: Request,
        redis: Redis,
        db: AsyncSession,
        identity: str,
        password: str,
    ) -> LoginSchema:
        """Exchange cloud credentials and create only a local KB session."""
        from app.plugin.module_ai.knowledge.member_client import CloudMemberClient

        client = CloudMemberClient()
        result = await client.login_member(identity.strip(), password)
        return await cls._create_cloud_session(
            request=request,
            redis=redis,
            db=db,
            client=client,
            result=result,
        )

    @classmethod
    async def authenticate_cloud_identity(
        cls,
        request: Request,
        redis: Redis,
        db: AsyncSession,
        identity_token: str,
        refresh_token: str,
    ) -> LoginSchema:
        """Exchange a control-plane identity pair into a local KB session."""
        from app.plugin.module_ai.knowledge.member_client import CloudMemberClient

        client = CloudMemberClient()
        cloud_identity_token = identity_token.strip()
        cloud_refresh_token = refresh_token.strip()
        if not cloud_identity_token or not cloud_refresh_token:
            raise CustomException(msg="云端身份凭证不能为空", code=10401, status_code=401)
        try:
            remote_user = await client.introspect_identity(cloud_identity_token)
        except CustomException as exc:
            if exc.status_code != 401:
                raise
            refreshed = await client.refresh_identity(cloud_refresh_token)
            cloud_identity_token = str(refreshed.get("identity_token") or "").strip()
            remote_user = refreshed.get("user")
            if not cloud_identity_token or not isinstance(remote_user, dict):
                raise CustomException(msg="云端身份会话已失效，请重新登录", code=10401, status_code=401) from exc

        if not isinstance(remote_user, dict):
            raise CustomException(msg="云端员工信息格式错误", status_code=502)
        return await cls._create_cloud_session(
            request=request,
            redis=redis,
            db=db,
            client=client,
            result={
                "user": remote_user,
                "identity_token": cloud_identity_token,
                "refresh_token": cloud_refresh_token,
            },
        )

    @classmethod
    async def _create_cloud_session(
        cls,
        request: Request,
        redis: Redis,
        db: AsyncSession,
        client: Any,
        result: dict[str, Any],
    ) -> LoginSchema:
        from app.plugin.module_ai.knowledge.member_service import CustomerMemberService

        remote_user = result["user"]
        if (
            not isinstance(remote_user, dict)
            or remote_user.get("status") != 0
            or not remote_user.get("knowledge_enabled")
        ):
            raise CustomException(msg="当前员工未开通知识库或已被停用", code=10403, status_code=403)
        member = await CustomerMemberService(
            AuthSchema(db=db, check_data_scope=False),
            client=client,
        ).sync_member(remote_user)
        user_info = {
            "id": member.id,
            "user_id": member.id,
            "kb_member_id": member.id,
            "cloud_user_id": member.cloud_user_id,
            "username": member.username,
            "user_name": member.username,
            "name": member.name,
            "email": member.email,
            "is_superuser": False,
            "status": member.cloud_status,
            "desktop_enabled": bool(remote_user.get("desktop_enabled")),
            "knowledge_enabled": bool(remote_user.get("knowledge_enabled")),
            "model_enabled": bool(remote_user.get("model_enabled")),
            "auth_source": "cloud_kb",
            "cloud_identity_token": result["identity_token"],
            "cloud_identity_refresh_token": result["refresh_token"],
        }
        token = await cls.create_external_token(
            request=request,
            redis=redis,
            user_info=user_info,
        )
        public_user_info = {
            key: value
            for key, value in user_info.items()
            if key not in {"cloud_identity_token", "cloud_identity_refresh_token"}
        }
        return LoginSchema(
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            expires_in=token.expires_in,
            token_type=token.token_type,
            user_info=public_user_info,
        )

    @classmethod
    async def _create_session_tokens(
        cls,
        *,
        request: Request | None,
        redis: Redis,
        user_info: dict[str, Any],
        login_type: str,
        session_id: str | None = None,
    ) -> JWTOutSchema:
        """Create the local KB session for either a local admin or cloud employee."""
        session_id = session_id or str(uuid.uuid4())
        now = datetime.now()

        if request is not None:
            request_ip = _resolve_request_ip(request)
            login_location = await IpLocalUtil.resolve_location_for_log(request_ip)

            from dataclasses import replace

            from app.core.request_context import RequestContext

            base_ctx = getattr(request.state, "ctx", None) or RequestContext()
            request.state.ctx = replace(
                base_ctx,
                session_id=session_id,
                user_username=str(user_info.get("username") or user_info.get("user_name") or ""),
                login_location=login_location,
            )

        access_expires = timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = timedelta(seconds=settings.REFRESH_TOKEN_EXPIRE_MINUTES)

        session_info = {
            **user_info,
            "session_id": session_id,
            "user_name": user_info.get("user_name") or user_info.get("username"),
            "login_type": login_type,
            "login_time": user_info.get("login_time") or now.isoformat(),
        }
        access_token = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=False,
                exp=now + access_expires,
                jti=secrets.token_urlsafe(16),
            )
        )
        refresh_token = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=True,
                exp=now + refresh_expires,
                jti=secrets.token_urlsafe(16),
            )
        )

        await RedisCURD(redis).set(
            key=f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}",
            value=access_token,
            expire=int(access_expires.total_seconds()),
        )

        await RedisCURD(redis).set(
            key=f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}",
            value=refresh_token,
            expire=int(refresh_expires.total_seconds()),
        )

        await RedisCURD(redis).set(
            key=f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}",
            value=session_info,
            expire=int(refresh_expires.total_seconds()),
        )

        return JWTOutSchema(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=int(access_expires.total_seconds()),
            token_type=settings.TOKEN_TYPE,
        )

    @classmethod
    async def create_token(cls, request: Request, redis: Redis, user: UserModel, login_type: str) -> JWTOutSchema:
        """创建本地管理员访问令牌和刷新令牌。"""
        return await cls._create_session_tokens(
            request=request,
            redis=redis,
            user_info={
                "user_id": user.id,
                "username": user.username,
                "user_name": user.username,
            },
            login_type=login_type,
        )

    @classmethod
    async def create_external_token(
        cls,
        request: Request,
        redis: Redis,
        user_info: dict[str, Any],
        login_type: str = "cloud_kb",
    ) -> JWTOutSchema:
        """Create a local session without copying a cloud employee password."""
        if not user_info.get("cloud_user_id") or not user_info.get("cloud_identity_token"):
            raise CustomException(msg="云端身份信息不完整", status_code=502)
        if not str(user_info.get("username") or "").strip():
            raise CustomException(msg="云端员工信息不完整", status_code=502)
        return await cls._create_session_tokens(
            request=request,
            redis=redis,
            user_info=user_info,
            login_type=login_type,
        )

    @classmethod
    async def refresh_token(
        cls,
        db: AsyncSession,
        redis: Redis,
        refresh_token: RefreshTokenPayloadSchema,
    ) -> JWTOutSchema:
        """刷新访问令牌"""
        token_payload: JWTPayloadSchema = decode_access_token(token=refresh_token.refresh_token)
        if not token_payload.is_refresh:
            raise CustomException(msg="非法凭证，请传入刷新令牌")

        session_id = token_payload.sub
        session_info = await RedisCURD(redis).get(
            f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}"
        )
        if not session_info:
            raise CustomException(msg="会话已过期，请重新登录")

        try:
            session_data = json.loads(session_info)
        except (TypeError, json.JSONDecodeError):
            raise CustomException(msg="会话已失效，请重新登录")

        if session_data.get("auth_source") == "cloud_kb":
            cloud_identity_token = str(session_data.get("cloud_identity_token") or "")
            cloud_refresh_token = str(session_data.get("cloud_identity_refresh_token") or "")
            if not cloud_identity_token or not cloud_refresh_token:
                raise CustomException(msg="云端身份会话已失效，请重新登录", code=10401, status_code=401)

            from app.plugin.module_ai.knowledge.member_client import CloudMemberClient
            from app.plugin.module_ai.knowledge.member_service import CustomerMemberService

            client = CloudMemberClient()
            try:
                remote_user = await client.introspect_identity(cloud_identity_token)
            except CustomException as exc:
                if exc.status_code != 401:
                    raise
                refreshed = await client.refresh_identity(cloud_refresh_token)
                cloud_identity_token = str(refreshed.get("identity_token") or "")
                remote_user = refreshed.get("user")
                if not cloud_identity_token or not isinstance(remote_user, dict):
                    raise CustomException(msg="云端身份会话已失效，请重新登录", code=10401, status_code=401) from exc

            member = await CustomerMemberService(AuthSchema(db=db, check_data_scope=False), client=client).sync_member(remote_user)
            session_data.update(
                {
                    "user_id": member.id,
                    "username": member.username,
                    "user_name": member.username,
                    "cloud_user_id": member.cloud_user_id,
                    "kb_member_id": member.id,
                    "cloud_identity_token": cloud_identity_token,
                    "cloud_identity_refresh_token": cloud_refresh_token,
                }
            )
            refresh_key = f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}"
            if not await RedisCURD(redis).compare_and_delete(refresh_key, refresh_token.refresh_token):
                raise CustomException(msg="刷新令牌已失效，请重新登录")
            return await cls._create_session_tokens(
                request=None,
                redis=redis,
                user_info=session_data,
                login_type=str(session_data.get("login_type") or "cloud_kb"),
                session_id=session_id,
            )

        user_id = session_data.get("user_id")

        if not session_id or not user_id:
            raise CustomException(msg="非法凭证,无法获取会话编号或用户ID")

        auth = AuthSchema(db=db, check_data_scope=False)
        user = await UserCRUD(auth).get(id=user_id)
        if not user:
            raise CustomException(msg="刷新token失败，用户不存在")
        if user.status == 1:
            raise CustomException(msg="用户已被停用")

        refresh_key = f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}"
        if not await RedisCURD(redis).compare_and_delete(refresh_key, refresh_token.refresh_token):
            raise CustomException(msg="刷新令牌已失效，请重新登录")

        access_expires = timedelta(seconds=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        refresh_expires = timedelta(seconds=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
        now = datetime.now()

        # 延长会话信息 Redis TTL
        await RedisCURD(redis).expire(
            key=f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}",
            expire=int(refresh_expires.total_seconds()),
        )

        access_token = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=False,
                exp=now + access_expires,
                jti=secrets.token_urlsafe(16),
            )
        )

        refresh_token_new = create_access_token(
            payload=JWTPayloadSchema(
                sub=session_id,
                is_refresh=True,
                exp=now + refresh_expires,
                jti=secrets.token_urlsafe(16),
            )
        )

        await RedisCURD(redis).set(
            key=f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}",
            value=access_token,
            expire=int(access_expires.total_seconds()),
        )

        await RedisCURD(redis).set(
            key=refresh_key,
            value=refresh_token_new,
            expire=int(refresh_expires.total_seconds()),
        )

        return JWTOutSchema(
            access_token=access_token,
            refresh_token=refresh_token_new,
            token_type=settings.TOKEN_TYPE,
            expires_in=int(access_expires.total_seconds()),
        )

    @staticmethod
    async def logout(redis: Redis, session_id: str) -> bool:
        """Revoke only the session authenticated by the current request."""
        if not session_id:
            raise CustomException(msg="非法凭证,无法获取会话编号")

        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.ACCESS_TOKEN.key}:{session_id}")
        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.REFRESH_TOKEN.key}:{session_id}")
        await RedisCURD(redis).delete(f"{RedisInitKeyConfig.USER_SESSION.key}:{session_id}")

        logger.info(f"用户退出登录成功,会话编号:{session_id}")

        return True

    @staticmethod
    async def create_ws_ticket(redis: Redis, session_id: str) -> str:
        """Issue a short-lived, one-time ticket for a WebSocket upgrade.

        Args:
            redis: Redis connection used for the ticket store.
            session_id: Session belonging to the already authenticated request.

        Returns:
            Opaque ticket value that may be consumed exactly once.
        """
        if not session_id:
            raise CustomException(msg="认证已失效", code=10401, status_code=401)
        ticket = secrets.token_urlsafe(32)
        ok = await RedisCURD(redis).set(
            f"auth:ws_ticket:{ticket}",
            {"session_id": session_id},
            expire=60,
        )
        if not ok:
            raise CustomException(msg="创建 WebSocket ticket 失败")
        return ticket


class CaptchaService:
    """验证码服务"""

    @staticmethod
    async def get_captcha(redis: Redis) -> CaptchaOutSchema:
        """Generate a challenge for enabled or adaptive CAPTCHA flows.

        The endpoint remains callable while the global switch is disabled so
        the login page can reveal a challenge after repeated failures.
        """

        captcha_base64, captcha_value = CaptchaUtil.captcha_arithmetic()
        captcha_key = get_random_character()

        redis_key = f"{RedisInitKeyConfig.CAPTCHA_CODES.key}:{captcha_key}"
        await RedisCURD(redis).set(
            key=redis_key,
            value=captcha_value,
            expire=settings.CAPTCHA_EXPIRE_SECONDS,
        )

        return CaptchaOutSchema(
            enable=settings.CAPTCHA_ENABLE,
            key=CaptchaKey(captcha_key),
            img_base=CaptchaBase64(f"data:image/png;base64,{captcha_base64}"),
        )

    @staticmethod
    async def check_captcha(redis: Redis, key: str, captcha: str) -> bool:
        """校验验证码"""
        if not captcha:
            raise CustomException(msg="验证码不能为空")

        redis_key = f"{RedisInitKeyConfig.CAPTCHA_CODES.key}:{key}"
        captcha_value = await RedisCURD(redis).get(redis_key)
        if not captcha_value:
            raise CustomException(msg="验证码已过期")

        if captcha.lower() != captcha_value.lower():
            raise CustomException(msg="验证码错误")

        await RedisCURD(redis).delete(redis_key)
        return True


class AutoLoginService:
    """免登录服务"""

    AUTO_LOGIN_PREFIX = "fastapiadmin:auto_login:"
    TOKEN_EXPIRE = 300

    @classmethod
    async def get_auto_login_users(cls, db: AsyncSession) -> list[AutoLoginUserSchema]:
        """获取免登录用户列表"""
        from sqlalchemy import select

        from app.api.v1.module_system.user.model import UserModel

        stmt = select(UserModel).where(UserModel.status == 0)
        stmt = stmt.order_by(UserModel.id)
        result = await db.execute(stmt)
        users = result.scalars().all()

        return [
            AutoLoginUserSchema(
                id=user.id,
                username=user.username,
                name=user.name,
                avatar=user.avatar,
            )
            for user in users
        ]

    @classmethod
    async def create_auto_login_token(
        cls,
        redis: Redis,
        db: AsyncSession,
        user_id: int,
    ) -> AutoLoginTokenSchema:
        """创建免登录Token"""
        from sqlalchemy import select

        from app.api.v1.module_system.user.model import UserModel

        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise CustomException(msg="用户不存在")

        if user.status == 1:
            raise CustomException(msg="用户已被停用")

        import uuid

        token = str(uuid.uuid4())
        token_key = f"{cls.AUTO_LOGIN_PREFIX}{token}"

        token_data = {
            "user_id": user.id,
            "username": user.username,
            "created_at": datetime.now().isoformat(),
        }
        await RedisCURD(redis).set(
            key=token_key,
            value=json.dumps(token_data),
            expire=cls.TOKEN_EXPIRE,
        )

        logger.info(f"创建免登录Token成功,用户:{user.username}")

        return AutoLoginTokenSchema(
            token=token,
            user=AutoLoginUserSchema(
                id=user.id,
                username=user.username,
                name=user.name,
                avatar=user.avatar,
            ),
        )

    @classmethod
    async def auto_login(
        cls,
        request: Request,
        redis: Redis,
        db: AsyncSession,
        token: str,
    ) -> JWTOutSchema:
        """免登录"""
        from sqlalchemy import select

        from app.api.v1.module_system.user.model import UserModel

        token_key = f"{cls.AUTO_LOGIN_PREFIX}{token}"
        token_data_str = await RedisCURD(redis).getdel(token_key)

        if not token_data_str:
            raise CustomException(msg="免登录Token已过期或无效")

        if isinstance(token_data_str, bytes):
            token_data_str = token_data_str.decode("utf-8")

        token_data = json.loads(token_data_str)
        user_id = token_data.get("user_id")

        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            raise CustomException(msg="用户不存在")

        if user.status == 1:
            raise CustomException(msg="用户已被停用")

        await RedisCURD(redis).delete(token_key)

        jwt_token = await LoginService.create_token(request=request, redis=redis, user=user, login_type="PC端")

        logger.info(f"用户{user.username}免登录成功")

        return jwt_token
