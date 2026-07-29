import asyncio

import httpx

import app.config as config_module
from app.services.ai_request_limiter import (
    api_key_identity,
    provider_request_limiter,
    run_with_provider_limit,
)


def _rate_limit_error() -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://provider.example/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": "0.1"})
    return httpx.HTTPStatusError("rate limited", request=request, response=response)


def test_provider_limiter_caps_same_key_and_keeps_raw_key_out_of_state(monkeypatch):
    monkeypatch.setattr(config_module.settings, "API_KEY_CONCURRENCY", 2, raising=False)
    provider_request_limiter.reset()
    raw_key = "sk-sensitive-test-key"
    active = 0
    maximum = 0

    async def operation():
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.04)
        active -= 1
        return "ok"

    async def scenario():
        return await asyncio.gather(
            *(run_with_provider_limit(raw_key, operation) for _ in range(6))
        )

    assert asyncio.run(scenario()) == ["ok"] * 6
    assert maximum == 2
    assert raw_key not in provider_request_limiter._active
    assert raw_key not in api_key_identity(raw_key)


def test_different_byok_keys_do_not_block_each_other(monkeypatch):
    monkeypatch.setattr(config_module.settings, "API_KEY_CONCURRENCY", 1, raising=False)
    provider_request_limiter.reset()
    both_entered = asyncio.Event()
    entered = 0

    async def operation():
        nonlocal entered
        entered += 1
        if entered == 2:
            both_entered.set()
        await asyncio.wait_for(both_entered.wait(), timeout=0.5)
        return "ok"

    async def scenario():
        return await asyncio.gather(
            run_with_provider_limit("sk-byok-a", operation),
            run_with_provider_limit("sk-byok-b", operation),
        )

    assert asyncio.run(scenario()) == ["ok", "ok"]


def test_rate_limit_backoff_releases_provider_slot(monkeypatch):
    monkeypatch.setattr(config_module.settings, "API_KEY_CONCURRENCY", 1, raising=False)
    provider_request_limiter.reset()
    order = []
    attempts = 0

    async def rate_limited_operation():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            order.append("limited")
            raise _rate_limit_error()
        order.append("retried")
        return "retried"

    async def other_operation():
        order.append("other")
        return "other"

    async def scenario():
        first = asyncio.create_task(
            run_with_provider_limit("sk-shared", rate_limited_operation)
        )
        await asyncio.sleep(0.02)
        second_result = await run_with_provider_limit("sk-shared", other_operation)
        first_result = await first
        return first_result, second_result

    assert asyncio.run(scenario()) == ("retried", "other")
    assert order == ["limited", "other", "retried"]
