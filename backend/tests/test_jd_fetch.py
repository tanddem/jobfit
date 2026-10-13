"""Unit tests for fetching a JD from a link, with fake DNS, HTTP and browser."""

import httpx2
import pytest

from app.jd_fetch import (
    MAX_REDIRECTS,
    MAX_TEXT_CHARS,
    HttpPage,
    JdFetchError,
    check_url,
    fetch_jd,
)

PUBLIC = "93.184.215.14"
JD_TEXT = (
    "Senior Backend Engineer. You will design and run the payout services behind our payments "
    "platform. Requirements: five or more years of Python, FastAPI, PostgreSQL and Redis, Docker "
    "and Kubernetes in production, and AWS. Nice to have: Kafka and Terraform."
)
JD_PAGE = f"<html><head><title>Job</title></head><body><nav>Menu</nav><article><h1>Senior Backend Engineer</h1><p>{JD_TEXT}</p></article></body></html>".encode()
EMPTY_PAGE = b"<html><body><div id='root'></div><script src='app.js'></script></body></html>"


def resolver(table=None):
    """A fake DNS: hosts in table resolve as given, everything else to a public address."""
    table = table or {}
    return lambda host: table.get(host, [PUBLIC])


def pages(*replies):
    """A fake HTTP GET that returns replies in turn and records requested URLs."""
    replies = list(replies)
    seen = []

    def get(url):
        seen.append(url)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    get.seen = seen
    return get


def no_browser(url, resolve_fn):
    raise AssertionError("the browser should not be used")


def test_http_page_with_enough_text():
    result = fetch_jd("https://jobs.example.com/1", get=pages(HttpPage(200, None, JD_PAGE)), render=no_browser, resolve_fn=resolver())
    assert "FastAPI, PostgreSQL and Redis" in result.jd_text
    assert "Menu" not in result.jd_text
    assert result.final_url == "https://jobs.example.com/1"


def test_falls_back_to_browser_when_http_text_is_too_short():
    rendered = []

    def render(url, resolve_fn):
        rendered.append(url)
        return url, JD_PAGE.decode()

    result = fetch_jd("https://jobs.example.com/1", get=pages(HttpPage(200, None, EMPTY_PAGE)), render=render, resolve_fn=resolver())
    assert rendered == ["https://jobs.example.com/1"]
    assert "Kafka and Terraform" in result.jd_text


def test_too_little_text_even_in_browser_is_400():
    with pytest.raises(JdFetchError) as err:
        fetch_jd(
            "https://jobs.example.com/1",
            get=pages(HttpPage(200, None, EMPTY_PAGE)),
            render=lambda url, resolve_fn: (url, EMPTY_PAGE.decode()),
            resolve_fn=resolver(),
        )
    assert err.value.status_code == 400
    assert "Paste the text" in str(err.value)


def test_browser_ending_on_a_private_address_is_refused():
    with pytest.raises(JdFetchError):
        fetch_jd(
            "https://jobs.example.com/1",
            get=pages(HttpPage(200, None, EMPTY_PAGE)),
            render=lambda url, resolve_fn: ("http://internal.example/", JD_PAGE.decode()),
            resolve_fn=resolver({"internal.example": ["10.0.0.5"]}),
        )


def test_text_is_capped():
    long_page = f"<html><body><article><p>{'word ' * 10_000}</p></article></body></html>".encode()
    result = fetch_jd("https://jobs.example.com/1", get=pages(HttpPage(200, None, long_page)), render=no_browser, resolve_fn=resolver())
    assert len(result.jd_text) == MAX_TEXT_CHARS


@pytest.mark.parametrize("url", ["ftp://jobs.example.com/1", "file:///etc/passwd", "jobs.example.com/1", "https://"])
def test_rejects_non_http_links(url):
    with pytest.raises(JdFetchError) as err:
        check_url(url, resolver())
    assert err.value.status_code == 400


@pytest.mark.parametrize(
    "address",
    ["127.0.0.1", "10.1.2.3", "172.16.0.1", "192.168.1.1", "169.254.169.254", "100.64.0.1", "0.0.0.0", "224.0.0.1",
     "::1", "fe80::1", "fc00::1", "::ffff:127.0.0.1", "ff02::1"],
)
def test_rejects_non_public_addresses(address):
    with pytest.raises(JdFetchError):
        check_url("https://jobs.example.com/", resolver({"jobs.example.com": [address]}))


def test_rejects_host_with_any_private_address():
    with pytest.raises(JdFetchError):
        check_url("https://jobs.example.com/", resolver({"jobs.example.com": [PUBLIC, "10.0.0.1"]}))


def test_unknown_host_is_400():
    def fail(host):
        raise OSError("no such host")

    with pytest.raises(JdFetchError):
        check_url("https://nowhere.example/", fail)


def test_redirects_are_followed_and_each_hop_checked():
    get = pages(HttpPage(302, "/jobs/1", b""), HttpPage(301, "https://careers.example.com/1", b""), HttpPage(200, None, JD_PAGE))
    result = fetch_jd("https://jobs.example.com/old", get=get, render=no_browser, resolve_fn=resolver())
    assert get.seen == ["https://jobs.example.com/old", "https://jobs.example.com/jobs/1", "https://careers.example.com/1"]
    assert result.final_url == "https://careers.example.com/1"


def test_redirect_to_metadata_address_is_blocked_before_the_request():
    get = pages(HttpPage(302, "http://169.254.169.254/latest/meta-data/", b""))
    with pytest.raises(JdFetchError):
        fetch_jd("https://jobs.example.com/1", get=get, render=no_browser, resolve_fn=resolver())
    assert get.seen == ["https://jobs.example.com/1"]


def test_redirect_loop_stops():
    get = pages(*[HttpPage(302, "/again", b"")] * (MAX_REDIRECTS + 1))
    with pytest.raises(JdFetchError, match="too many"):
        fetch_jd("https://jobs.example.com/1", get=get, render=no_browser, resolve_fn=resolver())


def test_redirect_without_location_is_400():
    with pytest.raises(JdFetchError):
        fetch_jd("https://jobs.example.com/1", get=pages(HttpPage(302, None, b"")), render=no_browser, resolve_fn=resolver())


def test_http_error_status_is_400():
    with pytest.raises(JdFetchError, match="404"):
        fetch_jd("https://jobs.example.com/1", get=pages(HttpPage(404, None, b"")), render=no_browser, resolve_fn=resolver())


def test_network_failure_is_400():
    with pytest.raises(JdFetchError) as err:
        fetch_jd("https://jobs.example.com/1", get=pages(httpx2.ConnectError("down")), render=no_browser, resolve_fn=resolver())
    assert err.value.status_code == 400


@pytest.mark.parametrize("url", ["http://169.254.169.254/latest/", "http://127.0.0.1:8000/", "http://[::1]/"])
def test_ip_literal_hosts_are_checked_without_dns(url):
    with pytest.raises(JdFetchError):
        check_url(url, resolver())


@pytest.mark.parametrize("url", ["http://[abc", "http://" + "a" * 70 + ".com/", "http://exa mple.com/"])
def test_malformed_links_are_400_not_500(url):
    with pytest.raises(JdFetchError) as err:
        fetch_jd(url, get=pages(httpx2.InvalidURL("bad")), render=no_browser, resolve_fn=lambda host: [PUBLIC] if len(host) < 64 else (_ for _ in ()).throw(UnicodeError("label too long")))
    assert err.value.status_code == 400


@pytest.mark.parametrize("status", [401, 403, 429])
def test_sites_that_turn_plain_clients_away_get_the_browser(status):
    result = fetch_jd(
        "https://jobs.example.com/1",
        get=pages(HttpPage(status, None, b"Access denied")),
        render=lambda url, resolve_fn: (url, JD_PAGE.decode()),
        resolve_fn=resolver(),
    )
    assert "Kafka and Terraform" in result.jd_text
