from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    storage_mode: str = "local"
    admin_api_key: str = ""
    github_token: str = ""
    github_owner: str = "cfroquemes5"
    github_repo: str = "distritto-catalogo-assets"
    github_branch: str = "main"
    allowed_origins: str = "http://localhost:8000,http://127.0.0.1:8000"
    analytics_cache_seconds: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def site_root(self) -> Path:
        return self.project_root / "site"

    @property
    def data_root(self) -> Path:
        p = self.project_root / "backend" / "data"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def database_path(self) -> Path:
        return self.data_root / "distritto.db"

    @property
    def origins(self) -> list[str]:
        return [x.strip() for x in self.allowed_origins.split(",") if x.strip()]
