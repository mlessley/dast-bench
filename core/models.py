from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class VendorSource(str, Enum):
    SEEDED = "seeded"
    DISCOVERED = "discovered"


class VendorStatus(str, Enum):
    CANDIDATE = "candidate"
    FINALIST = "finalist"
    REJECTED = "rejected"
    EVALUATED = "evaluated"


class Confidence(str, Enum):
    PAPER = "paper"
    HANDS_ON = "hands-on"


class Criterion(BaseModel):
    id: str
    category: str
    name: str
    description: str
    weight: float = Field(ge=0, le=100)
    rubric: str


class CriteriaTaxonomy(BaseModel):
    version: int = 1
    criteria: list[Criterion] = Field(default_factory=list)

    def weight_total(self) -> float:
        return sum(c.weight for c in self.criteria)

    def validate_weights(self, tolerance: float = 0.01) -> list[str]:
        total = self.weight_total()
        if abs(total - 100.0) > tolerance:
            return [f"criteria weights sum to {total:.2f}, expected 100.00"]
        return []

    def get(self, criterion_id: str) -> Criterion | None:
        return next((c for c in self.criteria if c.id == criterion_id), None)


class ScoreEntry(BaseModel):
    criterion_id: str
    score: float = Field(ge=1, le=5)
    evidence: str
    confidence: Confidence
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Observation(BaseModel):
    context: str
    note: str
    tags: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class HandsOnResult(BaseModel):
    test_id: str
    description: str
    automated: bool
    benchmark_id: str | None = None
    outcome: str
    observations: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Vendor(BaseModel):
    id: str
    name: str
    source: VendorSource
    status: VendorStatus = VendorStatus.CANDIDATE
    website: str = ""
    notes: str = ""
    ci_tool_id: str | None = None
    scores: list[ScoreEntry] = Field(default_factory=list)
    hands_on_results: list[HandsOnResult] = Field(default_factory=list)
    observations: list[Observation] = Field(default_factory=list)

    def score_for(self, criterion_id: str) -> ScoreEntry | None:
        matches = [s for s in self.scores if s.criterion_id == criterion_id]
        return matches[-1] if matches else None


class BenchmarkVulnerability(BaseModel):
    id: str
    name: str
    severity: str


class Benchmark(BaseModel):
    id: str
    name: str
    target_type: str
    known_vulnerabilities: list[BenchmarkVulnerability] = Field(default_factory=list)


class ResearchFinding(BaseModel):
    url: str
    snippet: str


class CriterionResearchCache(BaseModel):
    researched_at: datetime = Field(default_factory=datetime.utcnow)
    queries: list[str] = Field(default_factory=list)
    findings: list[ResearchFinding] = Field(default_factory=list)
    reviewed_by_gap_check: bool = False
    stale: bool = False


class VendorResearchCache(BaseModel):
    vendor_id: str
    criteria: dict[str, CriterionResearchCache] = Field(default_factory=dict)
