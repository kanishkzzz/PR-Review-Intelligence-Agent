from pydantic import BaseModel
from typing import List, Optional

class PRReviewRequest(BaseModel):
    pr_url: str
    token: Optional[str] = None  # private repos ke liye

class Issue(BaseModel):
    type: str          # SECURITY / LOGIC / QUALITY
    file: str
    description: str

class PRReviewResponse(BaseModel):
    summary: str
    risk_level: str    # HIGH / MEDIUM / LOW
    issues: List[Issue]
    suggestions: List[str]
    test_cases_missing: List[str]