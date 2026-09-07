from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio.client import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import db_getter, redis_getter

from ..member_client import CloudMemberClient
from .service import AppDataPrincipal, principal_from_claims

_app_data_bearer = HTTPBearer(auto_error=False)


async def get_app_data_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_app_data_bearer)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    _redis: Annotated[Redis, Depends(redis_getter)],
) -> AppDataPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        from app.core.exceptions import CustomException

        raise CustomException(msg="App Data 凭证缺失", code=10401, status_code=401)
    claims = await CloudMemberClient(db=db).introspect_app_data_token(credentials.credentials)
    return principal_from_claims(claims)
