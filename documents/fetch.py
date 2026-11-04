"""
documents/fetch.py — fetch a user-supplied link safely.

Every server-side fetch of a user URL goes through `safe_download`:
  * http/https only, default ports only (80/443);
  * the host is resolved once and EVERY address must be public (no private,
    loopback, link-local, CGNAT, multicast or reserved ranges);
  * the connection goes to that checked IP (Host header + TLS SNI keep the
    real name), so DNS can't be rebound between the check and the connect;
  * redirects are followed by hand, re-checking each hop (max 5);
  * a byte cap while streaming and a content-type check.

`rewrite_link` maps share links to direct downloads: Dropbox (dl=1), Google
Docs/Slides (export as docx/pptx). Plain Google Drive files go through gdown in
ingest/ingest.py (fixed Google hosts, no user-controlled host).
"""

from __future__ import annotations

import ipaddress
import logging
import os
import re
import socket
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import httpx

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
TIMEOUT = httpx.Timeout(20.0, connect=10.0)
MAX_DOC_BYTES = int(os.environ.get("NORAI_MAX_DOC_BYTES", str(50 * 1024**2)))
MAX_HTML_BYTES = 5 * 1024**2
USER_AGENT = "Mozilla/5.0 (compatible; NorAI/1.0; study-notes fetcher)"


class FetchError(ValueError):
    """A link we won't or can't fetch, with a message fit to show the user."""


class IsVideoLink(FetchError):
    """The link is a video file and the caller asked not to download videos."""


@dataclass
class Fetched:
    path: Path
    content_type: str
    final_url: str
    filename: str


# ── address checks ────────────────────────────────────────────────────────────

_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def is_public_ip(ip: str) -> bool:
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return not (
        addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_multicast
        or addr.is_reserved or addr.is_unspecified
        or (isinstance(addr, ipaddress.IPv4Address) and addr in _CGNAT)
    )


def resolve_public(host: str, port: int) -> str:
    """One public IP for `host`, or FetchError if any resolved address isn't public."""
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise FetchError(f"Couldn't find the site {host!r}. Check the link.") from e
    ips = sorted({i[4][0] for i in infos}, key=lambda ip: ":" in ip)  # IPv4 first
    if not ips:
        raise FetchError(f"Couldn't find the site {host!r}. Check the link.")
    bad = [ip for ip in ips if not is_public_ip(ip)]
    if bad:
        raise FetchError("That link points to a private or local address, which isn't allowed.")
    return ips[0]


def check_url(url: str) -> tuple[str, str, int]:
    """Validate a URL's shape. Returns (scheme, host, port)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("Only http:// and https:// links are supported.")
    if p.username or p.password:
        raise FetchError("Links with a username or password aren't supported.")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port not in (80, 443):
        raise FetchError("Links on non-standard ports aren't supported.")
    return p.scheme, p.hostname, port


# ── share-link rewriting ──────────────────────────────────────────────────────

_GDOC = re.compile(r"^/(document|presentation)/d/([a-zA-Z0-9_-]{10,})")


def google_export_url(url: str) -> str | None:
    """Google Docs / Slides link → its export URL (docx / pptx); None otherwise."""
    p = urlparse(url)
    if (p.hostname or "").lower() != "docs.google.com":
        return None
    m = _GDOC.match(p.path)
    if not m:
        return None
    kind, doc_id = m.groups()
    fmt = "docx" if kind == "document" else "pptx"
    return f"https://docs.google.com/{kind}/d/{doc_id}/export?format={fmt}"


def rewrite_link(url: str) -> str:
    gexport = google_export_url(url)
    if gexport:
        return gexport
    p = urlparse(url)
    host = (p.hostname or "").lower()
    if host in ("www.dropbox.com", "dropbox.com"):
        q = parse_qs(p.query)
        q["dl"] = ["1"]
        return urlunparse(p._replace(query=urlencode(q, doseq=True)))
    return url


# ── download ──────────────────────────────────────────────────────────────────

_ALLOWED_CTYPES = (
    "text/html", "application/xhtml+xml", "text/plain", "text/markdown",
    "application/pdf", "application/octet-stream", "binary/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/zip", "application/x-zip-compressed",
    "application/msword", "application/vnd.ms-powerpoint",  # rejected later with a clear message
)


def _ctype_ok(ctype: str) -> bool:
    return not ctype or ctype in _ALLOWED_CTYPES or ctype.startswith("video/")


def _filename(resp: httpx.Response, url: str) -> str:
    cd = resp.headers.get("content-disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search(r'filename="?([^";]+)"?', cd)
    name = m.group(1) if m else Path(urlparse(url).path).name
    from urllib.parse import unquote
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", unquote(name))[:120] or "download"


def safe_download(url: str, dest_dir: str | Path, *, max_bytes: int = MAX_DOC_BYTES,
                  max_video_bytes: int | None = None) -> Fetched:
    """Download `url` into `dest_dir` under the SSRF rules above. Without
    `max_video_bytes`, a video/* response raises IsVideoLink before its body
    is read."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    current = url
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False, trust_env=False) as client:
        for _ in range(MAX_REDIRECTS + 1):
            scheme, host, port = check_url(current)
            ip = resolve_public(host, port)
            p = urlparse(current)
            netloc_ip = f"[{ip}]" if ":" in ip else ip
            pinned = urlunparse(p._replace(netloc=netloc_ip if port in (80, 443) else f"{netloc_ip}:{port}"))
            req = client.build_request(
                "GET", pinned,
                headers={"Host": p.netloc.split("@")[-1], "User-Agent": USER_AGENT,
                         "Accept": "text/html,application/pdf,*/*;q=0.8"},
                extensions={"sni_hostname": host} if scheme == "https" else {},
            )
            try:
                resp = client.send(req, stream=True)
            except httpx.HTTPError as e:
                raise FetchError(f"Couldn't download that link ({type(e).__name__}).") from e
            try:
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("location")
                    if not loc:
                        raise FetchError("The link redirected without a target.")
                    current = urljoin(current, loc)
                    continue
                if resp.status_code in (401, 403):
                    raise FetchError("That link needs a login or isn't shared publicly. "
                                     "Make it viewable by anyone with the link, or upload the file.")
                if resp.status_code == 404:
                    raise FetchError("That link wasn't found (404).")
                if resp.status_code >= 400:
                    raise FetchError(f"The site returned an error ({resp.status_code}).")
                ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                if not _ctype_ok(ctype):
                    raise FetchError(f"That link is a {ctype or 'unknown'} file, which isn't supported.")
                if ctype.startswith("video/") and not max_video_bytes:
                    raise IsVideoLink("That link is a video file.")
                cap = max_bytes
                if ctype in ("text/html", "application/xhtml+xml"):
                    cap = min(max_bytes, MAX_HTML_BYTES)
                elif ctype.startswith("video/") and max_video_bytes:
                    cap = max_video_bytes
                declared = int(resp.headers.get("content-length") or 0)
                if declared > cap:
                    raise FetchError(f"That file is larger than the {cap // 1024**2} MB limit.")
                name = _filename(resp, current)
                path = dest_dir / name
                written = 0
                with open(path, "wb") as f:
                    for chunk in resp.iter_bytes(65536):
                        written += len(chunk)
                        if written > cap:
                            f.close()
                            path.unlink(missing_ok=True)
                            raise FetchError(f"That file is larger than the {cap // 1024**2} MB limit.")
                        f.write(chunk)
                logger.info("Fetched %s → %s (%d bytes, %s)", url, path.name, written, ctype)
                return Fetched(path, ctype, current, name)
            finally:
                resp.close()
    raise FetchError("That link redirected too many times.")
