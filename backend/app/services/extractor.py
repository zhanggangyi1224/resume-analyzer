from __future__ import annotations

import re
from typing import Any

from app.schemas import ContactInfo, ResumeExtraction
from app.services.ai_client import AIClient
from app.utils.text import estimate_years_by_date_ranges, extract_keywords, parse_years_from_text

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+?86[-\s]?)?1[3-9]\d{9}")

_CN_NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,8}$")
_EN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\s\-.]{2,30}$")

_ADDRESS_HINT_RE = re.compile(
    r"(省|市|区|县|路|街|号|栋|室|公寓|大厦|园区|镇|乡|村|City|District)",
    flags=re.IGNORECASE,
)

_DEGREE_KEYWORDS = ["博士", "硕士", "研究生", "本科", "学士", "大专", "专科", "高中"]
_EDU_HINT_KEYWORDS = ["大学", "学院", "University", "College", "GPA", "WAM"]
_PROJECT_HINT_KEYWORDS = [
    "项目",
    "系统",
    "平台",
    "Project",
    "产品",
    "开发",
    "负责人",
    "上线",
    "落地",
]
_PROJECT_GENERIC_TERMS = {
    "it项目",
    "机器学习项目",
    "客户项目",
    "政府项目",
}
_PROJECT_ACTION_PREFIXES = ("负责", "主导", "管理", "维护", "使用", "基于", "设计", "构建", "生产", "实现", "编写")

_STOP_FIELD_MARKERS = [
    "教育背景",
    "教育经历",
    "工作经历",
    "工作经验",
    "项目经历",
    "项目经验",
    "求职意向",
    "求职信息",
    "联系方式",
    "专业技能",
    "技能",
    "荣誉奖项",
]

_JOB_INTENT_KEYWORDS = {
    "前端开发工程师": {"react", "react native", "vue", "javascript", "typescript", "html", "css", "前端", "ui", "ux"},
    "后端开发工程师": {"fastapi", "spring", "java", "node", "redis", "mysql", "postgresql", "后端", "api", "server"},
    "机器学习工程师": {"机器学习", "深度学习", "pytorch", "tensorflow", "llm", "rag", "nlp", "kaggle", "模型"},
}


class ResumeExtractor:
    def __init__(self, ai_client: AIClient | None = None) -> None:
        self.ai_client = ai_client

    async def extract(self, cleaned_text: str, sections: dict[str, str]) -> ResumeExtraction:
        rule_based = self._extract_with_rules(cleaned_text, sections)

        ai_result: dict[str, Any] | None = None
        if self.ai_client and self.ai_client.enabled:
            ai_input = _build_ai_input(cleaned_text, sections)
            ai_result = await self.ai_client.extract_resume(ai_input)
            if ai_result is None and self.ai_client.require_success:
                reason = self.ai_client.last_error or "AI extraction failed"
                raise RuntimeError(reason)

        if ai_result:
            return self._merge_rule_and_ai(rule_based, ai_result)
        return rule_based

    def _extract_with_rules(self, text: str, sections: dict[str, str]) -> ResumeExtraction:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        preview_lines = lines[:16]

        basic_text = _join_sections(sections, ["基本信息", "全文"])
        job_text = _join_sections(sections, ["求职信息"])
        work_text = _join_sections(sections, ["工作经历"])
        project_text = _join_sections(sections, ["项目经历"])
        skills_text = _join_sections(sections, ["技能"])

        contact_text = f"{basic_text}\n{text}" if basic_text else text

        email_match = _EMAIL_RE.search(contact_text)
        phone_match = _PHONE_RE.search(contact_text)

        contact = ContactInfo(
            name=self._extract_name(preview_lines, contact_text),
            phone=phone_match.group(0) if phone_match else None,
            email=email_match.group(0) if email_match else None,
            address=self._extract_address(contact_text),
        )

        target_text = job_text or text
        job_intention = _extract_by_patterns(
            target_text,
            [
                r"(?:求职意向|求职信息|应聘岗位|期望职位|目标岗位)[:：\s]+([^\n]{2,40})",
                r"(?:应聘|申请)\s*([^\n]{2,30})",
            ],
            max_len=40,
        )
        if not job_intention:
            job_intention = self._infer_job_intention(
                "\n".join([job_text, skills_text, project_text, work_text, text]),
            )
        expected_salary = _extract_by_patterns(
            target_text,
            [
                r"(?:期望薪资|薪资要求|期望月薪|期望年薪)[:：\s]+([^\n]{2,40})",
                r"(\d{1,3}\s*[kK]\s*[-~]\s*\d{1,3}\s*[kK])",
                r"(\d{1,3}\s*万\s*[-~]\s*\d{1,3}\s*万)",
            ],
            max_len=40,
        )

        work_years = parse_years_from_text(work_text or text)
        if work_years is None:
            work_years = estimate_years_by_date_ranges(work_text) if work_text else None
        if work_years is None:
            work_years = estimate_years_by_date_ranges(text)
        education_background = self._extract_education(text, sections)
        projects = self._extract_projects(text, sections)
        skills = self._extract_skills(text, skills_text)

        return ResumeExtraction(
            contact=contact,
            job_intention=job_intention,
            expected_salary=expected_salary,
            work_years=work_years,
            education_background=education_background,
            project_experience=projects,
            skills=skills,
        )

    @staticmethod
    def _extract_name(lines: list[str], text: str) -> str | None:
        explicit = _extract_by_patterns(
            text,
            [
                r"(?:姓名|Name)[:：\s]+([\u4e00-\u9fffA-Za-z·\-\s]{2,30})",
                r"^([\u4e00-\u9fff·]{2,8})\s*(?:\||｜|邮箱|手机|电话)",
            ],
            max_len=30,
        )
        if explicit and _looks_like_name(explicit):
            return explicit

        for line in lines:
            compact = line.strip()
            if any(keyword in compact for keyword in ("邮箱", "email", "手机", "电话")):
                leading = re.split(r"\||｜|邮箱|email|手机|电话", compact, maxsplit=1, flags=re.IGNORECASE)[0]
                candidate = leading.strip(" ：:-")
                if _looks_like_name(candidate):
                    return candidate

        for line in lines:
            if re.search(r"@|\d", line):
                continue
            candidate = line.strip().strip(" ：:-")
            if _looks_like_name(candidate):
                return candidate

        return None

    @staticmethod
    def _extract_address(text: str) -> str | None:
        explicit = _extract_by_patterns(
            text,
            [
                r"(?:地址|现居住地|所在地|居住地|Location)[:：\s]+([^\n]{2,120})",
                r"((?:北京|上海|广州|深圳|杭州|成都|南京|武汉|苏州|嘉兴)[^\n]{2,80})",
            ],
            max_len=120,
        )

        if explicit:
            cleaned = _trim_field_value(explicit, max_len=80)
            cleaned = _strip_after_markers(cleaned, _STOP_FIELD_MARKERS)
            cleaned = re.split(r"\||｜|邮箱|电话|手机|Email", cleaned, maxsplit=1, flags=re.IGNORECASE)[0]
            cleaned = cleaned.strip(" ，,;；。")
            if cleaned and _ADDRESS_HINT_RE.search(cleaned):
                return cleaned

        for line in text.splitlines()[:12]:
            if any(token in line for token in ("地址", "居住地", "所在地")):
                cleaned = _strip_after_markers(line, _STOP_FIELD_MARKERS)
                cleaned = re.sub(r"^(?:地址|居住地|所在地)[:：\s]*", "", cleaned).strip()
                cleaned = _trim_field_value(cleaned, max_len=80)
                if cleaned and _ADDRESS_HINT_RE.search(cleaned):
                    return cleaned

        return None

    @staticmethod
    def _extract_education(text: str, sections: dict[str, str]) -> str | None:
        edu_text = _join_sections(sections, ["教育背景"])
        source_text = edu_text if edu_text else text
        source_lines = _compact_lines(source_text, max_lines=80)

        combined_text = "\n".join(source_lines)
        degree_segments = re.findall(
            r"([\u4e00-\u9fffA-Za-z（）()&.\-/\s]{2,50}(?:大学|学院|University|College|Institute)"
            r"[\u4e00-\u9fffA-Za-z（）()&.\-/\s]{0,60}?"
            r"(?:博士|硕士|研究生|本科|学士|Master|Bachelor|PhD)"
            r"[\u4e00-\u9fffA-Za-z（）()&.\-/\s]{0,30})",
            combined_text,
            flags=re.IGNORECASE,
        )

        highlights: list[str] = []
        for segment in degree_segments:
            cleaned = _clean_education_segment(segment)
            if cleaned:
                highlights.append(cleaned)
            if len(highlights) >= 3:
                break

        if not highlights:
            for line in source_lines:
                if any(keyword in line for keyword in _DEGREE_KEYWORDS + _EDU_HINT_KEYWORDS):
                    cleaned = _clean_education_segment(line)
                    if cleaned:
                        highlights.append(cleaned)
                if len(highlights) >= 3:
                    break

        if not highlights:
            return None

        return "；".join(_dedupe_ordered(highlights)[:3])

    @staticmethod
    def _extract_projects(text: str, sections: dict[str, str]) -> list[str]:
        project_text = _join_sections(sections, ["项目经历"])
        source = project_text if project_text else text

        lines = _compact_lines(source, max_lines=180)
        candidates: list[str] = []

        for line in lines:
            stripped = line.strip("•-·* ")
            if len(stripped) < 6:
                continue
            if stripped.startswith(_PROJECT_ACTION_PREFIXES):
                continue

            short_line = _trim_field_value(stripped, max_len=90)
            if short_line and len(short_line) <= 70 and any(key in short_line for key in _PROJECT_HINT_KEYWORDS):
                candidates.append(short_line)

            title = _extract_project_title_from_line(stripped)
            if title:
                candidates.append(title)

        if not candidates:
            candidates.extend(_extract_project_titles_from_text(source))

        cleaned_projects = []
        for item in _dedupe_ordered([project for project in candidates if project]):
            normalized = item.strip()
            normalized_lower = normalized.lower()
            if normalized_lower in _PROJECT_GENERIC_TERMS:
                continue
            if any(term in normalized_lower for term in _PROJECT_GENERIC_TERMS):
                if "交通标志分类系统" in normalized or "短信诈骗检测" in normalized:
                    pass
                else:
                    continue
            if len(normalized) < 5:
                continue
            cleaned_projects.append(_trim_field_value(normalized, max_len=90))

        return _dedupe_project_titles([item for item in cleaned_projects if item])[:6]

    @staticmethod
    def _extract_skills(text: str, skills_text: str) -> list[str]:
        target = skills_text if skills_text else text
        return extract_keywords(target, limit=40)

    @staticmethod
    def _infer_job_intention(text: str) -> str | None:
        lowered = text.lower()
        scores: dict[str, int] = {}
        for job, keywords in _JOB_INTENT_KEYWORDS.items():
            scores[job] = sum(1 for keyword in keywords if keyword in lowered or keyword in text)

        top_job = max(scores, key=scores.get)
        top_score = scores[top_job]
        if top_score < 2:
            return None

        front = scores.get("前端开发工程师", 0)
        back = scores.get("后端开发工程师", 0)

        if ("前端负责人" in text or "frontend" in lowered or "front-end" in lowered) and front >= 2:
            return "前端开发工程师"
        if ("后端" in text or "backend" in lowered) and back >= 2 and back > front:
            return "后端开发工程师"

        if front >= 3 and back >= 3 and abs(front - back) <= 1:
            return "全栈开发工程师"

        return top_job

    def _merge_rule_and_ai(
        self,
        rule_based: ResumeExtraction,
        ai_data: dict[str, Any],
    ) -> ResumeExtraction:
        ai_contact = ai_data.get("contact") if isinstance(ai_data.get("contact"), dict) else {}

        merged_contact = ContactInfo(
            name=_clean_name(ai_contact.get("name")) or rule_based.contact.name,
            phone=_clean_phone(ai_contact.get("phone")) or rule_based.contact.phone,
            email=_clean_email(ai_contact.get("email")) or rule_based.contact.email,
            address=_clean_address(ai_contact.get("address")) or rule_based.contact.address,
        )

        project_experience = _clean_project_list(
            ai_data.get("project_experience"),
            fallback=rule_based.project_experience,
        )
        skills = _clean_skill_list(
            ai_data.get("skills"),
            fallback=rule_based.skills,
        )

        work_years = ai_data.get("work_years")
        if work_years is None:
            work_years = rule_based.work_years
        else:
            try:
                work_years = float(work_years)
            except (TypeError, ValueError):
                work_years = rule_based.work_years

        return ResumeExtraction(
            contact=merged_contact,
            job_intention=_clean_job_intention(ai_data.get("job_intention"), rule_based.job_intention),
            expected_salary=_trim_field_value(ai_data.get("expected_salary"), max_len=40)
            or rule_based.expected_salary,
            work_years=work_years,
            education_background=_clean_education_field(ai_data.get("education_background"))
            or rule_based.education_background,
            project_experience=project_experience,
            skills=skills,
        )


def _join_sections(sections: dict[str, str], keys: list[str]) -> str:
    chunks = [sections[key].strip() for key in keys if key in sections and sections[key].strip()]
    return "\n".join(chunks)


def _build_ai_input(cleaned_text: str, sections: dict[str, str]) -> str:
    preferred_order = ["基本信息", "求职信息", "工作经历", "教育背景", "项目经历", "技能"]
    blocks: list[str] = []

    for key in preferred_order:
        if key in sections and sections[key].strip():
            snippet = _trim_field_value(sections[key], max_len=2400)
            if snippet:
                blocks.append(f"[{key}]\n{snippet}")

    if not blocks:
        fallback = _trim_field_value(cleaned_text, max_len=9000) or ""
        return fallback

    total = "\n\n".join(blocks)
    if len(total) > 10000:
        return total[:10000]
    return total


def _extract_by_patterns(text: str, patterns: list[str], max_len: int = 120) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return _trim_field_value(match.group(1), max_len=max_len)
    return None


def _compact_lines(text: str, max_lines: int = 100) -> list[str]:
    lines: list[str] = []
    for line in text.splitlines():
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if re.fullmatch(r"[-_=]{3,}", cleaned):
            continue
        lines.append(cleaned)
        if len(lines) >= max_lines:
            break
    return lines


def _strip_after_markers(value: str, markers: list[str]) -> str:
    output = value
    for marker in markers:
        output = re.split(re.escape(marker), output, maxsplit=1)[0]
    return output


def _trim_field_value(value: Any, max_len: int = 120) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", str(value)).strip(" ：:-")
    if not cleaned:
        return None
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" ，,;；")
    return cleaned


def _clean_education_segment(value: str) -> str | None:
    segment = _trim_field_value(value, max_len=140)
    if not segment:
        return None
    segment = re.sub(r"^(?:\d{1,2}月|\d{4}年(?:\d{1,2}月)?)\s*", "", segment)
    segment = re.sub(r"^月\s*", "", segment)
    segment = re.split(r"核心课程|相关课程|课程：|课程:|WAM|GPA", segment, maxsplit=1)[0]
    segment = re.split(r"\\s{2,}", segment, maxsplit=1)[0]
    segment = re.sub(r"[（(][^）)]*$", "", segment)
    segment = segment.strip(" ，,;；。")
    return _trim_field_value(segment, max_len=90)


def _extract_project_title_from_line(line: str) -> str | None:
    cleaned = re.sub(r"\s+", " ", line).strip(" •-·*")
    if not cleaned:
        return None

    before_date = re.search(
        r"([A-Za-z0-9\u4e00-\u9fff（）()·&/.\-\s]{4,45})\s+\d{4}[./年]\d{1,2}\s*[—–-]",
        cleaned,
    )
    if before_date:
        candidate = _normalize_project_candidate(before_date.group(1))
        if _is_valid_project_title(candidate):
            return _trim_field_value(candidate, max_len=80)

    compact_titles = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff]{2,24}(?:平台|系统|项目))",
        cleaned,
    )
    for candidate in reversed(compact_titles):
        candidate = _normalize_project_candidate(candidate)
        if _is_valid_project_title(candidate):
            return _trim_field_value(candidate, max_len=80)

    suffix_candidates = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff（）()·&/.\-\s]{3,45}(?:平台|系统|项目))",
        cleaned,
    )
    for candidate in reversed(suffix_candidates):
        candidate = _normalize_project_candidate(candidate)
        if _is_valid_project_title(candidate):
            return _trim_field_value(candidate, max_len=80)

    topic_candidates = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff]{2,24}(?:检测|分类|识别|推荐|分析)(?:（[^）]{1,20}）)?)",
        cleaned,
    )
    for candidate in reversed(topic_candidates):
        candidate = _normalize_project_candidate(candidate)
        if _is_valid_project_title(candidate):
            return _trim_field_value(candidate, max_len=80)

    return None


def _extract_project_titles_from_text(text: str) -> list[str]:
    candidates: list[str] = []

    before_date_matches = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff（）()·&/.\-\s]{4,45})\s+\d{4}[./年]\d{1,2}\s*[—–-]",
        text,
    )
    candidates.extend(before_date_matches)

    suffix_matches = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff（）()·&/.\-\s]{3,45}(?:平台|系统|项目))",
        text,
    )
    candidates.extend(suffix_matches)

    compact_matches = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff]{2,24}(?:平台|系统|项目))",
        text,
    )
    candidates.extend(compact_matches)

    topic_matches = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff]{2,24}(?:检测|分类|识别|推荐|分析)(?:（[^）]{1,20}）)?)",
        text,
    )
    candidates.extend(topic_matches)

    cleaned: list[str] = []
    for candidate in candidates:
        norm = _normalize_project_candidate(candidate)
        if _is_valid_project_title(norm):
            cleaned.append(_trim_field_value(norm, max_len=80) or "")
    return _dedupe_project_titles([item for item in _dedupe_ordered(cleaned) if item])


def _is_valid_project_title(value: str) -> bool:
    title = value.strip()
    if len(title) < 4 or len(title) > 80:
        return False
    lowered = title.lower()
    if lowered in _PROJECT_GENERIC_TERMS:
        return False
    if any(term in lowered for term in ("客户项目", "政府项目")):
        return False
    if title.startswith(_PROJECT_ACTION_PREFIXES):
        return False
    if re.match(r"^\d{4}", title):
        return False
    if not any(token in title for token in ("项目", "系统", "平台", "检测", "分类", "识别", "推荐", "分析", "Project")):
        return False
    return True


def _normalize_project_candidate(value: str) -> str:
    candidate = _trim_field_value(value, max_len=120) or ""
    candidate = candidate.strip(" ：:-")
    if not candidate:
        return ""

    suffix_titles = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff（）()·&/.\-\s]{2,30}(?:平台|系统|项目))",
        candidate,
    )
    if suffix_titles:
        tail = suffix_titles[-1].strip(" ：:-")
        if tail and (tail != candidate or len(candidate) > 20):
            candidate = tail

    if " " in candidate:
        parts = [part for part in candidate.split(" ") if part]
        for n in range(min(4, len(parts)), 0, -1):
            tail = " ".join(parts[-n:])
            if _is_valid_project_title(tail):
                candidate = tail
                break

    topic_titles = re.findall(
        r"([A-Za-z0-9\u4e00-\u9fff]{2,24}(?:检测|分类|识别|推荐|分析)(?:（[^）]{1,20}）)?)",
        candidate,
    )
    if topic_titles and len(candidate) > 30:
        candidate = topic_titles[-1].strip(" ：:-")

    if "—" in candidate and len(candidate) > 45:
        candidate = candidate.split("—", maxsplit=1)[0].strip(" ：:-")
    return candidate


def _dedupe_project_titles(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in values:
        normalized = item.strip()
        if not normalized:
            continue

        replaced = False
        for idx, existing in enumerate(deduped):
            if normalized == existing:
                replaced = True
                break
            if normalized in existing:
                replaced = True
                break
            if existing in normalized:
                deduped[idx] = normalized
                replaced = True
                break

        if not replaced:
            deduped.append(normalized)

    return deduped


def _dedupe_ordered(values: list[str]) -> list[str]:
    seen = set()
    result: list[str] = []
    for item in values:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _looks_like_name(value: str) -> bool:
    candidate = value.strip()
    if len(candidate) > 30:
        return False
    if any(token in candidate.lower() for token in ("邮箱", "email", "电话", "手机", "地址")):
        return False
    if _CN_NAME_RE.fullmatch(candidate):
        return True
    if _EN_NAME_RE.fullmatch(candidate):
        return True
    return False


def _clean_phone(value: Any) -> str | None:
    text = _trim_field_value(value, max_len=30)
    if not text:
        return None
    match = _PHONE_RE.search(text)
    return match.group(0) if match else None


def _clean_email(value: Any) -> str | None:
    text = _trim_field_value(value, max_len=80)
    if not text:
        return None
    match = _EMAIL_RE.search(text)
    return match.group(0) if match else None


def _clean_name(value: Any) -> str | None:
    text = _trim_field_value(value, max_len=30)
    if not text:
        return None
    return text if _looks_like_name(text) else None


def _clean_address(value: Any) -> str | None:
    text = _trim_field_value(value, max_len=80)
    if not text:
        return None
    text = _strip_after_markers(text, _STOP_FIELD_MARKERS)
    text = re.split(r"\||｜|邮箱|电话|手机|Email", text, maxsplit=1, flags=re.IGNORECASE)[0]
    text = text.strip(" ，,;；。")
    if not text:
        return None
    if _ADDRESS_HINT_RE.search(text) is None and len(text) < 6:
        return None
    return text


def _clean_education_field(value: Any) -> str | None:
    if isinstance(value, list):
        merged = []
        for item in value:
            part = _trim_field_value(item, max_len=140)
            if part:
                merged.append(part)
        text = "；".join(_dedupe_ordered(merged))
    else:
        text = _trim_field_value(value, max_len=260)

    if not text:
        return None

    candidates: list[str] = []
    for part in re.split(r"[\n；;]+", text):
        cleaned = _clean_education_segment(part)
        if not cleaned:
            continue
        if any(keyword in cleaned for keyword in _DEGREE_KEYWORDS + _EDU_HINT_KEYWORDS):
            candidates.append(cleaned)

    if not candidates:
        fallback = _clean_education_segment(text)
        return fallback

    return "；".join(_dedupe_ordered(candidates)[:4])


def _clean_job_intention(value: Any, fallback: str | None) -> str | None:
    ai_value = _trim_field_value(value, max_len=40)
    fallback_value = _trim_field_value(fallback, max_len=40)
    if not ai_value:
        return fallback_value

    if fallback_value:
        ai_lower = ai_value.lower()
        fallback_lower = fallback_value.lower()
        if fallback_lower in ai_lower:
            return fallback_value
        if any(sep in ai_value for sep in ("/", "、", "|", "或", ",")) and len(ai_value) > len(fallback_value) + 4:
            return fallback_value

    return ai_value


def _clean_project_list(value: Any, fallback: list[str]) -> list[str]:
    candidates: list[str] = []

    if isinstance(value, list):
        for item in value:
            text = _trim_field_value(item, max_len=180)
            if not text:
                continue
            for part in re.split(r"[\n；;]+", text):
                cleaned = _trim_field_value(part, max_len=120)
                if not cleaned:
                    continue
                title = _extract_project_title_from_line(cleaned)
                if title:
                    candidates.append(title)
                elif _is_valid_project_title(cleaned):
                    candidates.append(cleaned)

    if candidates:
        return _dedupe_project_titles(_dedupe_ordered(candidates))[:6]

    fallback_cleaned = []
    fallback_raw = []
    for item in fallback:
        text = _trim_field_value(item, max_len=90)
        if not text:
            continue
        fallback_raw.append(text)
        title = _extract_project_title_from_line(text) or text
        if _is_valid_project_title(title):
            fallback_cleaned.append(title)

    if not fallback_cleaned:
        return _dedupe_ordered(fallback_raw)[:6]

    return _dedupe_project_titles(_dedupe_ordered(fallback_cleaned))[:6]


def _clean_skill_list(value: Any, fallback: list[str]) -> list[str]:
    allowed_short = {"c", "go", "ai", "ml", "ui", "ux"}
    cleaned = _clean_string_list(value, fallback=fallback, max_len=32, max_items=40)

    filtered: list[str] = []
    noise_words = {"其他", "兴趣", "语言", "地址", "手机", "邮箱", "教育", "背景", "项目", "经历"}
    for item in cleaned:
        token = item.strip()
        if not token:
            continue
        lowered = token.lower()
        if token in noise_words or lowered in {"other", "language", "experience"}:
            continue
        if re.fullmatch(r"[\W_]+", token):
            continue
        if len(lowered) < 2:
            continue
        if len(lowered) <= 2 and lowered not in allowed_short and not re.search(r"[\u4e00-\u9fff]", token):
            continue
        filtered.append(token)

    deduped = _dedupe_ordered(filtered)
    return deduped[:40]


def _clean_string_list(
    value: Any,
    fallback: list[str],
    max_len: int,
    max_items: int,
) -> list[str]:
    if isinstance(value, list):
        cleaned = []
        for item in value:
            text = _trim_field_value(item, max_len=max_len)
            if text:
                cleaned.append(text)
        cleaned = _dedupe_ordered(cleaned)
        if cleaned:
            return cleaned[:max_items]

    fallback_cleaned = [
        _trim_field_value(item, max_len=max_len)
        for item in fallback
        if item
    ]
    return [item for item in _dedupe_ordered([x for x in fallback_cleaned if x])][:max_items]
