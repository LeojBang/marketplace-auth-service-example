import asyncio
import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.presentation.api.middleware import TraceIdMiddleware
from src.tracing import TraceIdFilter, get_trace_id


@pytest.fixture
def traced_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)

    @app.get("/trace")
    async def trace(delay: float = 0) -> dict[str, str | None]:
        await asyncio.sleep(delay)
        return {"trace_id": get_trace_id()}

    return app


@pytest.fixture
async def traced_client(traced_app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=traced_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_uses_incoming_header(traced_client: AsyncClient) -> None:
    resp = await traced_client.get("/trace", headers={"X-Trace-Id": "abc-1"})

    assert resp.json() == {"trace_id": "abc-1"}
    assert resp.headers["X-Trace-Id"] == "abc-1"


async def test_generates_when_header_missing(traced_client: AsyncClient) -> None:
    resp = await traced_client.get("/trace")

    generated = resp.headers["X-Trace-Id"]
    assert len(generated) == 32
    assert resp.json() == {"trace_id": generated}


async def test_replaces_invalid_header(traced_client: AsyncClient) -> None:
    resp = await traced_client.get("/trace", headers={"X-Trace-Id": "bad id!"})

    assert resp.headers["X-Trace-Id"] != "bad id!"
    assert len(resp.headers["X-Trace-Id"]) == 32


async def test_context_is_reset_after_request(traced_client: AsyncClient) -> None:
    await traced_client.get("/trace", headers={"X-Trace-Id": "abc-2"})

    assert get_trace_id() is None


async def test_concurrent_requests_do_not_mix_ids(traced_client: AsyncClient) -> None:
    async def call(trace_id: str, delay: float) -> dict[str, str | None]:
        resp = await traced_client.get(
            "/trace",
            params={"delay": delay},
            headers={"X-Trace-Id": trace_id},
        )
        return resp.json()

    results = await asyncio.gather(call("slow", 0.05), call("fast", 0.0))

    assert results == [{"trace_id": "slow"}, {"trace_id": "fast"}]


async def test_log_lines_carry_trace_id(
    traced_app: FastAPI, traced_client: AsyncClient
) -> None:
    records: list[logging.LogRecord] = []

    class Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = Capture()
    handler.addFilter(TraceIdFilter())
    logger = logging.getLogger("trace-test")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    @traced_app.get("/log")
    async def log() -> dict[str, bool]:
        logger.info("inside request")
        return {"ok": True}

    try:
        await traced_client.get("/log", headers={"X-Trace-Id": "abc-3"})
    finally:
        logger.removeHandler(handler)

    assert [r.trace_id for r in records] == ["abc-3"]
