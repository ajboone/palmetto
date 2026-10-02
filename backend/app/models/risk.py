from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"


class EvidenceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    PARTIAL = "PARTIAL"


class RiskComponent(BaseModel):
    name: str
    score: int | None = Field(ge=0)
    max_score: int = Field(gt=0)
    explanation: str
    evidence_status: EvidenceStatus
    source: str | None
    observed_values: dict[str, str | int | float | None]
    unit: str | None


class RiskAssessment(BaseModel):
    risk_level: RiskLevel | None
    score: int = Field(ge=0, le=100)
    max_score: int = 100
    assessed_at: datetime
    location_name: str
    evidence_status: EvidenceStatus
    components: list[RiskComponent]
    contributing_factors: list[str]
    unavailable_sources: list[str]
    limitations: list[str]
    methodology: str
    disclaimer: str