import httpx
from datetime import datetime, timezone
from scrapers.base import BaseScraper
from models import Job, JobFilter
from pipeline.parsers import extract_tech_stack
from config import settings


class JSearchScraper(BaseScraper):
    """Aggregates Indeed + LinkedIn jobs via RapidAPI JSearch.
    Sign up free at rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
    """
    source_name = "jsearch"
    _BASE_URL = "https://jsearch.p.rapidapi.com/search"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, location: str, job_filter: JobFilter) -> list[Job]:
        params = {
            "query": f"{query} in {location}",
            "page": "1",
            "num_pages": "3",
            "remote_jobs_only": "true" if "remote" in location.lower() else "false",
            "employment_types": "FULLTIME",
            "date_posted": settings.jsearch_date_posted,
        }
        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(self._BASE_URL, params=params, headers=headers)
            resp.raise_for_status()

        records = resp.json().get("data", [])
        now = datetime.now(timezone.utc)
        jobs: list[Job] = []

        for r in records:
            # Drop listings whose expiration date has already passed
            expiry_raw = r.get("job_offer_expiration_datetime_utc")
            if expiry_raw:
                try:
                    expiry = datetime.fromisoformat(expiry_raw.replace("Z", "+00:00"))
                    if expiry < now:
                        continue
                except ValueError:
                    pass

            # Pick the best apply URL:
            # 1. A direct apply link from apply_options (goes straight to company ATS)
            # 2. Fall back to job_apply_link (aggregator redirect)
            apply_url = _best_apply_url(r)

            salary_min = r.get("job_min_salary")
            salary_max = r.get("job_max_salary")
            period = (r.get("job_salary_period") or "YEAR").upper()

            if period == "HOUR":
                salary_min = int(salary_min * 2080) if salary_min else None
                salary_max = int(salary_max * 2080) if salary_max else None
            else:
                salary_min = int(salary_min) if salary_min else None
                salary_max = int(salary_max) if salary_max else None

            salary_raw = None
            if salary_min and salary_max:
                salary_raw = f"${salary_min:,} - ${salary_max:,} a year"

            city = r.get("job_city") or ""
            state = r.get("job_state") or ""
            country = r.get("job_country") or ""
            location_str = ", ".join(filter(None, [city, state, country])) or "Remote"
            is_remote = bool(r.get("job_is_remote", False))
            publisher = (r.get("job_publisher") or "unknown").lower()

            jobs.append(Job(
                job_id=f"jsearch_{r['job_id']}",
                title=r.get("job_title", ""),
                company=r.get("employer_name", ""),
                location=location_str,
                is_remote=is_remote,
                salary_min=salary_min,
                salary_max=salary_max,
                salary_raw=salary_raw,
                job_type=(r.get("job_employment_type") or "").lower(),
                posted_at=r.get("job_posted_at_datetime_utc"),
                apply_url=apply_url,
                source=f"jsearch_{publisher}",
                description=r.get("job_description", ""),
                tech_stack=extract_tech_stack(
                    f"{r.get('job_title', '')} {r.get('job_description', '')}"
                ),
            ))

        return jobs


_BLOCKED_DOMAINS = {
    "google.com", "talk4fun.net", "web1337.net",
}


def _best_apply_url(record: dict) -> str:
    """Return the most reliable apply URL from a JSearch job record.

    Priority:
      1. Direct apply link from apply_options (company ATS — most reliable)
      2. Any non-blocked apply_options link
      3. job_apply_link if not a blocked domain
    """
    options: list[dict] = record.get("apply_options") or []

    for opt in options:
        url = opt.get("apply_link", "")
        if opt.get("is_direct") and url and not _is_blocked(url):
            return url

    for opt in options:
        url = opt.get("apply_link", "")
        if url and not _is_blocked(url):
            return url

    fallback = record.get("job_apply_link", "")
    return fallback if not _is_blocked(fallback) else ""


def _is_blocked(url: str) -> bool:
    return any(domain in url for domain in _BLOCKED_DOMAINS)
