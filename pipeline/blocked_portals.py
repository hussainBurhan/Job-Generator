"""Paid job boards and aggregator portals to exclude from results."""

from urllib.parse import urlparse

# Domains from sample output + common paid/scraper job-board networks.
BLOCKED_PORTAL_DOMAINS: frozenset[str] = frozenset({
    "toptal.com",
    "flexjobs.com",
    "talent.com",
    "bebee.com",
    "builtin.com",
    "builtinboston.com",
    "zycto.com",
    "trabajo.org",
    "jooble.org",
    "is-great.net",
    "is-best.net",
    "dailyremote.com",
    "clearancejobs.com",
    # Misc scraper / redirect domains already filtered in JSearch
    "google.com",
    "talk4fun.net",
    "web1337.net",
})


def portal_host(url: str) -> str:
    if not url:
        return ""
    if "://" not in url:
        url = f"https://{url}"
    return (urlparse(url).netloc or "").lower().removeprefix("www.")


def is_blocked_portal_url(url: str, extra_domains: frozenset[str] | None = None) -> bool:
    host = portal_host(url)
    if not host:
        return False
    domains = BLOCKED_PORTAL_DOMAINS
    if extra_domains:
        domains = domains | extra_domains
    return any(host == d or host.endswith(f".{d}") for d in domains)
