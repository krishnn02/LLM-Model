import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # LLM
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_base_url: str = ""  # Set to https://openrouter.ai/api/v1 for OpenRouter keys
    google_api_key: str = ""
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    
    # Playwright
    headless: bool = True
    browser_timeout: int = 30000
    user_data_dir: str = "./playwright_user_data"
    
    # Scraping
    max_retries: int = 2
    scrape_timeout: int = 45
    
    # Cache
    pincode_cache_ttl: int = 3600
    enable_cache: bool = True
    
    # Logging
    log_level: str = "INFO"
    
    # Demo Mode (simulates scraping when Playwright is unavailable)
    demo_mode: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
