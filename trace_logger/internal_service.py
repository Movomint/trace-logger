from interservice import BaseHTTPService, Services


class InternalObservabilityService(BaseHTTPService):
    SERVICE = Services.INTERNAL_API

    def __init__(self, api_url: str | None = None) -> None:
        super().__init__(self.SERVICE)
        if api_url:
            self.base_url = api_url.rstrip("/")

    async def send_logs(self, payload: dict) -> None:
        await self._call_("POST", "/observability/logs", json=payload)

    async def send_error_logs(self, payload: dict) -> None:
        await self._call_("POST", "/observability/error-logs", json=payload)
