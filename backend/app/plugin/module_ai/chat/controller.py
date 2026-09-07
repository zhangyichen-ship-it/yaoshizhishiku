from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission, db_getter
from app.core.router_class import OperationLogRoute

from ..knowledge.control_plane_service import authenticate_control_plane_push
from ..knowledge.schema import AiModelUsagePushOutSchema, AiModelUsagePushSchema
from ..knowledge.usage_service import record_model_usage
from .model_config_service import (
    apply_embedding_model_config,
    get_model_config,
    sync_embedding_model_config,
    update_model_config,
)
from .schema import (
    AiEmbeddingConfigPushSchema,
    AiEmbeddingSyncOutSchema,
    AiModelConfigOutSchema,
    AiModelConfigUpdateSchema,
)

ChatRouter = APIRouter(route_class=OperationLogRoute, prefix="/chat", tags=["AI管理", "模型配置"])
_cloud_push_bearer = HTTPBearer(auto_error=False)


@ChatRouter.get(
    "/model-config",
    summary="AI model configuration",
    response_model=ResponseSchema[AiModelConfigOutSchema],
)
async def model_config_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:model_config:query"]))],
) -> JSONResponse:
    result = await get_model_config(auth)
    return SuccessResponse(data=result, msg="query AI model configuration success")


@ChatRouter.post(
    "/model-config/sync-embedding",
    summary="从云面板同步向量模型配置",
    response_model=ResponseSchema[AiEmbeddingSyncOutSchema],
)
async def sync_embedding_model_config_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:model_config:update"]))],
) -> JSONResponse:
    result = await sync_embedding_model_config(auth)
    return SuccessResponse(data=result, msg="向量模型同步成功")


@ChatRouter.post(
    "/model-config/push-embedding",
    summary="接收云面板推送的向量模型配置",
    response_model=ResponseSchema[AiEmbeddingSyncOutSchema],
)
async def push_embedding_model_config_controller(
    data: AiEmbeddingConfigPushSchema,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_cloud_push_bearer)],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    await authenticate_control_plane_push(db, credentials.credentials if credentials else None)
    result = await apply_embedding_model_config(AuthSchema(db=db, check_data_scope=False), data)
    return SuccessResponse(data=result, msg="云面板向量模型推送成功")


@ChatRouter.post(
    "/model-usage/push",
    summary="接收云面板推送的模型用量",
    response_model=ResponseSchema[AiModelUsagePushOutSchema],
)
async def push_model_usage_controller(
    data: AiModelUsagePushSchema,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_cloud_push_bearer)],
    db: Annotated[AsyncSession, Depends(db_getter)],
) -> JSONResponse:
    await authenticate_control_plane_push(db, credentials.credentials if credentials else None)
    result = await record_model_usage(db, data)
    return SuccessResponse(data=result, msg="云面板模型用量推送成功")


@ChatRouter.put(
    "/model-config",
    summary="Update AI model configuration",
    response_model=ResponseSchema[AiModelConfigOutSchema],
)
async def update_model_config_controller(
    data: AiModelConfigUpdateSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:model_config:update"]))],
) -> JSONResponse:
    result = await update_model_config(auth, data)
    return SuccessResponse(data=result, msg="update AI model configuration success")
