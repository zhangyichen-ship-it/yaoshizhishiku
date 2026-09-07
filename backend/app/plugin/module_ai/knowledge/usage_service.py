from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from .model import AiModelUsageModel
from .schema import AiModelUsagePushSchema


def _normalise_group_day(value: object) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        return value[:10]
    return None


def _row_int(row: object, key: str) -> int:
    value = row[key]  # type: ignore[index]
    return max(0, int(value or 0))


def _row_money(row: object, key: str) -> float:
    value = row[key]  # type: ignore[index]
    return float(max(Decimal(str(value or 0)), Decimal("0")))


async def record_model_usage(db: AsyncSession, data: AiModelUsagePushSchema) -> dict[str, bool]:
    existing_id = await db.scalar(
        select(AiModelUsageModel.id).where(
            AiModelUsageModel.source_request_id == data.request_id,
            AiModelUsageModel.is_deleted.is_(False),
        )
    )
    if existing_id is not None:
        return {"accepted": True, "duplicate": True}

    db.add(
        AiModelUsageModel(
            source_request_id=data.request_id,
            occurred_at=data.occurred_at.replace(tzinfo=None),
            cloud_user_id=data.user_id,
            username=data.username,
            requested_model=data.requested_model,
            upstream_model=data.upstream_model,
            provider_name=data.provider_name,
            protocol=data.protocol,
            purpose=data.purpose,
            status=data.status,
            response_code=data.response_code,
            is_stream=data.is_stream,
            usage_reported=data.usage_reported,
            prompt_tokens=data.prompt_tokens,
            completion_tokens=data.completion_tokens,
            cached_input_tokens=data.cached_input_tokens,
            cache_creation_input_tokens=data.cache_creation_input_tokens,
            duration_ms=data.duration_ms,
            input_cost_cny=data.input_cost_cny,
            output_cost_cny=data.output_cost_cny,
            total_cost_cny=data.total_cost_cny,
            free_cost_cny=data.free_cost_cny,
            paid_cost_cny=data.paid_cost_cny,
            billing_status=data.billing_status,
        )
    )
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        return {"accepted": True, "duplicate": True}
    return {"accepted": True, "duplicate": False}


async def get_model_usage_summary(db: AsyncSession) -> dict[str, object]:
    today = date.today()
    first_day = today - timedelta(days=6)
    start_at = datetime.combine(first_day, time.min)
    end_at = datetime.combine(today + timedelta(days=1), time.min)
    usage_filters = (
        AiModelUsageModel.is_deleted.is_(False),
        AiModelUsageModel.occurred_at >= start_at,
        AiModelUsageModel.occurred_at < end_at,
    )

    usage_day = func.date(AiModelUsageModel.occurred_at).label("day")
    usage_query = (
        select(
            usage_day,
            func.count(AiModelUsageModel.id).label("request_count"),
            func.sum(case((AiModelUsageModel.usage_reported.is_(True), 1), else_=0)).label("usage_reported_requests"),
            func.coalesce(func.sum(AiModelUsageModel.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.cache_creation_input_tokens), 0).label(
                "cache_creation_input_tokens"
            ),
            func.coalesce(func.sum(AiModelUsageModel.total_cost_cny), 0).label("total_cost_cny"),
            func.coalesce(func.sum(AiModelUsageModel.free_cost_cny), 0).label("free_cost_cny"),
            func.coalesce(func.sum(AiModelUsageModel.paid_cost_cny), 0).label("paid_cost_cny"),
        )
        .where(*usage_filters)
        .group_by(usage_day)
    )
    rows = (await db.execute(usage_query)).mappings()
    by_day: dict[str, dict[str, int | float | str]] = {}
    for row in rows:
        group_day = _normalise_group_day(row["day"])
        if group_day is None:
            continue
        prompt_tokens = _row_int(row, "prompt_tokens")
        completion_tokens = _row_int(row, "completion_tokens")
        by_day[group_day] = {
            "day": group_day,
            "request_count": _row_int(row, "request_count"),
            "usage_reported_requests": _row_int(row, "usage_reported_requests"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cached_input_tokens": _row_int(row, "cached_input_tokens"),
            "cache_creation_input_tokens": _row_int(row, "cache_creation_input_tokens"),
            "total_cost_cny": _row_money(row, "total_cost_cny"),
            "free_cost_cny": _row_money(row, "free_cost_cny"),
            "paid_cost_cny": _row_money(row, "paid_cost_cny"),
        }

    items = [
        by_day.get(
            (first_day + timedelta(days=offset)).isoformat(),
            {
                "day": (first_day + timedelta(days=offset)).isoformat(),
                "request_count": 0,
                "usage_reported_requests": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "cached_input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "total_cost_cny": 0.0,
                "free_cost_cny": 0.0,
                "paid_cost_cny": 0.0,
            },
        )
        for offset in range(7)
    ]

    usage_user_key = func.coalesce(
        AiModelUsageModel.cloud_user_id,
        AiModelUsageModel.username,
        "__unknown__",
    ).label("user_key")
    user_query = (
        select(
            usage_user_key,
            func.max(AiModelUsageModel.cloud_user_id).label("user_id"),
            func.max(AiModelUsageModel.username).label("username"),
            func.count(AiModelUsageModel.id).label("request_count"),
            func.coalesce(func.sum(AiModelUsageModel.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.cached_input_tokens), 0).label("cached_input_tokens"),
            func.coalesce(func.sum(AiModelUsageModel.cache_creation_input_tokens), 0).label(
                "cache_creation_input_tokens"
            ),
            func.coalesce(func.sum(AiModelUsageModel.total_cost_cny), 0).label("total_cost_cny"),
            func.coalesce(func.sum(AiModelUsageModel.free_cost_cny), 0).label("free_cost_cny"),
            func.coalesce(func.sum(AiModelUsageModel.paid_cost_cny), 0).label("paid_cost_cny"),
        )
        .where(*usage_filters)
        .group_by(usage_user_key)
    )
    users: list[dict[str, object]] = []
    for row in (await db.execute(user_query)).mappings():
        prompt_tokens = _row_int(row, "prompt_tokens")
        completion_tokens = _row_int(row, "completion_tokens")
        user_id = row["user_id"]
        username = row["username"] or (f"用户 {user_id}" if user_id else "未知用户")
        users.append(
            {
                "user_id": user_id,
                "username": username,
                "request_count": _row_int(row, "request_count"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
                "cached_input_tokens": _row_int(row, "cached_input_tokens"),
                "cache_creation_input_tokens": _row_int(row, "cache_creation_input_tokens"),
                "total_cost_cny": _row_money(row, "total_cost_cny"),
                "free_cost_cny": _row_money(row, "free_cost_cny"),
                "paid_cost_cny": _row_money(row, "paid_cost_cny"),
            }
        )
    users.sort(key=lambda item: (-int(item["total_tokens"]), str(item["username"]).casefold()))

    integer_fields = (
        "request_count",
        "usage_reported_requests",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "cached_input_tokens",
        "cache_creation_input_tokens",
    )
    money_fields = (
        "total_cost_cny",
        "free_cost_cny",
        "paid_cost_cny",
    )
    return {
        "items": items,
        "users": users,
        **{field: sum(int(item[field]) for item in items) for field in integer_fields},
        **{field: sum(float(item[field]) for item in items) for field in money_fields},
    }
