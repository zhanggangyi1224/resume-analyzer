"""Resume-to-JD matching service with deterministic and AI-assisted scoring."""

from __future__ import annotations

from typing import Any

from app.schemas import MatchResult, MatchScore, ResumeExtraction
from app.services.ai_client import AIClient
from app.utils.text import (
    extract_keywords,
    normalize_score,
    parse_required_years,
    parse_years_from_text,
)

DEGREE_LEVELS = {
    "高中": 1,
    "中专": 1,
    "大专": 2,
    "专科": 2,
    "本科": 3,
    "学士": 3,
    "硕士": 4,
    "研究生": 4,
    "博士": 5,
}

ROLE_KEYWORDS = {
    "前端开发工程师": {"前端", "react", "vue", "typescript", "javascript", "css", "ui", "ux"},
    "后端开发工程师": {"后端", "fastapi", "spring", "java", "node", "redis", "mysql", "api"},
    "全栈开发工程师": {"fullstack", "full-stack", "全栈"},
    "机器学习工程师": {"机器学习", "深度学习", "pytorch", "tensorflow", "llm", "rag", "nlp", "kaggle"},
    "数据分析工程师": {"数据分析", "sql", "pandas", "bi", "dashboard", "etl"},
}


class JobMatcher:
    """Compute keyword/experience/education/role fit and final match result."""

    def __init__(self, ai_client: AIClient | None = None) -> None:
        self.ai_client = ai_client

    async def match(
        self,
        extraction: ResumeExtraction,
        resume_text: str,
        job_description: str,
    ) -> MatchResult:
        """Return detailed match result for one resume against one JD text."""

        job_keywords = extract_keywords(job_description, limit=48)

        resume_keyword_source = "\n".join(
            [
                resume_text,
                extraction.education_background or "",
                extraction.job_intention or "",
                " ".join(extraction.project_experience),
                " ".join(extraction.skills),
            ]
        )
        resume_keywords = extract_keywords(resume_keyword_source, limit=70)

        job_keyword_map = {keyword.lower(): keyword for keyword in job_keywords}
        resume_keyword_map = {keyword.lower(): keyword for keyword in resume_keywords}

        matched_norm = sorted(set(job_keyword_map) & set(resume_keyword_map))
        missing_norm = sorted(set(job_keyword_map) - set(resume_keyword_map))

        matched_keywords = [job_keyword_map[key] for key in matched_norm]
        missing_keywords = [job_keyword_map[key] for key in missing_norm]

        skill_match_rate = len(matched_norm) / len(job_keyword_map) if job_keyword_map else 0.0

        required_years = parse_required_years(job_description)
        candidate_years = extraction.work_years or parse_years_from_text(resume_text)
        experience_relevance = _experience_relevance(required_years, candidate_years)

        education_relevance = _education_relevance(
            extraction.education_background or resume_text,
            job_description,
        )

        job_role = _infer_role(job_description)
        resume_role = extraction.job_intention or _infer_role(resume_keyword_source)
        role_relevance = _role_relevance(job_role, resume_role)

        skill_score = normalize_score(skill_match_rate * 100)
        experience_score = normalize_score(experience_relevance * 100)
        education_score = normalize_score(education_relevance * 100)
        role_score = normalize_score(role_relevance * 100)

        # Baseline score from deterministic signals.
        # Weight choice:
        # - skills (50%): most direct proxy for immediate delivery capability.
        # - experience (20%): validates seniority against JD expectation.
        # - education (15%): useful but usually less decisive than hard skills.
        # - role relevance (15%): keeps role direction aligned (frontend/backend/fullstack/ml).
        # This score is always available and serves as the fallback when AI is disabled/unreachable.
        heuristic_score = normalize_score(
            0.5 * skill_score
            + 0.2 * experience_score
            + 0.15 * education_score
            + 0.15 * role_score
        )

        ai_score = None
        ai_reason = None
        ai_strengths: list[str] = []
        ai_gaps: list[str] = []

        if self.ai_client and self.ai_client.enabled:
            ai_payload = await self.ai_client.score_match(
                resume_summary=resume_keyword_source,
                job_description=job_description,
                heuristic_score=heuristic_score,
            )

            if ai_payload is None and self.ai_client.require_success:
                reason = self.ai_client.last_error or "AI score failed"
                raise RuntimeError(reason)

            if ai_payload:
                ai_score = _to_optional_score(ai_payload.get("ai_score"))
                ai_reason = _to_optional_text(ai_payload.get("reason"))
                ai_strengths = _to_string_list(ai_payload.get("strengths"), limit=4)
                ai_gaps = _to_string_list(ai_payload.get("gaps"), limit=4)

        # Blend AI score only when present.
        # We keep heuristic as the major component to maintain stability/reproducibility,
        # and use AI as a calibrated adjustment to capture semantic fit from free-text JD/resume.
        # If AI has no valid output, we keep final_score identical to heuristic_score.
        final_score = (
            normalize_score(0.65 * heuristic_score + 0.35 * ai_score)
            if ai_score is not None
            else heuristic_score
        )

        strengths = ai_strengths or _build_strengths(
            matched_keywords=matched_keywords,
            skill_match_rate=skill_match_rate,
            candidate_years=candidate_years,
            required_years=required_years,
            resume_role=resume_role,
        )

        gaps = ai_gaps or _build_gaps(
            missing_keywords=missing_keywords,
            skill_match_rate=skill_match_rate,
            candidate_years=candidate_years,
            required_years=required_years,
            role_relevance=role_relevance,
        )

        summary = _build_summary(
            final_score=final_score,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            required_years=required_years,
            candidate_years=candidate_years,
            ai_reason=ai_reason,
        )

        score = MatchScore(
            final_score=final_score,
            heuristic_score=heuristic_score,
            ai_score=ai_score,
            skill_match_rate=round(skill_match_rate, 4),
            experience_relevance=round(experience_relevance, 4),
            education_relevance=round(education_relevance, 4),
            role_relevance=round(role_relevance, 4),
            skill_score=skill_score,
            experience_score=experience_score,
            education_score=education_score,
            role_score=role_score,
            matched_keywords_count=len(matched_keywords),
            total_job_keywords=len(job_keyword_map),
        )
        return MatchResult(
            score=score,
            job_keywords=job_keywords,
            resume_keywords=resume_keywords,
            matched_keywords=matched_keywords,
            missing_keywords=missing_keywords,
            strengths=strengths,
            gaps=gaps,
            summary=summary,
        )


def _experience_relevance(required: float | None, candidate: float | None) -> float:
    """Score candidate years against required years."""

    if required is None:
        return 0.75
    if candidate is None:
        return 0.35
    if candidate >= required:
        return 1.0
    return max(0.0, round(candidate / max(required, 1.0), 4))


def _education_relevance(candidate_text: str, jd_text: str) -> float:
    """Score education relevance by highest degree level comparison."""

    required_level = _max_degree_level(jd_text)
    candidate_level = _max_degree_level(candidate_text)

    if required_level is None:
        return 0.75
    if candidate_level is None:
        return 0.35
    if candidate_level >= required_level:
        return 1.0
    return round(candidate_level / required_level, 4)


def _max_degree_level(text: str) -> int | None:
    """Return max mapped degree level found in text."""

    levels = [value for key, value in DEGREE_LEVELS.items() if key in text]
    return max(levels) if levels else None


def _infer_role(text: str) -> str | None:
    """Infer role family from keyword hits."""

    lowered = text.lower()
    role_scores: dict[str, int] = {}

    for role, keywords in ROLE_KEYWORDS.items():
        role_scores[role] = sum(
            1 for keyword in keywords if keyword in lowered or keyword in text
        )

    top_role = max(role_scores, key=role_scores.get)
    top_score = role_scores[top_role]

    if top_score <= 0:
        return None

    front_score = role_scores.get("前端开发工程师", 0)
    back_score = role_scores.get("后端开发工程师", 0)
    fullstack_score = role_scores.get("全栈开发工程师", 0)
    if (front_score >= 2 and back_score >= 2) or fullstack_score >= 1:
        return "全栈开发工程师"

    return top_role


def _role_relevance(job_role: str | None, resume_role: str | None) -> float:
    """Score semantic relevance between inferred JD role and resume role."""

    if job_role is None and resume_role is None:
        return 0.7
    if job_role is None or resume_role is None:
        return 0.55
    if job_role == resume_role:
        return 1.0

    compatible_pairs = {
        ("前端开发工程师", "全栈开发工程师"),
        ("后端开发工程师", "全栈开发工程师"),
        ("全栈开发工程师", "前端开发工程师"),
        ("全栈开发工程师", "后端开发工程师"),
    }
    if (job_role, resume_role) in compatible_pairs:
        return 0.78

    return 0.35


def _to_optional_score(value: Any) -> float | None:
    """Parse optional numeric score into normalized 0-100 range."""

    try:
        if value is None:
            return None
        return normalize_score(float(value))
    except (TypeError, ValueError):
        return None


def _to_optional_text(value: Any) -> str | None:
    """Convert value to non-empty string when possible."""

    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_string_list(value: Any, limit: int = 4) -> list[str]:
    """Normalize arbitrary value to deduplicated short string list."""

    if not isinstance(value, list):
        return []
    result: list[str] = []
    seen = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _build_strengths(
    matched_keywords: list[str],
    skill_match_rate: float,
    candidate_years: float | None,
    required_years: float | None,
    resume_role: str | None,
) -> list[str]:
    """Generate human-readable strengths when AI strengths are unavailable."""

    strengths: list[str] = []

    if matched_keywords:
        strengths.append(f"关键词命中：{', '.join(matched_keywords[:6])}")
    if skill_match_rate >= 0.5:
        strengths.append("核心技能覆盖较好")

    if candidate_years is not None and required_years is not None and candidate_years >= required_years:
        strengths.append(f"工作年限满足要求（{candidate_years:g} 年）")
    elif candidate_years is not None:
        strengths.append(f"具备可验证工作经历（约 {candidate_years:g} 年）")

    if resume_role:
        strengths.append(f"岗位方向：{resume_role}")

    return strengths[:4]


def _build_gaps(
    missing_keywords: list[str],
    skill_match_rate: float,
    candidate_years: float | None,
    required_years: float | None,
    role_relevance: float,
) -> list[str]:
    """Generate concise improvement gaps when AI gaps are unavailable."""

    gaps: list[str] = []

    if missing_keywords:
        gaps.append(f"待补技能：{', '.join(missing_keywords[:6])}")
    if skill_match_rate < 0.35:
        gaps.append("关键词命中率偏低，建议补充与 JD 强相关项目")

    if required_years is not None:
        if candidate_years is None:
            gaps.append(f"简历未明确体现工作年限（岗位要求约 {required_years:g} 年）")
        elif candidate_years < required_years:
            gaps.append(f"工作年限偏少：{candidate_years:g}/{required_years:g} 年")

    if role_relevance < 0.5:
        gaps.append("岗位方向与 JD 存在偏差")

    return gaps[:4]


def _build_summary(
    final_score: float,
    matched_keywords: list[str],
    missing_keywords: list[str],
    required_years: float | None,
    candidate_years: float | None,
    ai_reason: str | None,
) -> str:
    """Build one-paragraph summary for frontend display."""

    hit_preview = "、".join(matched_keywords[:6]) if matched_keywords else "暂无明显重合关键词"
    miss_preview = "、".join(missing_keywords[:5]) if missing_keywords else "暂无明显短板关键词"

    experience_msg = (
        f"岗位要求约 {required_years:g} 年，候选人约 {candidate_years:g} 年。"
        if required_years is not None and candidate_years is not None
        else "岗位或简历未提供明确工作年限。"
    )

    summary = (
        f"匹配度 {final_score:.2f} 分；命中关键词：{hit_preview}；"
        f"待补关键词：{miss_preview}。{experience_msg}"
    )
    if ai_reason:
        summary += f" AI 评估：{ai_reason}"
    return summary
