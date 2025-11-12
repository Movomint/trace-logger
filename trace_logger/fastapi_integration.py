from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

if TYPE_CHECKING:
    from .logger import TraceLogger

__all__ = ["TraceLoggingMiddleware", "setup_observability"]


class TraceLoggingMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, trace_logger: "TraceLogger") -> None:
        super().__init__(app)
        self.trace_logger = trace_logger

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        trace_id_header = request.headers.get("x-trace-id")
        trace_id = self.trace_logger.ensure_trace_id(trace_id_header)
        request_payload = await self._extract_request_payload(request)
        metadata = {
            "query_params": dict(request.query_params),
            "user_agent": request.headers.get("user-agent"),
        }

        caller_service = request.headers.get("x-caller-service")
        caller_user_id = request.headers.get("x-user-id")
        caller_ip = request.client.host if request.client else None

        with self.trace_logger.capture_request(
            direction="inbound",
            route=self._resolve_route(request),
            method=request.method,
            caller_service=caller_service,
            caller_user_id=caller_user_id,
            caller_ip=caller_ip,
            request_payload=request_payload,
            metadata=metadata,
            trace_id=trace_id,
        ) as capture:
            response = await call_next(request)
            capture.set_response(status_code=response.status_code)

        response.headers["x-trace-id"] = trace_id
        return response

    async def _extract_request_payload(self, request: Request) -> Optional[Dict[str, Any]]:
        try:
            body = await request.body()
        except Exception:
            return None

        if not body:
            return None

        # Allow downstream handlers to re-read the body.
        request._body = body  # type: ignore[attr-defined]

        content_type = request.headers.get("content-type", "")
        try:
            if "application/json" in content_type:
                return json.loads(body.decode("utf-8"))
            if "application/x-www-form-urlencoded" in content_type:
                return dict(parse_qsl(body.decode("utf-8")))
        except Exception:
            return {"raw": body[:2048].decode("utf-8", errors="ignore")}

        return None

    def _resolve_route(self, request: Request) -> str:
        route = request.scope.get("route")
        if route and hasattr(route, "path"):
            return route.path  # type: ignore[attr-defined]
        return request.url.path


def setup_observability(
    app: FastAPI,
    service_name: Optional[str] = None,
    environment: Optional[str] = None,
    api_url: Optional[str] = None,
    redact_keys: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> Optional["TraceLogger"]:
    """
    Set up observability for a FastAPI application.

    This function configures and enables trace logging middleware automatically.
    All parameters are optional and will use sensible defaults from environment variables.

    Args:
        app: The FastAPI application instance
        service_name: Service name for logging (default: from TRACE_LOGGER_SERVICE_NAME env var, fallback to app.title)
        environment: Environment name (default: from ENV env var, fallback to "local")
        api_url: Internal API URL for sending logs (default: from TRACE_LOGGER_API_URL or INTERNAL_API_BASE_URL env vars)
        redact_keys: Comma-separated keys to redact from payloads (default: from TRACE_LOGGER_REDACT_KEYS env var)
        enabled: Whether to enable observability (default: from TRACE_LOGGER_ENABLED env var, default True)

    Returns:
        TraceLogger instance if enabled, None otherwise
    """
    try:
        from .logger import TraceLogger
        from .config import TraceLoggerConfig
    except ImportError:
        import logging
        logging.getLogger(__name__).warning(
            "trace_logger package components not available; observability setup skipped."
        )
        return None

    # Check if enabled (default True)
    if enabled is None:
        enabled = os.environ.get("TRACE_LOGGER_ENABLED", "true").lower() == "true"

    if not enabled:
        return None

    # Set defaults from environment or parameters
    final_service_name = service_name or os.environ.get("TRACE_LOGGER_SERVICE_NAME")
    if not final_service_name and hasattr(app, 'title'):
        final_service_name = app.title.lower().replace(' ', '_')
    final_service_name = final_service_name or "unknown_service"

    final_environment = environment or os.environ.get("ENV", "local")
    final_api_url = api_url or os.environ.get("TRACE_LOGGER_API_URL") or os.environ.get("INTERNAL_API_BASE_URL", "http://internal-api:8005")

    # Parse redact keys
    final_redact_keys = ()
    if redact_keys:
        final_redact_keys = tuple(key.strip() for key in redact_keys.split(",") if key.strip())
    else:
        redact_keys_env = os.environ.get("TRACE_LOGGER_REDACT_KEYS")
        if redact_keys_env:
            final_redact_keys = tuple(key.strip() for key in redact_keys_env.split(",") if key.strip())

    # Create logger and add middleware
    config = TraceLoggerConfig(
        service_name=final_service_name,
        environment=final_environment,
        api_url=final_api_url,
        redact_keys=final_redact_keys,
    )

    trace_logger = TraceLogger(config)
    app.add_middleware(TraceLoggingMiddleware, trace_logger=trace_logger)

    # Add shutdown handler
    @app.on_event("shutdown")
    async def shutdown_trace_logger():
        trace_logger.shutdown()

    return trace_logger
