from config import settings
from models import Job, JobFilter
from pipeline.blocked_portals import is_blocked_portal_url


def drop_blocked_portals(jobs: list[Job]) -> tuple[list[Job], int]:
    extra = settings.blocked_portal_domains_set
    kept: list[Job] = []
    dropped = 0
    for job in jobs:
        if is_blocked_portal_url(job.apply_url, extra_domains=extra or None):
            dropped += 1
        else:
            kept.append(job)
    return kept, dropped


def apply_filters(jobs: list[Job], f: JobFilter) -> list[Job]:
    return [job for job in jobs if _passes(job, f)]


def _passes(job: Job, f: JobFilter) -> bool:
    extra = settings.blocked_portal_domains_set
    if is_blocked_portal_url(job.apply_url, extra_domains=extra or None):
        return False

    # Remote filter
    if "remote" in [loc.lower() for loc in f.locations] and not job.is_remote:
        return False

    # Salary filter
    if f.salary_min is not None:
        if job.salary_min is None and job.salary_max is None:
            if f.require_salary:
                return False
            # No salary listed — let it through unless require_salary is set
        elif job.salary_max is not None and job.salary_max < f.salary_min:
            # Both min and max are below the threshold — exclude
            return False

    # Keyword filter — at least one keyword must match.
    # Multi-word keywords use AND logic: "java developer" → must contain
    # both "java" AND "developer" anywhere in title or description.
    if f.keywords:
        title_lower = job.title.lower()
        desc_lower = (job.description or "").lower()
        searchable = f"{title_lower} {desc_lower}"
        if not any(
            any(token in searchable for token in kw.lower().split())
            for kw in f.keywords
        ):
            return False

    # Job type filter
    if f.job_types and job.job_type:
        if job.job_type.lower() not in [jt.lower() for jt in f.job_types]:
            return False

    return True
