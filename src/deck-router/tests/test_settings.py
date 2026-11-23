"""Settings tests with isolated process-environment overrides."""

from pathlib import Path

import pytest
from deck_router.utils.settings import AzureSettings, DecisionSettings, Settings
from pydantic import HttpUrl, ValidationError


def test_given_service_environment_when_loaded_then_uses_prefixed_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECK_ROUTER_HOST", "127.0.0.1")
    monkeypatch.setenv("DECK_ROUTER_PORT", "9010")
    monkeypatch.setenv("DECK_ROUTER_PUBLIC_URL", "http://localhost:9010")
    monkeypatch.setenv("OTHER_AGENT_PORT", "9999")

    settings = Settings()

    assert settings.host == "127.0.0.1"
    assert settings.port == 9010
    assert str(settings.public_url) == "http://localhost:9010/"


def test_given_empty_endpoint_placeholders_when_loaded_then_starts_without_external_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DECK_ROUTER_CREATOR_URL", "")
    monkeypatch.setenv("DECK_ROUTER_EDITOR_URL", "")
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "")
    monkeypatch.setenv("AZURE_DECISION_ENDPOINT", "")

    assert Settings().creator_url is None
    assert Settings().editor_url is None
    assert AzureSettings().endpoint is None
    assert DecisionSettings().endpoint is None


def test_given_common_dotenv_when_utils_load_then_process_and_explicit_values_take_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in (
        "AZURE_DECISION_ENDPOINT",
        "DECISION_ENDPOINT",
        "DECISION_API_KEY",
        "DECISION_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "AZURE_DECISION_ENDPOINT=https://decision.test/providers/microsoft\n"
        "DECISION_API_KEY=synthetic-key\n"
        "DECISION_MODEL=dotenv-decision\n"
        "AZURE_OPENAI_DEPLOYMENT=dotenv-llm\n"
        "DECK_ROUTER_PORT=8000\n"
        "UNRELATED_SERVICE_SETTING=ignored\n",
        encoding="utf-8",
    )

    from_file = DecisionSettings()
    monkeypatch.setenv("DECISION_MODEL", "environment-decision")
    from_environment = DecisionSettings()
    explicit = DecisionSettings(model="explicit-decision")

    assert from_file.model == "dotenv-decision"
    assert from_file.api_key is not None
    assert from_file.api_key.get_secret_value() == "synthetic-key"
    assert from_environment.model == "environment-decision"
    assert explicit.model == "explicit-decision"
    assert "synthetic-key" not in repr(from_file)


def test_given_separate_azure_endpoints_when_loaded_then_each_provider_uses_its_own_endpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    for key in ("AZURE_DECISION_ENDPOINT", "AZURE_OPENAI_ENDPOINT", "DECISION_ENDPOINT"):
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text(
        "AZURE_DECISION_ENDPOINT=https://decision.test/providers/microsoft\n"
        "AZURE_OPENAI_ENDPOINT=https://llm.test/\n"
        "DECISION_ENDPOINT=https://old-decision.test/\n",
        encoding="utf-8",
    )

    decision = DecisionSettings()
    llm = AzureSettings()
    explicit = DecisionSettings(endpoint=HttpUrl("https://explicit.test/"))

    assert str(decision.endpoint) == "https://decision.test/providers/microsoft"
    assert str(llm.endpoint) == "https://llm.test/"
    assert str(explicit.endpoint) == "https://explicit.test/"


@pytest.mark.parametrize("timeout", [0, 601])
def test_given_invalid_model_timeout_when_configured_then_fails_before_network(
    timeout: int,
) -> None:
    with pytest.raises(ValidationError, match="timeout"):
        DecisionSettings(timeout=timeout, _env_file=None)


@pytest.mark.parametrize(
    ("variable", "value", "field"),
    [
        ("DECK_ROUTER_PORT", "0", "port"),
        ("DECK_ROUTER_PORT", "65536", "port"),
        ("DECK_ROUTER_PORT", "invalid", "port"),
        ("DECK_ROUTER_HOST", "", "host"),
        ("DECK_ROUTER_PUBLIC_URL", "ftp://localhost:8000", "public_url"),
        ("DECK_ROUTER_PUBLIC_URL", "not-a-url", "public_url"),
        ("DECK_ROUTER_PUBLIC_URL", "http://localhost:8000/not-mounted", "public_url"),
        ("DECK_ROUTER_PUBLIC_URL", "http://localhost:8000/?query=1", "public_url"),
        ("DECK_ROUTER_SELECTOR", "unknown", "selector"),
    ],
)
def test_given_invalid_environment_when_loaded_then_fails_explicitly(
    monkeypatch: pytest.MonkeyPatch, variable: str, value: str, field: str
) -> None:
    monkeypatch.setenv("DECK_ROUTER_HOST", "127.0.0.1")
    monkeypatch.setenv("DECK_ROUTER_PORT", "8000")
    monkeypatch.setenv("DECK_ROUTER_PUBLIC_URL", "http://localhost:8000")
    monkeypatch.setenv(variable, value)

    with pytest.raises(ValidationError, match=field):
        Settings()
