from contextvars import ContextVar
from typing import Optional

_trace_id_var: ContextVar[Optional[str]] = ContextVar("trace_logger_trace_id", default=None)


def get_trace_id() -> Optional[str]:
    return _trace_id_var.get()


def set_trace_id(trace_id: Optional[str]) -> None:
    _trace_id_var.set(trace_id)


def clear_trace_id() -> None:
    _trace_id_var.set(None)
