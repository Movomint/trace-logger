from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass(slots=True)
class TraceRecord:
    trace_id: str
    service: str
    environment: str
    timestamp: str
    direction: str
    route: str
    method: str
    status_code: int
    duration_ms: float
    caller_service: Optional[str] = None
    caller_user_id: Optional[str] = None
    caller_ip: Optional[str] = None
    request_payload: Optional[Dict[str, Any]] = None
    response_payload: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_stack: Optional[str] = None
    host_name: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}
