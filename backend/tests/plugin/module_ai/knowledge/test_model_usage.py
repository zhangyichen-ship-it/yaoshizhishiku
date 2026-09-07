from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.plugin.module_ai.knowledge.model import AiModelUsageModel
from app.plugin.module_ai.knowledge.schema import AiModelUsagePushSchema
from app.plugin.module_ai.knowledge.usage_service import get_model_usage_summary, record_model_usage


@pytest.mark.asyncio
async def test_model_usage_is_idempotent_and_summarized(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'model-usage.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(AiModelUsageModel.__table__.create)

    data = AiModelUsagePushSchema(
        request_id="request-1",
        occurred_at=datetime.now(),
        user_id="user-1",
        username="alice",
        requested_model="logical-model",
        upstream_model="upstream-model",
        provider_name="primary",
        protocol="openai",
        status=1,
        response_code=200,
        usage_reported=True,
        prompt_tokens=12,
        completion_tokens=7,
        cached_input_tokens=3,
        cache_creation_input_tokens=1,
        duration_ms=42,
        input_cost_cny=Decimal("0.001"),
        output_cost_cny=Decimal("0.002"),
        total_cost_cny=Decimal("0.003"),
        free_cost_cny=Decimal("0.002"),
        paid_cost_cny=Decimal("0.001"),
        billing_status="charged",
    )
    second_data = data.model_copy(
        update={
            "request_id": "request-2",
            "user_id": "user-2",
            "username": "bob",
            "prompt_tokens": 5,
            "completion_tokens": 4,
            "cached_input_tokens": None,
            "cache_creation_input_tokens": None,
            "input_cost_cny": Decimal("0.004"),
            "output_cost_cny": Decimal("0.001"),
            "total_cost_cny": Decimal("0.005"),
            "free_cost_cny": Decimal("0.005"),
            "paid_cost_cny": Decimal("0"),
            "billing_status": "free",
        }
    )
    legacy_data = data.model_copy(
        update={
            "request_id": "request-legacy",
            "user_id": None,
            "username": None,
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "cached_input_tokens": None,
            "cache_creation_input_tokens": None,
            "input_cost_cny": None,
            "output_cost_cny": None,
            "total_cost_cny": None,
            "free_cost_cny": Decimal("0"),
            "paid_cost_cny": Decimal("0"),
            "billing_status": "price_unconfigured",
        }
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as db:
        assert await record_model_usage(db, data) == {"accepted": True, "duplicate": False}
        assert await record_model_usage(db, second_data) == {"accepted": True, "duplicate": False}
        assert await record_model_usage(db, legacy_data) == {"accepted": True, "duplicate": False}
        await db.commit()

        assert await record_model_usage(db, data) == {"accepted": True, "duplicate": True}
        summary = await get_model_usage_summary(db)

    assert summary["request_count"] == 3
    assert summary["usage_reported_requests"] == 3
    assert summary["prompt_tokens"] == 18
    assert summary["completion_tokens"] == 13
    assert summary["total_tokens"] == 31
    assert summary["cached_input_tokens"] == 3
    assert summary["cache_creation_input_tokens"] == 1
    assert summary["total_cost_cny"] == pytest.approx(0.008)
    assert summary["free_cost_cny"] == pytest.approx(0.007)
    assert summary["paid_cost_cny"] == pytest.approx(0.001)
    assert len(summary["items"]) == 7
    users = {item["username"]: item for item in summary["users"]}
    assert users["alice"]["total_tokens"] == 19
    assert users["bob"]["total_tokens"] == 9
    assert users["alice"]["total_cost_cny"] == pytest.approx(0.003)
    assert users["bob"]["total_cost_cny"] == pytest.approx(0.005)
    assert users["未知用户"]["total_tokens"] == 3
    await engine.dispose()
