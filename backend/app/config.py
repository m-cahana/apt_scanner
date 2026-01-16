from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database - defaults to SQLite for local dev
    database_url: str = "sqlite:///./apt_scanner.db"

    # Supabase-specific (optional, for direct API access)
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_key: Optional[str] = None

    # Scraper settings
    scrape_interval_minutes: int = 30
    max_pages_per_scrape: int = 10
    scrape_sources: str = "craigslist"  # comma-separated list

    # Email settings (optional)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = ""

    # Monitoring (optional)
    slack_webhook_url: Optional[str] = None  # For error notifications

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
