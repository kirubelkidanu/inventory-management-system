from functools import lru_cache
from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Inventory Management System"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/inventory_db"
    SUPABASE_URL: str = "https://kllunchfkzwhpiwhklzz.supabase.co"
    SUPABASE_KEY: str = "sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q"
    SUPABASE_ANON_KEY: str = "sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q"
    SUPABASE_SERVICE_ROLE_KEY: str = "service-role-key"
    SUPABASE_JWT_SECRET: Optional[str] = None
    JWT_SECRET: str = "development-secret-key-change-me"
    JWT_ALGORITHM: str = "HS256"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000,https://inventory.moderngebeya.com,http://inventory.moderngebeya.com"
    BACKEND_CORS_ORIGINS: Optional[str] = None
    ALLOWED_ORIGINS: Optional[str] = None
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @model_validator(mode="after")
    def sanitize_supabase_settings(self) -> "Settings":
        """
        Sanitizes Supabase configuration in production environments (e.g. Render)
        where stale or placeholder environment variables may override defaults.
        """
        # 1. Sanitize SUPABASE_URL
        url = str(self.SUPABASE_URL or "").strip()
        if not url or "your-project" in url or "example" in url:
            self.SUPABASE_URL = "https://kllunchfkzwhpiwhklzz.supabase.co"

        # 2. Sanitize SUPABASE_ANON_KEY
        anon = str(self.SUPABASE_ANON_KEY or "").strip()
        if not anon or "placeholder" in anon or "your-" in anon:
            self.SUPABASE_ANON_KEY = "sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q"

        # 3. Sanitize SUPABASE_KEY
        key = str(self.SUPABASE_KEY or "").strip()
        if not key or "placeholder" in key or "your-" in key or key == "public-anon-key":
            self.SUPABASE_KEY = self.SUPABASE_ANON_KEY or "sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q"

        return self

    @property
    def effective_supabase_url(self) -> str:
        url = str(self.SUPABASE_URL or "").strip()
        if not url or "your-project" in url or "example" in url:
            return "https://kllunchfkzwhpiwhklzz.supabase.co"
        return url

    @property
    def effective_supabase_anon_key(self) -> str:
        anon = str(self.SUPABASE_ANON_KEY or self.SUPABASE_KEY or "").strip()
        if not anon or "placeholder" in anon or "your-" in anon:
            return "sb_publishable_08sHZvm3HnDFO8hwh5mRog_Rbk_Z33Q"
        return anon

    @property
    def async_database_url(self) -> str:
        return self.DATABASE_URL.replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://", 1
        ) if "postgresql+psycopg2://" in self.DATABASE_URL else self.DATABASE_URL

    @property
    def cors_origins_list(self) -> list[str]:
        core_origins = [
            "https://inventory.moderngebeya.com",
            "http://inventory.moderngebeya.com",
            "http://localhost:5173",
            "http://localhost:3000",
        ]
        origins_set = {o.rstrip("/") for o in core_origins}

        for raw_source in [self.CORS_ORIGINS, self.BACKEND_CORS_ORIGINS, self.ALLOWED_ORIGINS]:
            if not raw_source:
                continue
            raw = str(raw_source).strip()
            if raw.startswith("[") and raw.endswith("]"):
                import json
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        for o in parsed:
                            if o and str(o).strip():
                                origins_set.add(str(o).strip().rstrip("/"))
                        continue
                except json.JSONDecodeError:
                    pass
            for origin in raw.split(","):
                cleaned = origin.strip().strip("'").strip('"').rstrip("/")
                if cleaned:
                    origins_set.add(cleaned)

        return sorted(list(origins_set))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
