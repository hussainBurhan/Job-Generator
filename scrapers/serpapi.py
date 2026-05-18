import httpx
import re
from scrapers.base import BaseScraper
from models import Job, JobFilter
from pipeline.parsers import extract_tech_stack
from config import settings
from pipeline.blocked_portals import is_blocked_portal_url


class SerpAPIGoogleJobsScraper(BaseScraper):
    """Google Jobs via SerpAPI.
    Sign up at serpapi.com — the free tier gives 100 searches/month.
    """
    source_name = "google_jobs"
    _BASE_URL = "https://serpapi.com/search.json"

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def search(self, query: str, location: str, job_filter: JobFilter) -> list[Job]:
        is_remote = "remote" in location.lower()
        search_query = f"{query} remote" if is_remote else f"{query} {location}"

        # Google Jobs only accepts: today, week, month — map JSearch's "3days" to "week"
        _DATE_MAP = {"today": "today", "3days": "week", "week": "week", "month": "month"}
        date_chip = _DATE_MAP.get(settings.jsearch_date_posted, "week")

        params = {
            "engine": "google_jobs",
            "q": search_query,
            "api_key": self.api_key,
            "hl": "en",
            "chips": f"date_posted:{date_chip}",
        }
        if not is_remote:
            params["location"] = location

        jobs: list[Job] = []

        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(3):
                if page > 0:
                    params["start"] = page * 10

                resp = await client.get(self._BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()

                records = data.get("jobs_results", [])
                if not records:
                    break

                for r in records:
                    jobs.append(_parse_job(r))

        return jobs


def _parse_job(r: dict) -> Job:
    extensions: list[str] = r.get("extensions") or []
    detected: dict = r.get("detected_extensions") or {}

    is_remote = (
        detected.get("work_from_home", False)
        or any("remote" in e.lower() for e in extensions)
    )

    job_type = None
    for ext in extensions:
        lower = ext.lower()
        if "full-time" in lower or "fulltime" in lower:
            job_type = "fulltime"
            break
        if "part-time" in lower or "parttime" in lower:
            job_type = "parttime"
            break
        if "contract" in lower:
            job_type = "contract"
            break

    salary_raw, salary_min, salary_max = _parse_salary(extensions, detected)

    apply_url = _best_apply_url(r)

    description = r.get("description") or ""
    for highlight in r.get("job_highlights") or []:
        items = highlight.get("items") or []
        description += " " + " ".join(items)

    job_id = r.get("job_id") or f"serpapi_{r.get('title', '')}_{r.get('company_name', '')}"

    return Job(
        job_id=f"serpapi_{job_id}",
        title=r.get("title", ""),
        company=r.get("company_name", ""),
        location=r.get("location") or ("Remote" if is_remote else ""),
        is_remote=is_remote,
        salary_min=salary_min,
        salary_max=salary_max,
        salary_raw=salary_raw,
        job_type=job_type,
        posted_at=detected.get("posted_at"),
        apply_url=apply_url,
        source="google_jobs",
        description=description.strip(),
        tech_stack=extract_tech_stack(f"{r.get('title', '')} {description}"),
    )


def _parse_salary(
    extensions: list[str], detected: dict
) -> tuple[str | None, int | None, int | None]:
    # SerpAPI sometimes surfaces salary in detected_extensions
    raw = detected.get("salary")
    if not raw:
        for ext in extensions:
            if "$" in ext or "salary" in ext.lower() or "/yr" in ext.lower():
                raw = ext
                break
    if not raw:
        return None, None, None

    # Strip non-numeric noise and extract numbers
    numbers = [int(n.replace(",", "")) for n in re.findall(r"\d[\d,]+", raw)]
    if not numbers:
        return raw, None, None

    # Normalise hourly → annual
    is_hourly = "/hr" in raw.lower() or "hour" in raw.lower()
    if is_hourly:
        numbers = [n * 2080 for n in numbers]

    if len(numbers) == 1:
        return raw, numbers[0], None
    return raw, numbers[0], numbers[1]


def _is_blocked(url: str) -> bool:
    extra = settings.blocked_portal_domains_set
    return is_blocked_portal_url(url, extra_domains=extra or None)


def _best_apply_url(r: dict) -> str:
    for opt in r.get("apply_options") or []:
        link = opt.get("link", "")
        if link and not _is_blocked(link):
            return link
    for rel in r.get("related_links") or []:
        link = rel.get("link", "")
        if link and not _is_blocked(link):
            return link
    return ""
