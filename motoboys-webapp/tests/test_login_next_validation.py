import importlib
from types import SimpleNamespace

import pytest


class DummyRequest:
    def __init__(self, session=None, ip="127.0.0.1"):
        self.session = session or {}
        self.client = SimpleNamespace(host=ip)
        self.headers = {}
        self.url = SimpleNamespace(path="/ui/login", query="")


@pytest.fixture
def router_module(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("DB_MODE", "desktop")
    monkeypatch.setenv("APP_MODE", "desktop")
    monkeypatch.setenv("APP_ENV", "dev")

    module = importlib.import_module("app.web.router")
    module = importlib.reload(module)
    monkeypatch.setattr(module.auth_provider, "needs_initial_setup", lambda: False)
    return module


@pytest.fixture
def template_capture(router_module, monkeypatch):
    captured = {}

    def _fake_template_response(name, context, **kwargs):
        captured["name"] = name
        captured["context"] = context
        captured["kwargs"] = kwargs
        return SimpleNamespace(template=name, context=context, kwargs=kwargs)

    monkeypatch.setattr(router_module.templates, "TemplateResponse", _fake_template_response)
    return captured


@pytest.mark.parametrize(
    "value,expected",
    [
        ("/ui/imports/new", "/ui/imports/new"),
        ("/ui/weeks/current?tab=1", "/ui/weeks/current?tab=1"),
        ("https://evil.example/a", None),
        ("http://evil.example/a", None),
        ("//evil.example/a", None),
        ("javascript:alert(1)", None),
        ("/admin", None),
    ],
)
def test_safe_internal_next(router_module, value, expected):
    assert router_module._safe_internal_next(value) == expected


def test_login_page_passes_only_safe_next_to_template(router_module, template_capture):
    request = DummyRequest()

    router_module.login_page(request=request, next="/ui/weeks/current")
    assert template_capture["context"]["next"] == "/ui/weeks/current"

    router_module.login_page(request=request, next="https://evil.example/")
    assert template_capture["context"]["next"] == "/ui/imports/new"


@pytest.mark.parametrize(
    "role,bad_next,expected_location",
    [
        ("ADMIN", "https://evil.example/", "/ui/imports/new"),
        ("ADMIN", "//evil.example/path", "/ui/imports/new"),
        ("CASHIER", "https://evil.example/", "/ui/weeks/current"),
        ("CASHIER", "//evil.example/path", "/ui/weeks/current"),
    ],
)
def test_login_post_forces_profile_default_on_invalid_next(router_module, role, bad_next, expected_location):
    monkey_verify = lambda username, password: role if username == "ok" and password == "ok" else None
    router_module.auth_provider.verify_credentials = monkey_verify
    request = DummyRequest()

    response = router_module.login_post(request=request, username="ok", password="ok", next=bad_next)

    assert response.status_code == 303
    assert response.headers["location"] == expected_location


def test_login_post_redirects_to_valid_internal_next(router_module):
    router_module.auth_provider.verify_credentials = lambda username, password: "ADMIN"
    request = DummyRequest()

    response = router_module.login_post(
        request=request,
        username="ok",
        password="ok",
        next="/ui/imports/new?from=login",
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/ui/imports/new?from=login"
