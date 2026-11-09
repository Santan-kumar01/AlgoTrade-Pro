
from pydantic import SecretStr

from src.core.config import Settings, settings


def test_default_app_settings():
    """Verify application settings loaded from the environment."""
    assert settings.app_name == "AlgoTrade Pro"
    assert settings.app_env == "development"


def test_database_url_is_configured():
    """Verify that the database URL is available."""
    assert settings.database_url
    assert settings.database_url.startswith("postgresql+asyncpg://")


def test_secret_key_is_protected():
    """Verify that the secret key uses Pydantic SecretStr."""
    assert isinstance(settings.secret_key, SecretStr)
    assert settings.secret_key.get_secret_value()


def test_settings_can_be_created_independently():
    """Verify settings can be created without reading the .env file."""
    test_settings = Settings(
        _env_file=None,
        app_name="Test AlgoTrade",
        app_env="testing",
        database_url="postgresql+asyncpg://test:test@localhost/test_db",
        secret_key="test-secret-key",
    )

    assert test_settings.app_name == "Test AlgoTrade"
    assert test_settings.app_env == "testing"
    assert test_settings.secret_key.get_secret_value() == "test-secret-key"
