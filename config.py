from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # JSearch API via RapidAPI — rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    rapidapi_key: Optional[str] = None

    # SerpAPI key — serpapi.com (100 free searches/month)
    serp_api_key: Optional[str] = None

    # Space-separated OR keywords. A job matches if its title/description
    # contains ANY of the listed words.
    # e.g. "java springboot kotlin developer" matches jobs mentioning java OR
    # springboot OR kotlin OR developer.
    default_keywords: str = "java springboot kotlin developer"

    default_location: str = "remote"
    default_country: str = "us"
    default_salary_min: int = 100000
    # Options: today, 3days, week, month
    jsearch_date_posted: str = "3days"
    # Comma-separated source names to skip URL verification for.
    # Use "jsearch" to skip all jsearch results, or exact names like "activejobsdb,linkedin"
    verify_skip_sources: str = "jsearch"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def api_key(self) -> Optional[str]:
        if not self.rapidapi_key or self.rapidapi_key == "your_key_here":
            return None
        return self.rapidapi_key

    @property
    def jsearch_key(self) -> Optional[str]:
        return self.api_key

    @property
    def serpapi_key(self) -> Optional[str]:
        if not self.serp_api_key or self.serp_api_key == "your_key_here":
            return None
        return self.serp_api_key

    @property
    def keywords_list(self) -> list[str]:
        return [k.strip() for k in self.default_keywords.split(",")]

    @property
    def skip_sources_set(self) -> set[str]:
        return {s.strip() for s in self.verify_skip_sources.split(",") if s.strip()}


settings = Settings()
