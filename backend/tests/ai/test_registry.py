import pytest

from engcheck.ai.anthropic_provider import AnthropicProvider
from engcheck.ai.ollama import OllamaProvider
from engcheck.ai.openai_compat import OpenAICompatProvider
from engcheck.ai.registry import build, resolve, secret_name
from engcheck.core.models import AiProvider
from engcheck.core.secrets import SecretStore

from .fakes import FakeProvider


@pytest.fixture
def store(settings):
    return SecretStore(settings.data_dir, use_keyring=False)


def add(db, name, kind="openai_compatible", url="https://api.example.com/v1", default=False, enabled=True):
    row = AiProvider(name=name, kind=kind, base_url=url, model="m", is_default=default, enabled=enabled)
    db.add(row); db.flush()
    return row


def fake_factory(behaviour):
    """behaviour: {provayder nomi: AiError kodi yoki None}"""
    def factory(row, key):
        return FakeProvider(row.name, row.base_url, fail=behaviour.get(row.name))
    return factory


def test_build_maps_kind_to_class_and_passes_key(db, store):
    assert isinstance(build(add(db, "a", "anthropic", None), "k"), AnthropicProvider)
    assert isinstance(build(add(db, "b", "openai_compatible"), "k"), OpenAICompatProvider)
    assert isinstance(build(add(db, "c", "ollama", None), None), OllamaProvider)
    with pytest.raises(ValueError):
        build(add(db, "d", "telepathy"), None)
    assert secret_name(7) == "ai_provider:7"


def test_no_providers_means_rules_only(db, store, project):
    r = resolve(db, store, project)
    assert (r.provider, r.mode, r.reason) == (None, "none", "no_provider")


def test_cloud_blocked_by_default_then_local_is_used(db, store, project):
    add(db, "bulut", default=True); add(db, "lokal", "ollama", "http://127.0.0.1:11434")
    r = resolve(db, store, project, factory=fake_factory({}))
    assert (r.provider.name, r.mode) == ("lokal", "local")


def test_cloud_blocked_and_nothing_else(db, store, project):
    add(db, "bulut", default=True)
    r = resolve(db, store, project, factory=fake_factory({}))
    assert (r.mode, r.reason) == ("none", "cloud_not_allowed")


def test_cloud_used_when_project_allows(db, store, project):
    project.allow_cloud_ai = True
    add(db, "lokal", "ollama", "http://127.0.0.1:11434"); add(db, "bulut", default=True)
    r = resolve(db, store, project, factory=fake_factory({}))
    assert (r.provider.name, r.mode, r.reason) == ("bulut", "online", None)     # standart provayder birinchi


def test_offline_falls_back_to_local(db, store, project):
    project.allow_cloud_ai = True
    add(db, "bulut", default=True); add(db, "lokal", "ollama", "http://127.0.0.1:11434")
    r = resolve(db, store, project, factory=fake_factory({"bulut": "unreachable"}))
    assert (r.provider.name, r.mode) == ("lokal", "local")


def test_everything_down_reports_reason(db, store, project):
    project.allow_cloud_ai = True
    add(db, "bulut", default=True); add(db, "lokal", "ollama", "http://127.0.0.1:11434")
    r = resolve(db, store, project, factory=fake_factory({"bulut": "auth", "lokal": "unreachable"}))
    assert (r.provider, r.mode, r.reason) == (None, "none", "auth")            # standart provayderning sababi


def test_disabled_provider_is_ignored(db, store, project):
    add(db, "lokal", "ollama", "http://127.0.0.1:11434", enabled=False)
    assert resolve(db, store, project, factory=fake_factory({})).reason == "no_provider"


def test_key_is_read_from_secret_store(db, store, project):
    project.allow_cloud_ai = True
    row = add(db, "bulut", default=True)
    store.set(secret_name(row.id), "sk-123")
    seen = {}

    def factory(r, key):
        seen[r.name] = key
        return FakeProvider(r.name, r.base_url)
    resolve(db, store, project, factory=factory)
    assert seen == {"bulut": "sk-123"}
