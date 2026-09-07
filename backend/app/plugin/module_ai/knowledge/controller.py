from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Form, Header, Path, UploadFile
from fastapi.responses import JSONResponse

from app.common.response import ResponseSchema, SuccessResponse
from app.core.base_params import PaginationQueryParam
from app.core.base_schema import AuthSchema
from app.core.dependencies import AuthPermission
from app.core.router_class import OperationLogRoute

from .member_client import CloudMemberClient
from .member_service import CustomerMemberService
from .schema import (
    KbMemberCreateSchema,
    KbMemberOutSchema,
    KbMemberUpdateSchema,
    KnowledgeBaseAccessOutSchema,
    KnowledgeBaseAccessUpdateSchema,
    KnowledgeBaseCreateSchema,
    KnowledgeBaseOutSchema,
    KnowledgeBaseQueryParam,
    KnowledgeBaseUpdateSchema,
    KnowledgeDocumentOutSchema,
    KnowledgeDocumentQueryParam,
    KnowledgeSearchSchema,
    RetrievalTestSchema,
)
from .service import KnowledgeService
from .usage_service import get_model_usage_summary

KnowledgeRouter = APIRouter(route_class=OperationLogRoute, prefix="/knowledge", tags=["AI", "Knowledge"])


@KnowledgeRouter.get(
    "/list",
    summary="List knowledge bases",
    response_model=ResponseSchema[dict[str, Any]],
)
async def list_knowledge_base_controller(
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[KnowledgeBaseQueryParam, Depends()],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:knowledge:query"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).page_knowledge_bases(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="query knowledge bases success")


@KnowledgeRouter.get(
    "/optionselect",
    summary="List enabled knowledge bases",
    response_model=ResponseSchema[list[KnowledgeBaseOutSchema]],
)
async def list_enabled_knowledge_base_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:knowledge:query"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).list_enabled_bases()
    return SuccessResponse(data=result, msg="query enabled knowledge bases success")


@KnowledgeRouter.post(
    "/create",
    summary="Create knowledge base",
    response_model=ResponseSchema[KnowledgeBaseOutSchema],
)
async def create_knowledge_base_controller(
    data: KnowledgeBaseCreateSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:knowledge:create"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).create_knowledge_base(data=data)
    return SuccessResponse(data=result, msg="create knowledge base success")


@KnowledgeRouter.put(
    "/update/{id}",
    summary="Update knowledge base",
    response_model=ResponseSchema[KnowledgeBaseOutSchema],
)
async def update_knowledge_base_controller(
    id: Annotated[int, Path(ge=1)],
    data: KnowledgeBaseUpdateSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:knowledge:update"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).update_knowledge_base(knowledge_base_id=id, data=data)
    return SuccessResponse(data=result, msg="update knowledge base success")


@KnowledgeRouter.delete(
    "/delete",
    summary="Delete knowledge bases",
    response_model=ResponseSchema[None],
)
async def delete_knowledge_base_controller(
    ids: Annotated[list[int], Body()],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:knowledge:delete"]))],
) -> JSONResponse:
    await KnowledgeService(auth).delete_knowledge_base(ids=ids)
    return SuccessResponse(msg="delete knowledge base success")


@KnowledgeRouter.get(
    "/document/list",
    summary="List knowledge documents",
    response_model=ResponseSchema[dict[str, Any]],
)
async def list_document_controller(
    page: Annotated[PaginationQueryParam, Depends()],
    search: Annotated[KnowledgeDocumentQueryParam, Depends()],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:document:query"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).page_documents(
        page_no=page.page_no,
        page_size=page.page_size,
        search=search,
        order_by=page.order_by,
    )
    return SuccessResponse(data=result, msg="query knowledge documents success")


@KnowledgeRouter.post(
    "/document/upload",
    summary="Upload and index knowledge document",
    response_model=ResponseSchema[KnowledgeDocumentOutSchema],
)
async def upload_document_controller(
    knowledge_base_id: Annotated[int, Form(ge=1)],
    file: UploadFile,
    background_tasks: BackgroundTasks,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:document:create"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).upload_document(
        knowledge_base_id=knowledge_base_id,
        file=file,
        background_tasks=background_tasks,
    )
    return SuccessResponse(data=result, msg="upload knowledge document success")


@KnowledgeRouter.post(
    "/document/{id}/reindex",
    summary="Reindex knowledge document",
    response_model=ResponseSchema[KnowledgeDocumentOutSchema],
)
async def reindex_document_controller(
    id: Annotated[int, Path(ge=1)],
    background_tasks: BackgroundTasks,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:document:create"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).reindex_document(document_id=id, background_tasks=background_tasks)
    return SuccessResponse(data=result, msg="reindex knowledge document submitted")


@KnowledgeRouter.delete(
    "/document/delete",
    summary="Delete knowledge documents",
    response_model=ResponseSchema[None],
)
async def delete_document_controller(
    ids: Annotated[list[int], Body()],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:document:delete"]))],
) -> JSONResponse:
    await KnowledgeService(auth).delete_document(ids=ids)
    return SuccessResponse(msg="delete knowledge document success")


@KnowledgeRouter.post(
    "/retrieval/test",
    summary="Test knowledge retrieval",
    response_model=ResponseSchema[dict[str, Any]],
)
async def retrieval_test_controller(
    data: RetrievalTestSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:retrieval:test"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).query_retrieval(data=data)
    return SuccessResponse(data=result, msg="test retrieval success")


@KnowledgeRouter.post(
    "/search",
    summary="Search authorized knowledge bases",
    response_model=ResponseSchema[dict[str, Any]],
)
async def search_knowledge_controller(
    data: KnowledgeSearchSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:retrieval:test"]))],
) -> JSONResponse:
    result = await KnowledgeService(auth).search(data=data)
    return SuccessResponse(data=result, msg="knowledge search success")


@KnowledgeRouter.get(
    "/usage-summary",
    summary="查询近七日模型用量",
    response_model=ResponseSchema[dict[str, Any]],
)
async def get_model_usage_summary_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:member:query"]))],
) -> JSONResponse:
    result = await get_model_usage_summary(auth.db)  # type: ignore[arg-type]
    return SuccessResponse(data=result, msg="query model usage summary success")


@KnowledgeRouter.get(
    "/billing-summary",
    summary="查询云端租户额度",
    response_model=ResponseSchema[dict[str, Any]],
)
async def get_billing_summary_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:member:query"]))],
) -> JSONResponse:
    result = await CloudMemberClient(db=auth.db).get_billing_summary()
    return SuccessResponse(data=result, msg="查询云端租户额度成功")


@KnowledgeRouter.get(
    "/members",
    summary="同步并查询云端员工",
    response_model=ResponseSchema[list[KbMemberOutSchema]],
)
async def list_kb_members_controller(
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:member:query"]))],
) -> JSONResponse:
    result = await CustomerMemberService(auth).list_members()
    return SuccessResponse(data=result, msg="查询云端员工成功")


@KnowledgeRouter.post(
    "/members",
    summary="通过云面板创建员工",
    response_model=ResponseSchema[KbMemberOutSchema],
)
async def create_kb_member_controller(
    data: KbMemberCreateSchema,
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:member:create"]))],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> JSONResponse:
    result = await CustomerMemberService(auth).create_member(data, idempotency_key)
    return SuccessResponse(data=result, msg="创建云端员工成功")


@KnowledgeRouter.patch(
    "/members/{user_id}",
    summary="通过云面板修改员工",
    response_model=ResponseSchema[KbMemberOutSchema],
)
async def update_kb_member_controller(
    data: KbMemberUpdateSchema,
    user_id: Annotated[int, Path(gt=0)],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:member:update"]))],
) -> JSONResponse:
    result = await CustomerMemberService(auth).update_member(user_id, data)
    return SuccessResponse(data=result, msg="修改云端员工成功")


@KnowledgeRouter.get(
    "/members/{user_id}/access",
    summary="查询员工知识库权限",
    response_model=ResponseSchema[KnowledgeBaseAccessOutSchema],
)
async def get_kb_member_access_controller(
    user_id: Annotated[int, Path(gt=0)],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:access:query"]))],
) -> JSONResponse:
    result = await CustomerMemberService(auth).get_access(user_id)
    return SuccessResponse(data=result, msg="查询员工知识库权限成功")


@KnowledgeRouter.put(
    "/members/{user_id}/access",
    summary="设置员工知识库权限",
    response_model=ResponseSchema[KnowledgeBaseAccessOutSchema],
)
async def set_kb_member_access_controller(
    data: KnowledgeBaseAccessUpdateSchema,
    user_id: Annotated[int, Path(gt=0)],
    auth: Annotated[AuthSchema, Depends(AuthPermission(["module_ai:access:update"]))],
) -> JSONResponse:
    result = await CustomerMemberService(auth).set_access(user_id, data)
    return SuccessResponse(data=result, msg="设置员工知识库权限成功")
