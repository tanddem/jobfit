"""Fetching a job description from a link.

Plain HTTP first; a headless browser when the page needs JavaScript to show
its text or turns plain HTTP clients away. Every address contacted, including
each redirect hop and each request the browser makes, must resolve to a
public IP. Private, loopback, link-local (cloud metadata), multicast and
reserved addresses are refused, so a link cannot be used to reach the
server's own network. The browser may not open WebSockets at all.

Known gap: a host is checked by one DNS lookup and connected to by another,
so DNS that answers differently between the two (DNS rebinding) is not
caught yet.
"""

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx2
import trafilatura
from pydantic import BaseModel

MIN_TEXT_CHARS = 200
MAX_TEXT_CHARS = 20_000
MAX_BODY_BYTES = 2 * 1024 * 1024
MAX_REDIRECTS = 5
HTTP_TIMEOUT_SECONDS = 15
BROWSER_TIMEOUT_MS = 30_000
REDIRECT_STATUSES = {301, 302, 303, 307, 308}
TURNED_AWAY_STATUSES = {401, 403, 429}
USER_AGENT = "Mozilla/5.0 (compatible; JobFit/1.0; +https://github.com/tanddem/jobfit)"
BROWSER_ARGS = ["--force-webrtc-ip-handling-policy=disable_non_proxied_udp"]


class JdFetchError(Exception):
    """The link could not be turned into job description text; status_code is the HTTP status to return."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


class FetchedJd(BaseModel):
    jd_text: str
    final_url: str


@dataclass
class HttpPage:
    status: int
    location: str | None
    body: bytes


def resolve(host):
    """Every IP address the host name resolves to."""
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def is_public(address):
    ip = ipaddress.ip_address(address.split("%")[0])
    ip = getattr(ip, "ipv4_mapped", None) or ip
    return ip.is_global and not ip.is_multicast


def check_url(url, resolve_fn=resolve):
    """Raise JdFetchError unless url is http(s) and its host resolves only to public addresses.

    An IP-address host is checked as written, without asking DNS.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
        if parts.scheme not in ("http", "https") or not host:
            raise JdFetchError(400, "Enter a full link starting with http:// or https://.")
        try:
            addresses = [str(ipaddress.ip_address(host))]
        except ValueError:
            addresses = resolve_fn(host)
    except (ValueError, OSError):
        raise JdFetchError(400, "That link could not be read. Check it and try again.")
    if not addresses or not all(is_public(a) for a in addresses):
        raise JdFetchError(400, "That link points to a private network address.")


def follow_redirects(url, fetch_one, resolve_fn):
    """Fetch url, following redirects one hop at a time and checking each.

    fetch_one(url) returns (status, location, payload) for a single request;
    this returns (final_url, status, payload) for the first non-redirect.
    """
    for _ in range(MAX_REDIRECTS + 1):
        check_url(url, resolve_fn)
        status, location, payload = fetch_one(url)
        if status not in REDIRECT_STATUSES:
            return url, status, payload
        if not location:
            raise JdFetchError(400, "That page redirected without saying where to.")
        url = urljoin(url, location)
    raise JdFetchError(400, "That link redirects too many times.")


def http_get(url):
    """GET url without following redirects, reading at most MAX_BODY_BYTES within HTTP_TIMEOUT_SECONDS."""
    deadline = time.monotonic() + HTTP_TIMEOUT_SECONDS
    with httpx2.stream(
        "GET", url, follow_redirects=False, timeout=HTTP_TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    ) as response:
        body = b""
        for chunk in response.iter_bytes():
            body += chunk
            if len(body) > MAX_BODY_BYTES:
                raise JdFetchError(400, "That page is too large to read.")
            if time.monotonic() > deadline:
                raise JdFetchError(400, "That page took too long to load.")
        return HttpPage(status=response.status_code, location=response.headers.get("location"), body=body)


def fetch_http(url, *, get=http_get, resolve_fn=resolve):
    """Return (final_url, html bytes) over plain HTTP; empty html when the site turns plain clients away."""

    def fetch_one(target):
        try:
            page = get(target)
        except (httpx2.HTTPError, httpx2.InvalidURL):
            raise JdFetchError(400, "That page could not be fetched.")
        return page.status, page.location, page.body

    final_url, status, body = follow_redirects(url, fetch_one, resolve_fn)
    if status in TURNED_AWAY_STATUSES:
        return final_url, b""
    if status >= 400:
        raise JdFetchError(400, f"That page returned an error ({status}).")
    return final_url, body


def browser_render(url, resolve_fn=resolve):
    """Render url in headless Chromium and return (final_url, html).

    Every request the page makes goes through the guard. Chromium does not
    route the follow-up of a redirect it was handed, so the guard follows
    redirect chains itself and only ever hands the browser a final response.
    WebSockets, which page.route never sees, get a handler that never
    connects them to a server, so Playwright fakes the socket and nothing
    leaves the browser. (Calling ws.close() from a sync handler deadlocks.)
    """
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    def guard(route):
        def fetch_one(target):
            response = route.fetch(url=target, max_redirects=0)
            return response.status, response.headers.get("location"), response

        try:
            _, _, response = follow_redirects(route.request.url, fetch_one, resolve_fn)
            if len(response.body()) > MAX_BODY_BYTES:
                raise JdFetchError(400, "Response too large.")
        except (JdFetchError, PlaywrightError):
            route.abort()
            return
        route.fulfill(response=response)

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(args=BROWSER_ARGS)
            try:
                page = browser.new_page(user_agent=USER_AGENT, service_workers="block")
                page.route_web_socket("**/*", lambda ws: None)
                page.route("**/*", guard)
                page.goto(url, timeout=BROWSER_TIMEOUT_MS, wait_until="networkidle")
                return page.url, page.content()
            finally:
                browser.close()
    except PlaywrightError:
        raise JdFetchError(502, "That page could not be opened in the browser.")


def extract_text(html):
    """The main article text of a page, or an empty string."""
    return (trafilatura.extract(html, favor_precision=True, include_comments=False) or "").strip()


def fetch_jd(url, *, get=http_get, render=browser_render, resolve_fn=resolve):
    """Turn a job posting link into job description text, using the browser only when HTTP finds too little."""
    final_url, html = fetch_http(url.strip(), get=get, resolve_fn=resolve_fn)
    text = extract_text(html) if html else ""
    if len(text) < MIN_TEXT_CHARS:
        final_url, html = render(final_url, resolve_fn)
        check_url(final_url, resolve_fn)
        text = extract_text(html)
    if len(text) < MIN_TEXT_CHARS:
        raise JdFetchError(400, "Not enough job description text was found on that page. Paste the text instead.")
    return FetchedJd(jd_text=text[:MAX_TEXT_CHARS], final_url=final_url)
