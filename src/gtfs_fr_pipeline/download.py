"""Temporary download of one generation ZIP (data-model §1).

The URL must pass a host check: by default transport.data.gouv.fr's archive of resource files,
where every archived file has a permanent URL. Redirects are followed only to https and never
logged, returned or stored. The size is capped both by Content-Length and while streaming.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

from .http import USER_AGENT

HISTORY_HOST = "transport-data-gouv-fr-resource-history-prod.cellar-c2.services.clever-cloud.com"


def is_history_url(url: object) -> bool:
    """An archived resource file on transport.data.gouv.fr (permanent_url)."""
    if not isinstance(url, str):
        return False
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname == HISTORY_HOST and parts.username is None

DEFAULT_MAX_BYTES = 512 * 1024 * 1024
CHUNK = 1 << 16


class DownloadError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code  # SOURCE_UNAVAILABLE, TOO_LARGE, DOWNLOAD_FAILED, UNTRUSTED_URL
        self.detail = detail


@dataclass(frozen=True)
class Downloaded:
    path: Path
    sha256: str
    size: int


class _HttpsOnlyRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.lower().startswith("https://"):
            # Do not echo newurl: a signed URL must not reach logs or error messages.
            raise urllib.error.URLError("refused non-https redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


Opener = Callable[[str, float], tuple[int, dict[str, str], BinaryIO]]


def urllib_opener(url: str, timeout: float, user_agent: str = USER_AGENT) -> tuple[int, dict[str, str], BinaryIO]:
    opener = urllib.request.build_opener(_HttpsOnlyRedirects())
    request = urllib.request.Request(url, headers={"User-Agent": user_agent})
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as err:
        return err.code, {}, err
    return response.status, dict(response.headers.items()), response


def download_zip(
    url: str,
    dest: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    timeout: float = 300,
    opener: Opener = urllib_opener,
    allowed: Callable[[object], bool] = is_history_url,
) -> Downloaded:
    """Stream `url` to `dest`, hashing on the way. `dest` is removed on any failure.

    `allowed` is the source's host check; another source passes its own (and its opener for its User-Agent).
    """
    if not allowed(url):
        raise DownloadError("UNTRUSTED_URL", "download URL is not on the source's download host")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        status, headers, stream = opener(url, timeout)
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as err:
        raise DownloadError("DOWNLOAD_FAILED", type(err).__name__) from None
    try:
        if status in (404, 410):
            raise DownloadError("SOURCE_UNAVAILABLE", f"HTTP {status}")
        if status != 200:
            raise DownloadError("DOWNLOAD_FAILED", f"HTTP {status}")
        length = {k.lower(): v for k, v in headers.items()}.get("content-length")
        if length is not None and length.strip().isdigit() and int(length) > max_bytes:
            raise DownloadError("TOO_LARGE", f"Content-Length {int(length)} exceeds {max_bytes}")
        digest = hashlib.sha256()
        size = 0
        with open(dest, "wb") as out:
            while True:
                try:
                    block = stream.read(CHUNK)
                except (TimeoutError, ConnectionError, OSError) as err:
                    raise DownloadError("DOWNLOAD_FAILED", type(err).__name__) from None
                if not block:
                    break
                size += len(block)
                if size > max_bytes:
                    raise DownloadError("TOO_LARGE", f"stream exceeds {max_bytes} bytes")
                digest.update(block)
                out.write(block)
        if size == 0:
            raise DownloadError("DOWNLOAD_FAILED", "empty response")
        return Downloaded(dest, digest.hexdigest(), size)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
