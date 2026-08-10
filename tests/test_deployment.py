import pytest

from services.deployment import DeploymentConfigurationError, validate_production_environment


VALID = {
    "SECRET_KEY": "a-secure-random-secret-key-value-12345",
    "ADMIN_PASSWORD": "a-long-admin-password",
    "DATABASE_URL": "sqlite:////srv/system-knowledge-designer/catalogue.db",
    "DATA_DIR": "/srv/system-knowledge-designer/data",
}


def test_production_environment_accepts_explicit_secure_values():
    validate_production_environment(VALID)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"SECRET_KEY": "short"}, "SECRET_KEY"),
        ({"ADMIN_PASSWORD": "change-me"}, "ADMIN_PASSWORD"),
        ({"DATABASE_URL": ""}, "DATABASE_URL"),
        ({"DATA_DIR": "relative/data"}, "DATA_DIR"),
    ],
)
def test_production_environment_rejects_unsafe_or_implicit_values(override, message):
    environment = {**VALID, **override}
    with pytest.raises(DeploymentConfigurationError, match=message):
        validate_production_environment(environment)


def test_production_error_reports_all_missing_requirements_without_values():
    with pytest.raises(DeploymentConfigurationError) as captured:
        validate_production_environment({})
    message = str(captured.value)
    assert all(name in message for name in ("SECRET_KEY", "ADMIN_PASSWORD", "DATABASE_URL", "DATA_DIR"))
    assert "a-secure-random" not in message
