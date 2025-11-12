# trace_logger

Simple internal trace logging helper that captures request metadata and ships it to the internal observability API.

The exporter uses the shared `interservice` package, so make sure `INTERNAL_AUTH_SECRET` and the `interservice` base URLs are configured in the environment. You can override the internal API base URL per logger instance through `TraceLoggerConfig.api_url`.

## Quick start

```python
from trace_logger import TraceLogger, TraceLoggerConfig

logger = TraceLogger(
    TraceLoggerConfig(
        service_name="payments_api",
        environment="prod",
        api_url="https://internal-api.local",
    )
)

with logger.capture_request(
    direction="inbound",
    route="/v1/payments/{payment_id}",
    method="POST",
    caller_service="orders_api",
    caller_user_id="user_123",
    caller_ip="10.0.0.4",
    request_payload={"amount": 1200},
) as capture:
    # Your handler logic goes here.
    capture.set_response(status_code=201, response_payload={"status": "ok"})
```
