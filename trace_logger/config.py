from dataclasses import dataclass, field
from typing import Iterable, Tuple


@dataclass(slots=True)
class TraceLoggerConfig:
    """Runtime configuration for TraceLogger."""

    service_name: str
    environment: str
    api_url: str
    batch_size: int = 20
    flush_interval: float = 2.0
    redact_keys: Tuple[str, ...] = field(default_factory=tuple)
    enable_console_fallback: bool = True

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.flush_interval <= 0:
            raise ValueError("flush_interval must be > 0")
        if self.api_url.endswith("/"):
            self.api_url = self.api_url[:-1]
        if isinstance(self.redact_keys, Iterable):
            self.redact_keys = tuple(str(key) for key in self.redact_keys)
