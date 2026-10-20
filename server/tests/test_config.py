import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_default_secret():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="supersecretkey", _env_file=None)


def test_production_rejects_wildcard_cors():
    with pytest.raises(ValidationError):
        Settings(ENVIRONMENT="production", SECRET_KEY="x" * 40, CORS_ORIGINS=["*"], _env_file=None)


def test_production_disables_test_credits():
    s = Settings(ENVIRONMENT="production", SECRET_KEY="x" * 40, _env_file=None)
    assert s.test_credits_enabled is False


def test_dev_allows_default_secret():
    assert Settings(ENVIRONMENT="dev", _env_file=None).is_dev
