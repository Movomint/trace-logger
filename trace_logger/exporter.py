import asyncio
import queue
import threading
import time
from typing import List

from .config import TraceLoggerConfig
from .internal_service import InternalObservabilityService
from .models import TraceRecord


class LogExporter(threading.Thread):
    def __init__(self, config: TraceLoggerConfig) -> None:
        super().__init__(daemon=True)
        self.config = config
        self._queue: "queue.Queue[TraceRecord]" = queue.Queue()
        self._stop_event = threading.Event()
        self._client = InternalObservabilityService(api_url=self.config.api_url)

    def enqueue(self, record: TraceRecord) -> None:
        self._queue.put(record)

    def run(self) -> None:
        buffer: List[TraceRecord] = []
        last_flush = time.time()

        while not self._stop_event.is_set() or not self._queue.empty():
            timeout = max(self.config.flush_interval - (time.time() - last_flush), 0.1)
            try:
                record = self._queue.get(timeout=timeout)
                buffer.append(record)
            except queue.Empty:
                pass

            should_flush = (
                len(buffer) >= self.config.batch_size
                or (buffer and (time.time() - last_flush) >= self.config.flush_interval)
                or (self._stop_event.is_set() and buffer)
            )

            if should_flush:
                self._flush(buffer)
                buffer = []
                last_flush = time.time()

    def stop(self) -> None:
        self._stop_event.set()

    def _flush(self, records: List[TraceRecord]) -> None:
        # Separate error records (status >= 400) from regular records
        error_records = [r for r in records if r.status_code >= 400]
        all_records_payload = {
            "records": [record.to_payload() for record in records],
            "ingestion_version": 1,
        }

        try:
            # Send all records for aggregation
            asyncio.run(self._client.send_logs(all_records_payload))

            # Send error records for detailed debugging
            if error_records:
                error_payload = {
                    "records": [record.to_payload() for record in error_records],
                    "ingestion_version": 1,
                }
                asyncio.run(self._client.send_error_logs(error_payload))

        except Exception as exc:
            if self.config.enable_console_fallback:
                print(f"[trace_logger] failed to export logs: {exc}")
                for record in records:
                    print(record.to_payload())
