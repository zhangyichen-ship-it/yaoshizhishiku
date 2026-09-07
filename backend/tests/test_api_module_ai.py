"""模块接口测试 —— module_ai 的客户知识库路由边界。"""

from fastapi.testclient import TestClient


def test_customer_kb_does_not_register_chat_or_session_routes(ai_client: TestClient) -> None:
    for method, path in (
        ("GET", "/ai/chat/list"),
        ("GET", "/ai/chat/detail/test_session"),
        ("POST", "/ai/chat/create"),
        ("PUT", "/ai/chat/update/test_session"),
        ("DELETE", "/ai/chat/delete"),
        ("POST", "/ai/chat/ai-chat"),
        ("GET", "/ai/memory/list"),
    ):
        response = ai_client.request(method, path)
        assert response.status_code == 404, f"仍注册客户侧对话路由: {method} {path}"


def test_embedding_push_requires_instance_credential(ai_client: TestClient) -> None:
    response = ai_client.post(
        "/ai/chat/model-config/push-embedding",
        json={"provider": "local", "model": "bge-small", "base_url": ""},
    )
    assert response.status_code == 401


def test_model_usage_push_requires_instance_credential(ai_client: TestClient) -> None:
    response = ai_client.post(
        "/ai/chat/model-usage/push",
        json={
            "request_id": "request-1",
            "occurred_at": "2026-09-05T12:00:00",
            "requested_model": "logical-model",
            "upstream_model": "upstream-model",
            "provider_name": "primary",
            "protocol": "openai",
            "status": 1,
            "response_code": 200,
        },
    )
    assert response.status_code == 401


def test_model_usage_summary_requires_member_permission(ai_client: TestClient) -> None:
    response = ai_client.get("/ai/knowledge/usage-summary")
    assert response.status_code in {401, 403}
