import time
from collections import deque
from threading import Lock

from starlette.responses import JSONResponse

from app.core.settings import get_settings


class RequestLimits:
    """Bound request bodies and per-peer creation traffic in a single API process."""

    def __init__(self, app):
        self.app = app
        self.requests: dict[str, deque] = {}
        self.lock = Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            return await self.app(scope, receive, send)
        settings = get_settings()
        now = time.monotonic()
        # Do not trust user-supplied forwarded IP headers for rate-limit identity.
        peer = (scope.get("client") or ("unknown",))[0]
        with self.lock:
            self.requests = {
                key: value
                for key, value in self.requests.items()
                if value and now - value[-1] < 60
            }
            bucket = self.requests.setdefault(peer, deque())
            while bucket and now - bucket[0] >= 60:
                bucket.popleft()
            limited = len(bucket) >= settings.requests_per_minute
            if not limited:
                bucket.append(now)
        if limited:
            response = JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Too many requests. Try again in a minute.",
                    }
                },
            )
            return await response(scope, receive, send)
        max_bytes = (
            settings.max_image_bytes
            if scope["path"].endswith("/inputs/image")
            else 100_000
        )
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > max_bytes:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "BODY_TOO_LARGE",
                            "message": "The uploaded request is too large.",
                        }
                    },
                )
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
