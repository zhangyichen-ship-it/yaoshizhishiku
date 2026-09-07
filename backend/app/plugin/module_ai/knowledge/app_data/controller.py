from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Path
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.dependencies import db_getter

from .dependencies import get_app_data_principal
from .schema import AppResourceCreateSchema, AppResourceOutSchema, AppResourcePatchSchema
from .service import AppDataPrincipal, AppDataService

AppDataRouter = APIRouter(prefix="/app-data", tags=["AI", "App Data"])


def _request_id(value: str | None) -> str:
    return value.strip()[:128] if value and value.strip() else str(uuid4())


@AppDataRouter.get(
    "/apps/{app_id}/{resource_type}",
    response_model=ResponseSchema[list[AppResourceOutSchema]],
)
async def list_app_resources_controller(
    app_id: Annotated[str, Path(min_length=1, max_length=150)],
    resource_type: Annotated[str, Path(min_length=1, max_length=128)],
    principal: Annotated[AppDataPrincipal, Depends(get_app_data_principal)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> JSONResponse:
    data = await AppDataService(db, principal).list(app_id, resource_type, _request_id(x_request_id))
    return SuccessResponse(data=data, msg="查询 App 数据成功")


@AppDataRouter.post(
    "/apps/{app_id}/{resource_type}",
    response_model=ResponseSchema[AppResourceOutSchema],
)
async def create_app_resource_controller(
    data: AppResourceCreateSchema,
    app_id: Annotated[str, Path(min_length=1, max_length=150)],
    resource_type: Annotated[str, Path(min_length=1, max_length=128)],
    principal: Annotated[AppDataPrincipal, Depends(get_app_data_principal)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> JSONResponse:
    result = await AppDataService(db, principal).create(
        app_id,
        resource_type,
        data,
        _request_id(x_request_id),
        idempotency_key.strip() if idempotency_key else None,
    )
    return SuccessResponse(data=result, msg="创建 App 数据成功")


@AppDataRouter.get(
    "/apps/{app_id}/{resource_type}/{resource_id}",
    response_model=ResponseSchema[AppResourceOutSchema],
)
async def get_app_resource_controller(
    app_id: Annotated[str, Path(min_length=1, max_length=150)],
    resource_type: Annotated[str, Path(min_length=1, max_length=128)],
    resource_id: Annotated[str, Path(min_length=1, max_length=64)],
    principal: Annotated[AppDataPrincipal, Depends(get_app_data_principal)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> JSONResponse:
    result = await AppDataService(db, principal).get(app_id, resource_type, resource_id, _request_id(x_request_id))
    return SuccessResponse(data=result, msg="查询 App 数据成功")


@AppDataRouter.patch(
    "/apps/{app_id}/{resource_type}/{resource_id}",
    response_model=ResponseSchema[AppResourceOutSchema],
)
async def update_app_resource_controller(
    data: AppResourcePatchSchema,
    app_id: Annotated[str, Path(min_length=1, max_length=150)],
    resource_type: Annotated[str, Path(min_length=1, max_length=128)],
    resource_id: Annotated[str, Path(min_length=1, max_length=64)],
    principal: Annotated[AppDataPrincipal, Depends(get_app_data_principal)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> JSONResponse:
    result = await AppDataService(db, principal).update(
        app_id,
        resource_type,
        resource_id,
        data,
        _request_id(x_request_id),
        if_match,
    )
    return SuccessResponse(data=result, msg="更新 App 数据成功")


@AppDataRouter.delete(
    "/apps/{app_id}/{resource_type}/{resource_id}",
    response_model=ResponseSchema[None],
)
async def delete_app_resource_controller(
    app_id: Annotated[str, Path(min_length=1, max_length=150)],
    resource_type: Annotated[str, Path(min_length=1, max_length=128)],
    resource_id: Annotated[str, Path(min_length=1, max_length=64)],
    principal: Annotated[AppDataPrincipal, Depends(get_app_data_principal)],
    db: Annotated[AsyncSession, Depends(db_getter)],
    x_request_id: Annotated[str | None, Header(alias="X-Request-ID")] = None,
) -> JSONResponse:
    await AppDataService(db, principal).delete(app_id, resource_type, resource_id, _request_id(x_request_id))
    return SuccessResponse(msg="删除 App 数据成功")
