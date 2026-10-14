"""Polite JSON requests to a source's API.

One request per `min_interval` seconds by default, bounded retries on 429 and 5xx honouring
Retry-After, and no retry when TLS verification fails (a missing CA bundle does not heal).
Responses are untrusted: callers validate what they read.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable

from .source import ApiError

USER_AGENT = "gtfs-fr-monitor (+https://github.com/ttezer/gtfs-fr-monitor)"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

Transport = Callable[[str, float], tuple[int, dict[str, str], bytes]]


class NotFound(ApiError):
    """The API answered 404."""


def urllib_transport(url: str, timeout: float, user_agent: str = USER_AGENT) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": user_agent})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, dict(response.headers.items()), response.read()
    except urllib.error.HTTPError as err:
        return err.code, dict(err.headers.items()) if err.headers else {}, err.read() or b""


class JsonClient:
    def __init__(
        self,
        base_url: str,
        transport: Transport = urllib_transport,
        min_interval: float = 1.0,
        max_retries: int = 4,
        backoff_base: float = 2.0,
        max_backoff: float = 60.0,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self._min_interval = min_interval
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._max_backoff = max_backoff
        self._timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.request_count = 0

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            remaining = self._min_interval - (self._clock() - self._last_request)
            if remaining > 0:
                self._sleep(remaining)
        self._last_request = self._clock()

    def _retry_delay(self, attempt: int, headers: dict[str, str]) -> float:
        retry_after = {k.lower(): v for k, v in headers.items()}.get("retry-after")
        if retry_after is not None and retry_after.strip().isdigit():
            return min(float(retry_after.strip()), self._max_backoff)
        return min(self._backoff_base**attempt, self._max_backoff)

    def get_json(self, path: str, params: dict[str, object] | None = None) -> object:
        url = f"{self.base_url}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        last_error = ""
        for attempt in range(self._max_retries + 1):
            self._wait_turn()
            self.request_count += 1
            try:
                status, headers, body = self._transport(url, self._timeout)
            except (ssl.SSLCertVerificationError, urllib.error.URLError) as err:
                reason = getattr(err, "reason", err)
                if isinstance(reason, ssl.SSLCertVerificationError):
                    # Not transient: retrying cannot fix a missing or wrong CA bundle.
                    raise ApiError(f"TLS certificate verification failed for {path}: {reason}") from err
                status, headers, body = None, {}, b""
                last_error = f"network error: {err}"
            except (TimeoutError, ConnectionError, OSError) as err:
                status, headers, body = None, {}, b""
                last_error = f"network error: {err}"
            if status == 200:
                try:
                    return json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as err:
                    raise ApiError(f"invalid JSON from {path}: {err}") from err
            if status == 404:
                raise NotFound(f"404 for {path}")
            if status is not None and status not in RETRY_STATUSES:
                raise ApiError(f"HTTP {status} for {path}")
            if status is not None:
                last_error = f"HTTP {status}"
            if attempt < self._max_retries:
                self._sleep(self._retry_delay(attempt, headers))
        raise ApiError(f"giving up on {path} after {self._max_retries + 1} attempts: {last_error}")
