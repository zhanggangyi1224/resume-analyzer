from __future__ import annotations

from pydantic import BaseModel, Field


class ParseResult(BaseModel):
    page_count: int = Field(..., ge=1)
    raw_text: str
    cleaned_text: str
    sections: dict[str, str] = Field(default_factory=dict)


class ParseResponse(BaseModel):
    resume_id: str
    parsed: ParseResult
    cached: bool = False


class ContactInfo(BaseModel):
    name: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


class ResumeExtraction(BaseModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    job_intention: str | None = None
    expected_salary: str | None = None
    work_years: float | None = None
    education_background: str | None = None
    project_experience: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class ExtractionResponse(BaseModel):
    resume_id: str
    extraction: ResumeExtraction
    cached: bool = False


class KeywordRequest(BaseModel):
    job_description: str = Field(..., min_length=3)


class KeywordResponse(BaseModel):
    keywords: list[str] = Field(default_factory=list)


class MatchScore(BaseModel):
    final_score: float = Field(..., ge=0, le=100)
    heuristic_score: float = Field(..., ge=0, le=100)
    ai_score: float | None = Field(default=None, ge=0, le=100)
    skill_match_rate: float = Field(..., ge=0, le=1)
    experience_relevance: float = Field(..., ge=0, le=1)
    education_relevance: float = Field(..., ge=0, le=1)
    role_relevance: float = Field(..., ge=0, le=1)
    skill_score: float = Field(..., ge=0, le=100)
    experience_score: float = Field(..., ge=0, le=100)
    education_score: float = Field(..., ge=0, le=100)
    role_score: float = Field(..., ge=0, le=100)
    matched_keywords_count: int = Field(..., ge=0)
    total_job_keywords: int = Field(..., ge=0)


class MatchResult(BaseModel):
    score: MatchScore
    job_keywords: list[str] = Field(default_factory=list)
    resume_keywords: list[str] = Field(default_factory=list)
    matched_keywords: list[str] = Field(default_factory=list)
    missing_keywords: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    summary: str


class MatchResponse(BaseModel):
    resume_id: str
    match: MatchResult
    cached: bool = False


class AnalyzeResponse(BaseModel):
    resume_id: str
    parsed: ParseResult
    extraction: ResumeExtraction
    match: MatchResult | None = None
    cached: bool = False
