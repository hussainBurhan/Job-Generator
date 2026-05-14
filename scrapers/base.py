from abc import ABC, abstractmethod
from models import Job, JobFilter


class BaseScraper(ABC):
    source_name: str = ""

    @abstractmethod
    async def search(self, query: str, location: str, job_filter: JobFilter) -> list[Job]:
        pass
