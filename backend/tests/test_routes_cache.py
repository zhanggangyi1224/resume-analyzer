from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.schemas import ContactInfo, MatchResult, MatchScore, ParseResult, ResumeExtraction
from app.services.cache import CacheService


def _fake_match_result() -> MatchResult:
    return MatchResult(
        score=MatchScore(
            final_score=88.0,
            heuristic_score=84.0,
            ai_score=92.0,
            skill_match_rate=0.8,
            experience_relevance=0.9,
            education_relevance=1.0,
            role_relevance=0.9,
            skill_score=80.0,
            experience_score=90.0,
            education_score=100.0,
            role_score=90.0,
            matched_keywords_count=2,
            total_job_keywords=3,
        ),
        job_keywords=["python", "fastapi", "redis"],
        resume_keywords=["python", "fastapi"],
        matched_keywords=["python", "fastapi"],
        missing_keywords=["redis"],
        strengths=["技能匹配较好"],
        gaps=["缺少 Redis 经验"],
        summary="匹配度良好",
    )


def test_analyze_then_match_reuses_match_cache(monkeypatch) -> None:
    monkeypatch.setattr(routes, "cache", CacheService(redis_url=None, default_ttl_seconds=3600))
    calls = {"parse": 0, "extract": 0, "match": 0}

    def fake_parse_pdf_bytes(_: bytes) -> ParseResult:
        calls["parse"] += 1
        return ParseResult(
            page_count=1,
            raw_text="raw",
            cleaned_text="python fastapi",
            sections={"全文": "python fastapi"},
        )

    async def fake_extract(*, cleaned_text: str, sections: dict[str, str]) -> ResumeExtraction:
        calls["extract"] += 1
        assert cleaned_text
        assert sections
        return ResumeExtraction(
            contact=ContactInfo(name="张刚以"),
            work_years=3,
            education_background="计算机本科",
            skills=["python", "fastapi"],
        )

    async def fake_match(
        *,
        extraction: ResumeExtraction,
        resume_text: str,
        job_description: str,
    ) -> MatchResult:
        calls["match"] += 1
        assert extraction.skills
        assert resume_text
        assert job_description
        return _fake_match_result()

    monkeypatch.setattr(routes, "parse_pdf_bytes", fake_parse_pdf_bytes)
    monkeypatch.setattr(routes.extractor, "extract", fake_extract)
    monkeypatch.setattr(routes.matcher, "match", fake_match)

    client = TestClient(app)
    files = {"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")}
    data = {"job_description": "招聘 Python 后端工程师，熟悉 FastAPI 和 Redis"}

    analyze_resp = client.post("/api/v1/resumes/analyze", data=data, files=files)
    assert analyze_resp.status_code == 200
    assert analyze_resp.json()["cached"] is False

    match_resp = client.post("/api/v1/resumes/match", data=data, files=files)
    assert match_resp.status_code == 200
    assert match_resp.json()["cached"] is True

    assert calls == {"parse": 1, "extract": 1, "match": 1}
