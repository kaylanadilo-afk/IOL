import os

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Carga el .env también en os.environ: algunos módulos (horario de mercado, precios reales)
# leen las variables con os.getenv para poder cambiarlas en los tests.
load_dotenv()


class Settings(BaseSettings):
    DATABASE_URL: str
    PORT: int = 8000
    JWT_SECRET: str
    # Clave para firmar los tokens de sesión del broker. Si falta, se genera una al arrancar.
    SECRET_KEY: str | None = None
    # Orígenes permitidos para el front (separados por coma)
    CORS_ORIGINS: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

if settings.SECRET_KEY and not os.getenv("SECRET_KEY"):
    os.environ["SECRET_KEY"] = settings.SECRET_KEY
