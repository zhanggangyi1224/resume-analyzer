import asyncio

from app.schemas import ContactInfo, ResumeExtraction
from app.services.matcher import JobMatcher


def test_matcher_high_score_for_relevant_resume() -> None:
    extraction = ResumeExtraction(
        contact=ContactInfo(name="张三"),
        work_years=5,
        education_background="计算机科学本科",
        skills=["python", "fastapi", "redis", "docker"],
    )
    matcher = JobMatcher(ai_client=None)

    result = asyncio.run(
        matcher.match(
            extraction=extraction,
            resume_text="5年Python后端开发经验，熟悉FastAPI、Redis、Docker。",
            job_description="招聘Python后端工程师，要求3年以上经验，熟悉FastAPI和Redis，本科及以上。",
        )
    )

    assert result.score.final_score >= 65
    assert "python" in result.matched_keywords
