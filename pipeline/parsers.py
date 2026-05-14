import re
from typing import Optional

TECH_KEYWORDS = {
    "java", "python", "javascript", "typescript", "go", "golang", "rust",
    "kotlin", "scala", "c++", "c#", ".net", "ruby", "php", "swift",
    "react", "angular", "vue", "spring", "spring boot", "hibernate",
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s",
    "postgresql", "mysql", "mongodb", "redis", "kafka", "rabbitmq",
    "graphql", "rest", "grpc", "microservices", "terraform", "jenkins",
    "git", "linux", "maven", "gradle", "node", "nodejs", "nextjs",
}

REMOTE_KEYWORDS = {"remote", "work from home", "wfh", "anywhere", "distributed", "fully remote"}


def parse_salary(salary_str: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse '$ 92,500 - $119,000 a year' or '$60/hr' into (min, max) annual integers."""
    if not salary_str or salary_str.upper() in ("N/A", "NULL", "NONE", ""):
        return None, None

    clean = salary_str.replace("$", "").replace(",", "").replace("K", "000").lower()
    is_hourly = "hour" in clean or "/hr" in clean
    multiplier = 2080 if is_hourly else 1

    numbers = re.findall(r"\d+(?:\.\d+)?", clean)
    if not numbers:
        return None, None

    nums = [int(float(n) * multiplier) for n in numbers[:2]]
    if len(nums) == 1:
        return nums[0], nums[0]
    return min(nums), max(nums)


def normalize_location(location: str) -> tuple[str, bool]:
    """Return (cleaned_location, is_remote)."""
    lower = location.lower()
    is_remote = any(kw in lower for kw in REMOTE_KEYWORDS)
    return location.strip(), is_remote


def extract_tech_stack(text: str) -> list[str]:
    """Return sorted list of tech keywords found in text."""
    text_lower = text.lower()
    return sorted(kw for kw in TECH_KEYWORDS if kw in text_lower)
