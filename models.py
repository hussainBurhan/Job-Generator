from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timezone


class Job(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    is_remote: bool
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_raw: Optional[str] = None
    job_type: Optional[str] = None
    posted_at: Optional[str] = None
    apply_url: str
    source: str
    description: Optional[str] = None
    tech_stack: list[str] = []
    scraped_at: str = ""

    def model_post_init(self, __context):
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()


class JobFilter(BaseModel):
    keywords: list[str] = []
    locations: list[str] = ["remote"]
    salary_min: Optional[int] = None
    job_types: list[str] = []
    require_salary: bool = False
