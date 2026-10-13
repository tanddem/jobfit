"""Integration tests for POST /api/jd/fetch with an injected fetcher."""

from functools import partial

import pytest
from fastapi.testclient import TestClient

from app.jd_fetch import FetchedJd, JdFetchError
from app.main import create_app
from app.scoring import score
from conftest import register


def make_client(settings, stub_model, fetch_fn):
    app = create_app(settings, score_fn=partial(score, api_key="k", model="m", call=stub_model), jd_fetch_fn=fetch_fn)
    return TestClient(app)


def test_requires_sign_in(client):
    assert client.post("/api/jd/fetch", json={"url": "https://jobs.example.com/1"}).status_code == 401


def test_returns_fetched_text(settings, stub_model):
    calls = []

    def fetch(url):
        calls.append(url)
        return FetchedJd(jd_text="Senior Backend Engineer ...", final_url=url)

    with make_client(settings, stub_model, fetch) as browser:
        register(browser)
        response = browser.post("/api/jd/fetch", json={"url": "https://jobs.example.com/1"})
    assert response.status_code == 200
    assert response.json() == {"jd_text": "Senior Backend Engineer ...", "final_url": "https://jobs.example.com/1"}
    assert calls == ["https://jobs.example.com/1"]


@pytest.mark.parametrize("status", [400, 502])
def test_fetch_errors_keep_their_status_and_message(settings, stub_model, status):
    def fetch(url):
        raise JdFetchError(status, "That page could not be fetched.")

    with make_client(settings, stub_model, fetch) as browser:
        register(browser)
        response = browser.post("/api/jd/fetch", json={"url": "https://jobs.example.com/1"})
    assert response.status_code == status
    assert response.json()["detail"] == "That page could not be fetched."


def test_blank_url_is_422(signed_in):
    assert signed_in.post("/api/jd/fetch", json={"url": ""}).status_code == 422
