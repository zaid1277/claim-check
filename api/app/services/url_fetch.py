import gzip
import http.client
import io
import ipaddress
import socket
import ssl
import zlib
from urllib.parse import urljoin, urlsplit

from app.core.errors import ProviderError


def public_address(url: str) -> tuple[str, int, str]:
    """Validate all DNS answers and return one address to pin for this request."""
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or len(url) > 2048
    ):
        raise ProviderError("Use a public HTTP or HTTPS URL.", category="invalid-url")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port not in {80, 443}:
            raise ValueError
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        ips = [item[4][0] for item in addresses]
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            raise ValueError
    except (ValueError, OSError) as exc:
        raise ProviderError(
            "The URL must resolve to a public web server.", category="dns-error"
        ) from exc
    return parsed.hostname, port, ips[0]


# Remediation pass 5, part 11: 2 MB was tight enough to reject long but
# entirely legitimate real articles outright (measured failure: full
# Wikipedia pages exceeding it purely on markup/script weight, not content
# length). Raised to a still-bounded 6 MB -- a general limit increase, not
# a site-specific allowance.
DEFAULT_MAX_BYTES = 6_000_000


def fetch_html(url: str, max_bytes: int = DEFAULT_MAX_BYTES) -> tuple[str, str]:
    """Fetch bounded HTML, retrying once on a transient network failure.

    Remediation pass 5, part 11: diagnostic testing against real URLs found
    a meaningful share of "network-error" failures were transient (a
    fresh, immediate retry of the exact same request succeeded) rather
    than a genuine, persistent problem with the page -- ordinary internet
    flakiness, not a defect specific to any site. One retry is standard,
    general HTTP-client practice; deterministic outcomes (bot protection,
    404s, unsupported content type, download limit) are never retried,
    since a second attempt cannot change them.
    """
    try:
        return _fetch_html_once(url, max_bytes)
    except ProviderError as exc:
        if exc.category != "network-error":
            raise
        return _fetch_html_once(url, max_bytes)


def _fetch_html_once(url: str, max_bytes: int) -> tuple[str, str]:
    try:
        for _ in range(4):
            host, port, address = public_address(url)
            parsed = urlsplit(url)
            connection = http.client.HTTPConnection(host, port, timeout=10)
            try:
                connection.sock = socket.create_connection((address, port), timeout=10)
                if parsed.scheme == "https":
                    connection.sock = ssl.create_default_context().wrap_socket(
                        connection.sock, server_hostname=host
                    )
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                connection.request(
                    "GET",
                    path,
                    headers={
                        "User-Agent": "ClaimCheck/1.0 (evidence research)",
                        "Accept": "text/html, text/plain",
                        "Accept-Encoding": "identity",
                    },
                )
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise ProviderError(
                            "The page has an invalid redirect.",
                            category="redirect-error",
                        )
                    url = urljoin(url, location)
                    continue
                if response.status != 200:
                    # Remediation pass 5, part 10: distinguish access-denial
                    # (bot/WAF protection -- explicitly not to be bypassed,
                    # per part 11) and not-found from other server errors,
                    # for diagnosis only; the user-facing message is
                    # unchanged in every case.
                    category = (
                        "bot-protection-or-access-denied"
                        if response.status in {401, 403, 429}
                        else "not-found"
                        if response.status in {404, 410}
                        else "http-error"
                    )
                    raise ProviderError(
                        "The page cannot be read. Paste the article text instead.",
                        category=category,
                    )
                content_type = response.getheader("Content-Type", "").lower()
                if not any(
                    t in content_type
                    for t in ("text/html", "text/plain", "application/xhtml+xml")
                ):
                    raise ProviderError(
                        "This URL does not contain a readable article.",
                        category="unsupported-content-type",
                    )
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ProviderError(
                        "The article exceeds the download limit.",
                        category="download-limit-exceeded",
                    )
                encoding = response.getheader("Content-Encoding", "identity").lower()
                charset = response.headers.get_content_charset() or "utf-8"
                return decode_body(data, encoding, charset, max_bytes), url
            finally:
                connection.close()
        raise ProviderError(
            "The page redirects too many times.", category="redirect-loop"
        )
    except (OSError, ValueError, http.client.HTTPException) as exc:
        category = "tls-error" if isinstance(exc, ssl.SSLError) else "network-error"
        raise ProviderError(
            "The page cannot be read. Paste the article text instead.",
            category=category,
        ) from exc


def decode_body(data: bytes, encoding: str, charset: str, max_bytes: int) -> str:
    """Bound decompressed output too; compressed bodies can expand dramatically."""
    try:
        if encoding == "gzip":
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as compressed:
                data = compressed.read(max_bytes + 1)
        elif encoding == "deflate":
            decoder = zlib.decompressobj()
            data = decoder.decompress(data, max_bytes + 1)
            if len(data) <= max_bytes and not decoder.eof:
                raise ProviderError("The article response is incomplete.")
        elif encoding not in {"identity", ""}:
            raise ProviderError(
                "The page uses unsupported compression. Paste its text."
            )
        if len(data) > max_bytes:
            raise ProviderError("The article exceeds the download limit.")
        return data.decode(charset, errors="replace")
    except (OSError, EOFError, zlib.error, LookupError) as exc:
        raise ProviderError(
            "The article could not be decoded. Paste its text instead."
        ) from exc
