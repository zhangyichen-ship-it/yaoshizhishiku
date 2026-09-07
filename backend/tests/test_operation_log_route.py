from fastapi import APIRouter, BackgroundTasks, FastAPI
from fastapi.testclient import TestClient

from app.common.response import SuccessResponse
from app.core import router_class


def test_operation_log_route_preserves_endpoint_background_tasks(monkeypatch) -> None:
    events: list[str] = []

    async def write_operation_log(_log_data: dict) -> None:
        events.append("operation-log")

    async def index_document() -> None:
        events.append("index-document")

    monkeypatch.setattr(router_class, "_write_operation_log_async", write_operation_log)

    router = APIRouter(route_class=router_class.OperationLogRoute)

    @router.post("/document/upload")
    async def upload_document(background_tasks: BackgroundTasks) -> SuccessResponse:
        background_tasks.add_task(index_document)
        return SuccessResponse(data={"ok": True})

    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        response = client.post("/document/upload")

    assert response.status_code == 200
    assert events == ["index-document", "operation-log"]
