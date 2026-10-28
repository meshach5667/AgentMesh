import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_secret():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            PUBLIC_BASE_URL="https://api.example.com",
            SECRET_KEY="supersecretkey",
            _env_file=None,
        )


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(
            ENVIRONMENT="production",
            PUBLIC_BASE_URL="https://api.example.com",
            SECRET_KEY="x" * 40,
            CORS_ORIGINS=["*"],
            _env_file=None,
        )


PROD = {
    "ENVIRONMENT": "production",
    "PUBLIC_BASE_URL": "https://api.example.com",
    "SECRET_KEY": "x" * 40,
    "MONGODB_URL": "mongodb+srv://u:p@cluster0.example.mongodb.net/",
    "_env_file": None,
}


def test_no_payment_settings_are_needed():
    """The service starts with no payment gateway configuration at all."""
    configured = Settings(**PROD)
    assert not any(name.startswith(("PAYSTACK", "PAYOUT", "TOPUP")) for name in type(configured).model_fields)
    assert configured.DEFAULT_CURRENCY == "NGN"


def test_failover_timing_is_validated():
    with pytest.raises(ValidationError, match="HEARTBEAT_DEGRADED_SECONDS"):
        Settings(HEARTBEAT_DEGRADED_SECONDS=200, HEARTBEAT_TIMEOUT_SECONDS=90, _env_file=None)
    with pytest.raises(ValidationError, match="PLACEMENT_RETRY_BASE_SECONDS"):
        Settings(PLACEMENT_RETRY_BASE_SECONDS=600, PLACEMENT_RETRY_MAX_SECONDS=300, _env_file=None)


def test_production_requires_a_mongodb_url():
    with pytest.raises(ValidationError, match="MONGODB_URL"):
        Settings(**(PROD | {"MONGODB_URL": "mongodb://127.0.0.1:27017/?replicaSet=rs0"}))


def test_dev_allows_default_secret():
    assert Settings(ENVIRONMENT="dev", _env_file=None).is_dev


def test_heartbeat_timeout_must_cover_several_intervals():
    with pytest.raises(ValidationError, match="HEARTBEAT_TIMEOUT_SECONDS"):
        Settings(HEARTBEAT_TIMEOUT_SECONDS=15, WORKER_HEARTBEAT_INTERVAL_SECONDS=15, _env_file=None)
    Settings(
        HEARTBEAT_TIMEOUT_SECONDS=15, HEARTBEAT_DEGRADED_SECONDS=8, WORKER_HEARTBEAT_INTERVAL_SECONDS=3, _env_file=None
    )


def test_unset_environment_fails_closed(monkeypatch):
    """A deployment that forgets ENVIRONMENT must not run with the public default SECRET_KEY (forgeable tokens)."""
    for name in ("ENVIRONMENT", "SECRET_KEY", "MONGODB_URL", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        Settings(_env_file=None)
    configured = Settings(**{k: v for k, v in PROD.items() if k != "ENVIRONMENT"})
    assert configured.is_dev is False
