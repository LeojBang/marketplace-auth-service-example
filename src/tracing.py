import logging
import logging.config
import re
import uuid
from contextvars import ContextVar, Token
from typing import Any

TRACE_HEADER = "X-Trace-Id"
LOG_FORMAT = "%(asctime)s %(levelname)s [%(trace_id)s] %(name)s: %(message)s"

_TRACE_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

trace_id_var: ContextVar[str | None] = ContextVar("trace_id", default=None)


def get_trace_id() -> str | None:
    return trace_id_var.get()


def set_trace_id(trace_id: str | None) -> Token[str | None]:
    return trace_id_var.set(trace_id)


def reset_trace_id(token: Token[str | None]) -> None:
    trace_id_var.reset(token)


def new_trace_id() -> str:
    return uuid.uuid4().hex


def parse_trace_id(raw: str | None) -> str:
    if raw is not None and _TRACE_ID_PATTERN.match(raw):
        return raw
    return new_trace_id()


def trace_headers() -> dict[str, str]:
    trace_id = get_trace_id()
    return {TRACE_HEADER: trace_id} if trace_id else {}


class TraceIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = get_trace_id() or "-"
        return True


LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"trace_id": {"()": "src.tracing.TraceIdFilter"}},
    "formatters": {"default": {"format": LOG_FORMAT}},
    "handlers": {
        "default": {
            "class": "logging.StreamHandler",
            "formatter": "default",
            "filters": ["trace_id"],
            "stream": "ext://sys.stderr",
        },
    },
    "root": {"level": "INFO", "handlers": ["default"]},
    "loggers": {
        "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
        "uvicorn.access": {
            "handlers": ["default"],
            "level": "INFO",
            "propagate": False,
        },
    },
}


def configure_logging() -> None:
    logging.config.dictConfig(LOGGING_CONFIG)
