import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import require_admin


@pytest.fixture
def client():
    app = FastAPI(dependencies=[Depends(require_admin)])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/plans")
    def plans():
        return []

    return TestClient(app)


def test_open_when_no_key_configured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    assert client.get("/plans").status_code == 200


def test_missing_key_is_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    assert client.get("/plans").status_code == 401


def test_wrong_key_is_rejected(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r = client.get("/plans", headers={"X-Admin-Key": "nope"})
    assert r.status_code == 401


def test_right_key_is_accepted(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    r = client.get("/plans", headers={"X-Admin-Key": "secret"})
    assert r.status_code == 200


def test_health_stays_open(client, monkeypatch):
    monkeypatch.setenv("ADMIN_API_KEY", "secret")
    assert client.get("/health").status_code == 200