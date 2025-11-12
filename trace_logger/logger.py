from __future__ import annotations

import traceback
import uuid
from contextlib import contextmanager
from typing import Any, Dict, Optional
import time

from .config import TraceLoggerConfig
from .context import clear_trace_id, get_trace_id, set_trace_id
from .exporter import LogExporter
from .models import TraceRecord
from .utils import get_host_name, redact_payload, utc_iso_now


class TraceCapture:
    def __init__(self, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.status_code: Optional[int] = None
        self.response_payload: Optional[Dict[str, Any]] = None
        self.additional_metadata: Dict[str, Any] = metadata or {}
        self.error: Optional[BaseException] = None

    def set_response(self, *, status_code: int, response_payload: Optional[Dict[str, Any]] = None) -> None:
        self.status_code = status_code
        self.response_payload = response_payload

    def add_metadata(self, key: str, value: Any) -> None:
        self.additional_metadata[key] = value

    def set_error(self, error: BaseException) -> None:
        self.error = error


class TraceLogger:
    def __init__(self, config: TraceLoggerConfig) -> None:
        self.config = config
        self.host_name = get_host_name()
        self.exporter = LogExporter(config)
        self.exporter.start()

    def ensure_trace_id(self, trace_id: Optional[str] = None) -> str:
        current = trace_id or get_trace_id()
        if not current:
            current = str(uuid.uuid4())
        set_trace_id(current)
        return current

    def clear_trace(self) -> None:
        clear_trace_id()

    def log_event(
        self,
        *,
        direction: str,
        route: str,
        method: str,
        status_code: int,
        duration_ms: float,
        caller_service: Optional[str] = None,
        caller_user_id: Optional[str] = None,
        caller_ip: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        response_payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        error: Optional[BaseException] = None,
    ) -> str:
        normalized_trace_id = self.ensure_trace_id(trace_id)

        error_type: Optional[str] = None
        error_message: Optional[str] = None
        error_stack: Optional[str] = None
        if error:
            error_type = error.__class__.__name__
            error_message = str(error)
            error_stack = "".join(traceback.format_exception(error))

        record = TraceRecord(
            trace_id=normalized_trace_id,
            service=self.config.service_name,
            environment=self.config.environment,
            timestamp=utc_iso_now(),
            direction=direction,
            route=route,
            method=method,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            caller_service=caller_service,
            caller_user_id=caller_user_id,
            caller_ip=caller_ip,
            request_payload=redact_payload(request_payload, self.config.redact_keys) if request_payload else None,
            response_payload=redact_payload(response_payload, self.config.redact_keys) if response_payload else None,
            metadata=metadata,
            error_type=error_type,
            error_message=error_message,
            error_stack=error_stack,
            host_name=self.host_name,
        )

        self.exporter.enqueue(record)
        return normalized_trace_id

    @contextmanager
    def capture_request(
        self,
        *,
        direction: str,
        route: str,
        method: str,
        caller_service: Optional[str] = None,
        caller_user_id: Optional[str] = None,
        caller_ip: Optional[str] = None,
        request_payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ):
        trace_id = self.ensure_trace_id(trace_id)
        capture = TraceCapture(metadata=metadata)
        start = time.perf_counter()

        try:
            yield capture
        except Exception as exc:
            capture.set_error(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start) * 1000
            status_code = capture.status_code or (500 if capture.error else 200)
            self.log_event(
                direction=direction,
                route=route,
                method=method,
                status_code=status_code,
                duration_ms=duration_ms,
                caller_service=caller_service,
                caller_user_id=caller_user_id,
                caller_ip=caller_ip,
                request_payload=request_payload,
                response_payload=capture.response_payload,
                metadata=capture.additional_metadata,
                trace_id=trace_id,
                error=capture.error,
            )

    def shutdown(self, wait: bool = True) -> None:
        self.exporter.stop()
        if wait:
            self.exporter.join(timeout=self.config.flush_interval + 1)
