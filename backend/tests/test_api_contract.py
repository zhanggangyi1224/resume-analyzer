from __future__ import annotations

from fastapi.testclient import TestClient

import app.api.routes as routes
from app.main import app
from app.schemas import ContactInfo, MatchResult, MatchScore, ParseResult, ResumeExtraction
from app.services.cache import CacheService


def _fake_match_result() -> MatchResult:
    return MatchResult(
        score=MatchScore(
            final_score=86.0,
            heuristic_score=82.0,
            ai_score=90.0,
            skill_match_rate=0.75,
            experience_relevance=0.8,
            education_relevance=1.0,
            role_relevance=0.9,
            skill_score=75.0,
            experience_score=80.0,
            education_score=100.0,
            role_score=90.0,
            matched_keywords_count=3,
            total_job_keywords=4,
        ),
        job_keywords=["python", "fastapi", "redis", "docker"],
        resume_keywords=["python", "fastapi", "redis"],
        matched_keywords=["python", "fastapi", "redis"],
        missing_keywords=["docker"],
        strengths=["核心技能匹配"],
        gaps=["缺少 Docker 项目经验"],
        summary="匹配较好",
    )


def test_analyze_response_contract(monkeypatch) -> None:
    monkeypatch.setattr(routes, "cache", CacheService(redis_url=None, default_ttl_seconds=3600))

    def fake_parse_pdf_bytes(_: bytes) -> ParseResult:
        return ParseResult(
            page_count=2,
            raw_text="raw content",
            cleaned_text="cleaned content",
            sections={"全文": "cleaned content"},
        )

    async def fake_extract(*, cleaned_text: str, sections: dict[str, str]) -> ResumeExtraction:
        assert cleaned_text
        assert sections
        return ResumeExtraction(
            contact=ContactInfo(
                name="张刚以",
                phone="15252657633",
                email="zhanggangyi1224@gmail.com",
                address="浙江省嘉兴市",
            ),
            job_intention="后端开发工程师",
            expected_salary="30k-40k",
            work_years=3.0,
            education_background="墨尔本大学 本科",
            project_experience=["ICN Navigator平台"],
            skills=["python", "fastapi", "redis"],
        )

    async def fake_match(
        *,
        extraction: ResumeExtraction,
        resume_text: str,
        job_description: str,
    ) -> MatchResult:
        assert extraction.job_intention
        assert resume_text
        assert job_description
        return _fake_match_result()

    monkeypatch.setattr(routes, "parse_pdf_bytes", fake_parse_pdf_bytes)
    monkeypatch.setattr(routes.extractor, "extract", fake_extract)
    monkeypatch.setattr(routes.matcher, "match", fake_match)

    client = TestClient(app)
    files = {"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")}
    data = {"job_description": "招聘 Python 后端工程师，熟悉 FastAPI、Redis、Docker"}
    response = client.post("/api/v1/resumes/analyze", data=data, files=files)

    assert response.status_code == 200
    payload = response.json()

    assert set(payload.keys()) == {"resume_id", "parsed", "extraction", "match", "cached"}
    assert payload["cached"] is False

    assert set(payload["parsed"].keys()) == {"page_count", "raw_text", "cleaned_text", "sections"}
    assert set(payload["extraction"].keys()) == {
        "contact",
        "job_intention",
        "expected_salary",
        "work_years",
        "education_background",
        "project_experience",
        "skills",
    }
    assert set(payload["match"].keys()) == {
        "score",
        "job_keywords",
        "resume_keywords",
        "matched_keywords",
        "missing_keywords",
        "strengths",
        "gaps",
        "summary",
    }


def test_analyze_without_jd_returns_match_null(monkeypatch) -> None:
    monkeypatch.setattr(routes, "cache", CacheService(redis_url=None, default_ttl_seconds=3600))

    def fake_parse_pdf_bytes(_: bytes) -> ParseResult:
        return ParseResult(
            page_count=1,
            raw_text="raw content",
            cleaned_text="cleaned content",
            sections={"全文": "cleaned content"},
        )

    async def fake_extract(*, cleaned_text: str, sections: dict[str, str]) -> ResumeExtraction:
        assert cleaned_text
        assert sections
        return ResumeExtraction(
            contact=ContactInfo(name="张刚以"),
            education_background="本科",
            skills=["python"],
        )

    monkeypatch.setattr(routes, "parse_pdf_bytes", fake_parse_pdf_bytes)
    monkeypatch.setattr(routes.extractor, "extract", fake_extract)

    client = TestClient(app)
    files = {"file": ("resume.pdf", b"%PDF-1.4 fake", "application/pdf")}
    response = client.post("/api/v1/resumes/analyze", files=files)

    assert response.status_code == 200
    payload = response.json()
    assert payload["match"] is None
    assert payload["cached"] is False
