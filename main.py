import asyncio
import sys

from rich.console import Console
from rich.table import Table

from config import settings
from models import JobFilter
from pipeline.filters import apply_filters, drop_blocked_portals
from pipeline.verifier import verify_jobs
from scrapers.jsearch import JSearchScraper
from scrapers.serpapi import SerpAPIGoogleJobsScraper
from storage.database import init_db, save_jobs
from storage.excel import export_to_excel

console = Console()


async def run_pipeline(query: str, job_filter: JobFilter) -> None:
    console.print(f"\n[bold cyan]Query:[/] {query}")
    console.print(
        f"[bold cyan]Filters:[/] "
        f"salary_min=${job_filter.salary_min:,}  |  "
        f"remote={('remote' in [l.lower() for l in job_filter.locations])}  |  "
        f"keywords={job_filter.keywords}\n"
    )

    scrapers = []

    jsearch_key = settings.api_key
    if not jsearch_key:
        console.print("[yellow]RAPIDAPI_KEY not set — JSearch scraper skipped.[/]")
    else:
        scrapers.append(JSearchScraper(api_key=jsearch_key))

    serpapi_key = settings.serpapi_key
    if not serpapi_key:
        console.print("[yellow]SERP_API_KEY not set — Google Jobs scraper skipped.[/]")
    else:
        scrapers.append(SerpAPIGoogleJobsScraper(api_key=serpapi_key))

    if not scrapers:
        console.print("[red]No scrapers available — set at least one API key.[/]\n")
        return

    all_jobs = []
    for scraper in scrapers:
        console.print(f"[dim]Scraping {scraper.source_name}...[/]")
        try:
            jobs = await scraper.search(query, settings.default_location, job_filter)
            console.print(f"  [green]✓[/] {len(jobs)} raw results")
            all_jobs.extend(jobs)
        except Exception as exc:
            msg = str(exc).split("\n")[0][:100]
            console.print(f"  [red]✗ {scraper.source_name} failed:[/] {msg}")
            if "429" in msg:
                console.print(f"    [dim yellow]Rate limited — will succeed on next run when quota resets[/]")

    all_jobs, portal_dropped = drop_blocked_portals(all_jobs)
    if portal_dropped:
        console.print(
            f"[dim]Dropped {portal_dropped} listings on paid/aggregator job portals[/]\n"
        )

    skip = settings.skip_sources_set
    skip_note = f"  [dim](skipping verification for: {', '.join(sorted(skip))})[/]" if skip else ""
    console.print(f"[dim]Verifying {len(all_jobs)} URLs (dropping dead listings)...{skip_note}[/]")
    live_jobs = await verify_jobs(all_jobs, skip_sources=skip or None)
    console.print(f"  [green]✓[/] {len(live_jobs)} confirmed live  |  [red]{len(all_jobs) - len(live_jobs)} dead removed[/]\n")

    filtered = apply_filters(live_jobs, job_filter)
    console.print(
        f"[bold]Pipeline complete:[/] "
        f"{len(all_jobs)} raw → {len(live_jobs)} live → [green]{len(filtered)} matched[/] your filters\n"
    )

    new_count = save_jobs(filtered)
    if new_count:
        console.print(f"[dim]{new_count} new jobs saved to jobs.db[/]\n")
    else:
        console.print("[dim]No new jobs (all already in DB)[/]\n")

    if filtered:
        excel_path = export_to_excel(filtered)
        console.print(f"[dim]Excel export → {excel_path}[/]\n")

    _print_table(filtered[:25])


def _print_table(jobs) -> None:
    if not jobs:
        console.print("[yellow]No matching jobs to display.[/]")
        return

    table = Table(show_header=True, header_style="bold magenta", show_lines=True)
    table.add_column("#", width=3)
    table.add_column("Title", max_width=38)
    table.add_column("Company", max_width=22)
    table.add_column("Salary", max_width=22)
    table.add_column("Tech Stack", max_width=30)
    table.add_column("Apply URL", max_width=40)

    for i, job in enumerate(jobs, 1):
        salary = job.salary_raw or "[dim]Not listed[/]"
        tech = ", ".join(job.tech_stack[:6]) or "—"
        table.add_row(str(i), job.title, job.company, salary, tech, job.apply_url)

    console.print(table)


if __name__ == "__main__":
    init_db()

    # Allow quick CLI override: python main.py "senior java developer" 120000
    salary_arg = int(sys.argv[2]) if len(sys.argv) > 2 else settings.default_salary_min

    # API search query: use only the first token of the first keyword so the
    # scrapers return broad results. Local keyword filtering narrows them down.
    primary_query = sys.argv[1] if len(sys.argv) > 1 else settings.keywords_list[0].split()[0]

    job_filter = JobFilter(
        keywords=settings.keywords_list,
        locations=[settings.default_location],
        salary_min=salary_arg,
    )

    asyncio.run(run_pipeline(query=primary_query, job_filter=job_filter))
