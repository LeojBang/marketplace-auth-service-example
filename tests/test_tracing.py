import logging

from src.tracing import (
    TraceIdFilter,
    get_trace_id,
    parse_trace_id,
    reset_trace_id,
    set_trace_id,
    trace_headers,
)


def test_parse_accepts_valid_id() -> None:
    assert parse_trace_id("abc-123_X.y") == "abc-123_X.y"


def test_parse_generates_when_missing() -> None:
    first = parse_trace_id(None)
    assert len(first) == 32
    assert first != parse_trace_id(None)


def test_parse_replaces_invalid_id() -> None:
    assert parse_trace_id("bad\nid") != "bad\nid"
    assert len(parse_trace_id("x" * 65)) == 32
    assert len(parse_trace_id("")) == 32


def test_set_and_reset_restore_previous_value() -> None:
    assert get_trace_id() is None
    token = set_trace_id("t1")
    assert get_trace_id() == "t1"
    reset_trace_id(token)
    assert get_trace_id() is None


def test_trace_headers() -> None:
    assert trace_headers() == {}
    token = set_trace_id("t2")
    try:
        assert trace_headers() == {"X-Trace-Id": "t2"}
    finally:
        reset_trace_id(token)


def _record() -> logging.LogRecord:
    return logging.LogRecord("n", logging.INFO, "f", 1, "m", None, None)


def test_filter_adds_trace_id_to_record() -> None:
    token = set_trace_id("t3")
    try:
        record = _record()
        assert TraceIdFilter().filter(record) is True
        assert record.trace_id == "t3"
    finally:
        reset_trace_id(token)


def test_filter_uses_dash_outside_request() -> None:
    record = _record()
    TraceIdFilter().filter(record)
    assert record.trace_id == "-"
