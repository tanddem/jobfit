"""Integration tests that render real pages in headless Chromium against a local server.

The fake resolver makes the host name "localhost" look public while it really
reaches the local server, and IP-literal addresses such as 127.0.0.1 stay
refused. That lets these tests prove the browser guard blocks requests and
redirect hops to refused addresses. Skipped when Playwright's Chromium is not
installed.
"""

import os
import socketserver
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.jd_fetch import JdFetchError, browser_render, extract_text


def chromium_installed():
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            return os.path.exists(playwright.chromium.executable_path)
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not chromium_installed(), reason="playwright install chromium to run browser tests")

JD_TEXT = (
    "Senior Backend Engineer. You will design and run the payout services behind our payments platform. "
    "Requirements: five or more years of Python, FastAPI, PostgreSQL and Redis, Docker and Kubernetes in production."
)


class LocalServer(ThreadingHTTPServer):
    """An HTTP server that skips the reverse DNS lookup HTTPServer does on bind, which can stall for seconds."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


@pytest.fixture
def server():
    """A local site: a JavaScript-rendered job page that also tries to reach a private address."""
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            hits.append(self.path)
            port = self.server.server_address[1]
            if self.path == "/job":
                body = f"""<html><body><article id="jd"></article><script>
                    document.getElementById('jd').innerHTML = '<h1>Job</h1><p>{JD_TEXT}</p>';
                    fetch('http://127.0.0.1:{port}/secret').catch(() => {{}});
                </script></body></html>"""
                self.reply(200, body)
            elif self.path == "/socket":
                body = f"""<html><body><p>{JD_TEXT}</p><script>
                    new WebSocket('ws://127.0.0.1:{port}/ws-private');
                    new WebSocket('ws://localhost:{port}/ws-public');
                    fetch('/slow');
                </script></body></html>"""
                self.reply(200, body)
            elif self.path == "/slow":
                threading.Event().wait(1.5)
                self.reply(200, "ok")
            elif self.path == "/to-job":
                self.send_response(302)
                self.send_header("Location", "/job")
                self.end_headers()
            elif self.path == "/hop":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{port}/secret")
                self.end_headers()
            else:
                self.reply(200, "<html><body>secret</body></html>")

        def reply(self, status, body):
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())

    httpd = LocalServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://localhost:{httpd.server_address[1]}", hits
    httpd.shutdown()


def looks_public(host):
    """Treat the "localhost" host name as public; IP-literal addresses such as 127.0.0.1 stay refused."""
    return ["93.184.215.14"] if host == "localhost" else ["10.0.0.1"]


def test_renders_javascript_page_and_blocks_its_private_request(server):
    base, hits = server
    final_url, html = browser_render(f"{base}/job", looks_public)
    assert final_url == f"{base}/job"
    assert "PostgreSQL and Redis" in extract_text(html)
    assert "/secret" not in hits


def test_redirect_hop_to_private_address_is_blocked(server):
    base, hits = server
    with pytest.raises(JdFetchError):
        browser_render(f"{base}/hop", looks_public)
    assert "/hop" in hits
    assert "/secret" not in hits


def test_redirect_hop_to_public_address_is_followed(server):
    base, hits = server
    final_url, html = browser_render(f"{base}/to-job", looks_public)
    assert "PostgreSQL and Redis" in extract_text(html)
    assert hits[:2] == ["/to-job", "/job"]


def test_page_cannot_open_websockets(server):
    base, hits = server
    browser_render(f"{base}/socket", looks_public)
    assert not any(path.startswith("/ws") for path in hits)
