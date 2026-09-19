from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.tracing import (
    TRACE_HEADER,
    parse_trace_id,
    reset_trace_id,
    set_trace_id,
)


class TraceIdMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        trace_id = parse_trace_id(Headers(scope=scope).get(TRACE_HEADER))
        token = set_trace_id(trace_id)

        async def send_with_trace_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)[TRACE_HEADER] = trace_id
            await send(message)

        try:
            await self._app(scope, receive, send_with_trace_id)
        finally:
            reset_trace_id(token)
