"""Configuración de la app.

`Settings` lee variables de entorno (y el archivo `.env` en local). Así los secretos
y lo que cambia entre entornos (local, producción) nunca se escriben en el código.
"""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="KATIU_", extra="ignore")

    app_name: str = "Katiu Yoga"
    environment: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///data/katiu.db"
    timezone: str = "Europe/Madrid"
    # Firma la cookie de sesión. En producción DEBE venir del entorno (ver .env.example).
    secret_key: str = "dev-inseguro-no-usar-en-produccion"
    session_days: int = 30
    login_max_attempts: int = 5
    login_window_minutes: int = 15

    @property
    def is_dev(self) -> bool:
        return self.environment == "development"

    @property
    def is_prod(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Una sola instancia por proceso. Los tests pueden sustituirla con dependency overrides."""
    return Settings()
