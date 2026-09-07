from datetime import UTC, datetime

from app.plugin.module_ai.chat.controller import ChatRouter
from app.plugin.module_ai.chat.schema import AiEmbeddingConfigPushSchema
from app.plugin.module_ai.knowledge.schema import AiModelUsagePushSchema


def test_control_plane_v1_payload_contract_contains_only_shared_fields() -> None:
    embedding = AiEmbeddingConfigPushSchema(
        provider="local",
        model="text-embedding-3-small",
        base_url="",
    )
    assert set(embedding.model_dump()) == {"provider", "model", "base_url"}

    usage = AiModelUsagePushSchema(
        request_id="request-1",
        occurred_at=datetime.now(UTC),
        user_id="cloud-user-1",
        username="alice",
        requested_model="managed-model",
        upstream_model="upstream-model",
        provider_name="provider",
        protocol="openai",
        status=1,
        response_code=200,
    )
    assert set(usage.model_dump()) == {
        "request_id",
        "occurred_at",
        "user_id",
        "username",
        "requested_model",
        "upstream_model",
        "provider_name",
        "protocol",
        "purpose",
        "status",
        "response_code",
        "is_stream",
        "usage_reported",
        "prompt_tokens",
        "completion_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
        "duration_ms",
        "input_cost_cny",
        "output_cost_cny",
        "total_cost_cny",
        "free_cost_cny",
        "paid_cost_cny",
        "billing_status",
    }
    assert not {"tenant_id", "identity_token", "service_credential", "prompt", "response"} & set(usage.model_dump())
    assert "paid_balance_cny" not in usage.model_dump()


def test_control_plane_v1_push_routes_remain_compatible() -> None:
    paths = {route.path for route in ChatRouter.routes}
    assert {
        "/chat/model-config/push-embedding",
        "/chat/model-usage/push",
    } <= paths
