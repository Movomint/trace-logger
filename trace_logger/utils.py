from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping
import socket


def utc_iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def get_host_name() -> str:
    return socket.gethostname()


def redact_payload(payload: Any, redact_keys: Iterable[str]) -> Any:
    if not isinstance(payload, Mapping):
        return payload

    redact_set = {key.lower() for key in redact_keys}

    def _redact(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {k: _redact("<<redacted>>" if k.lower() in redact_set else v) for k, v in value.items()}
        if isinstance(value, list):
            return [_redact(item) for item in value]
        return value

    return _redact(payload)
