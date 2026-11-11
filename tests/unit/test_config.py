from katiu.core.config import Settings


def test_config_por_defecto_es_desarrollo_en_madrid() -> None:
    settings = Settings(_env_file=None)  # pyright: ignore[reportCallIssue]
    assert settings.is_dev
    assert settings.timezone == "Europe/Madrid"
