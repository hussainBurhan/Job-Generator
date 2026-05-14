import asyncio
import httpx
from models import Job

DEAD_PHRASES = [
    "no longer available",
    "job not found",
    "position has been filled",
    "this job has expired",
    "job listing removed",
    "no longer accepting",
    "job closed",
    "posting has been removed",
    "this position is no longer",
    "job is no longer",
    "page not found",
    "404 not found",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Sites that block bots with 403/503 but the URLs are real — don't discard them
BOT_BLOCKED_HOSTS = {"learn4good.com", "glassdoor.com", "ziprecruiter.com"}


async def verify_jobs(
    jobs: list[Job],
    concurrency: int = 10,
    skip_sources: set[str] | None = None,
) -> list[Job]:
    """Return only jobs whose apply_url is confirmed live or unverifiable (bot-blocked).

    Jobs whose source is in skip_sources bypass HTTP verification entirely.
    e.g. skip_sources={"jsearch_indeed", "jsearch_linkedin"} or {"jsearch"} to
    skip all jsearch-prefixed sources.
    """
    sem = asyncio.Semaphore(concurrency)

    async def check_or_skip(job: Job) -> bool:
        if skip_sources and _source_matches(job.source, skip_sources):
            return True
        return await _check(job, sem)

    results = await asyncio.gather(*[check_or_skip(job) for job in jobs])
    return [job for job, alive in zip(jobs, results) if alive]


def _source_matches(source: str, skip_sources: set[str]) -> bool:
    """Match exact source name or prefix. e.g. 'jsearch' matches 'jsearch_indeed'."""
    return source in skip_sources or any(source.startswith(s) for s in skip_sources)


async def _check(job: Job, sem: asyncio.Semaphore) -> bool:
    if not job.apply_url:
        return False

    async with sem:
        try:
            async with httpx.AsyncClient(
                timeout=10,
                follow_redirects=True,
                headers=HEADERS,
            ) as client:
                resp = await client.get(job.apply_url)

            final_url = str(resp.url)

            # LinkedIn redirects dead jobs to /authwall or /login
            if "linkedin.com" in final_url:
                if "/authwall" in final_url or "/login" in final_url:
                    return False
                return resp.status_code == 200

            # Hard 404
            if resp.status_code == 404:
                return False

            # Bot-blocked hosts — assume alive, we can't verify
            host = final_url.split("/")[2] if "//" in final_url else ""
            if any(blocked in host for blocked in BOT_BLOCKED_HOSTS):
                return True

            # 403 from other hosts — bot blocking, assume alive
            if resp.status_code == 403:
                return True

            # Scan body for dead-job phrases
            body = resp.text.lower()
            if any(phrase in body for phrase in DEAD_PHRASES):
                return False

            return resp.status_code == 200

        except (httpx.TimeoutException, httpx.ConnectError):
            # Network issue — keep the job, don't discard on flaky connection
            return True
        except Exception:
            return True
