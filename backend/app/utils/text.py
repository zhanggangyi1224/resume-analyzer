from __future__ import annotations

import re
from datetime import date

TECH_KEYWORDS = {
    "python",
    "java",
    "golang",
    "go",
    "c",
    "c++",
    "c#",
    "javascript",
    "typescript",
    "rust",
    "php",
    "ruby",
    "kotlin",
    "swift",
    "scala",
    "sql",
    "mysql",
    "postgresql",
    "redis",
    "mongodb",
    "elasticsearch",
    "hadoop",
    "spark",
    "hive",
    "flink",
    "kafka",
    "docker",
    "kubernetes",
    "linux",
    "git",
    "fastapi",
    "django",
    "flask",
    "spring",
    "vue",
    "react",
    "angular",
    "nodejs",
    "node",
    "grpc",
    "restful",
    "tensorflow",
    "pytorch",
    "llm",
    "rag",
    "langchain",
    "aws",
    "aliyun",
    "gcp",
    "机器学习",
    "深度学习",
    "数据分析",
    "后端",
    "前端",
    "算法",
    "云原生",
    "微服务",
    "大模型",
    "自然语言处理",
}

CN_STOPWORDS = {
    "负责",
    "参与",
    "以及",
    "相关",
    "进行",
    "具有",
    "能够",
    "以上",
    "以下",
    "熟悉",
    "掌握",
    "岗位",
    "职位",
    "工作",
    "简历",
    "经验",
    "能力",
    "团队",
    "公司",
    "项目",
}

EN_STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "you",
    "your",
    "from",
    "that",
    "this",
    "into",
    "must",
    "should",
    "years",
    "year",
    "experience",
    "resume",
    "work",
    "team",
}

SHORT_EN_TOKENS = {"ai", "ml", "ui", "ux", "go", "c", "js"}
SHORT_CN_TOKENS = {"前端", "后端", "算法", "运维", "建模", "优化", "数据", "模型"}
CN_NOISE_TOKENS = {
    "使用",
    "负责",
    "兴趣",
    "其他",
    "语言",
    "地址",
    "手机",
    "邮箱",
    "教育",
    "背景",
    "项目",
    "经历",
    "课程",
    "能力",
    "基础",
    "客户",
    "管理",
    "维护",
    "生产",
    "年以上经验",
    "本科及以上",
}

SECTION_ALIASES = {
    "个人信息": "基本信息",
    "基本信息": "基本信息",
    "联系方式": "基本信息",
    "contact": "基本信息",
    "contact info": "基本信息",
    "profile": "基本信息",
    "求职意向": "求职信息",
    "求职信息": "求职信息",
    "期望职位": "求职信息",
    "期望薪资": "求职信息",
    "job objective": "求职信息",
    "objective": "求职信息",
    "工作经历": "工作经历",
    "工作经验": "工作经历",
    "实习经历": "工作经历",
    "work experience": "工作经历",
    "experience": "工作经历",
    "教育背景": "教育背景",
    "教育经历": "教育背景",
    "学历背景": "教育背景",
    "education": "教育背景",
    "技能": "技能",
    "专业技能": "技能",
    "技能栈": "技能",
    "skills": "技能",
    "项目经历": "项目经历",
    "项目经验": "项目经历",
    "projects": "项目经历",
    "project experience": "项目经历",
    "证书": "证书",
    "获奖": "获奖",
    "荣誉奖项": "获奖",
    "自我评价": "自我评价",
    "个人总结": "自我评价",
}

HEADING_PATTERNS = [
    "个人信息",
    "基本信息",
    "联系方式",
    "求职意向",
    "求职信息",
    "期望职位",
    "期望薪资",
    "工作经历",
    "工作经验",
    "实习经历",
    "教育背景",
    "教育经历",
    "学历背景",
    "技能",
    "专业技能",
    "技能栈",
    "项目经历",
    "项目经验",
    "荣誉奖项",
    "获奖",
    "证书",
    "自我评价",
    "个人总结",
]

EN_HEADING_PATTERNS = [
    "contact",
    "contact info",
    "profile",
    "job objective",
    "objective",
    "work experience",
    "experience",
    "education",
    "skills",
    "projects",
    "project experience",
]

BULLET_CHARS = "•●▪◦■□◆◇・"


def normalize_text(text: str) -> str:
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\u200b\u200c\u200d\ufeff]", "", text)
    text = text.replace("\r", "\n")

    text = _insert_heading_breaks(text)
    text = re.sub(rf"\s*[{re.escape(BULLET_CHARS)}]\s*", "\n- ", text)
    text = re.sub(
        r"\s*(\d{4}[./年]\d{1,2}\s*[—–-]\s*(?:\d{4}[./年]\d{1,2}|至今|现在))",
        r"\n\1",
        text,
    )

    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\s+([,.;:，。；：])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.fullmatch(r"[-_=]{3,}", line):
            continue
        if re.fullmatch(r"\d{1,2}", line):
            continue
        lines.append(line)

    return "\n".join(lines)


def split_sections(text: str) -> dict[str, str]:
    if not text.strip():
        return {}

    sections: dict[str, str] = {}
    current_title = "全文"
    bucket: list[str] = []

    for line in text.split("\n"):
        heading = _normalize_heading(line)
        if heading:
            if bucket:
                sections[current_title] = "\n".join(bucket).strip()
                bucket = []
            current_title = heading
            continue
        bucket.append(line)

    if bucket:
        sections[current_title] = "\n".join(bucket).strip()

    return {key: value for key, value in sections.items() if value}


def _insert_heading_breaks(text: str) -> str:
    for heading in sorted(HEADING_PATTERNS, key=len, reverse=True):
        if len(heading) <= 2:
            # Avoid splitting combined headings like "专业技能" into "专业" + "技能".
            pattern = rf"(?<![\u4e00-\u9fffA-Za-z0-9])({re.escape(heading)})(?![\u4e00-\u9fffA-Za-z0-9])"
        else:
            pattern = rf"(?<!\n)\s*({re.escape(heading)})\s*(?:[:：]\s*)?"
        text = re.sub(
            pattern,
            r"\n\1\n",
            text,
        )

    for heading in sorted(EN_HEADING_PATTERNS, key=len, reverse=True):
        text = re.sub(
            rf"(?<!\n)\s*({re.escape(heading)})\s*(?:[:：]\s*)?",
            r"\n\1\n",
            text,
            flags=re.IGNORECASE,
        )

    return text


def _normalize_heading(line: str) -> str | None:
    normalized = line.strip().strip(":：").strip()
    if not normalized:
        return None

    if normalized in SECTION_ALIASES:
        return SECTION_ALIASES[normalized]

    lowered = normalized.lower()
    if lowered in SECTION_ALIASES:
        return SECTION_ALIASES[lowered]

    if len(normalized) <= 12:
        for pattern, target in SECTION_ALIASES.items():
            if pattern in normalized:
                return target

    return None


def _extract_english_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[A-Za-z][A-Za-z0-9+#\-.]{1,30}", text.lower()):
        token = token.strip(".")
        if len(token) < 2 or token in EN_STOPWORDS:
            continue
        if len(token) < 3 and token not in SHORT_EN_TOKENS and token not in TECH_KEYWORDS:
            continue
        if token in {"http", "https", "www", "com", "gmail"}:
            continue
        tokens.add(token)
    return tokens


def _extract_chinese_tokens(text: str) -> set[str]:
    tokens = set()
    for token in re.findall(r"[\u4e00-\u9fff]{2,8}", text):
        if token in CN_STOPWORDS or token in CN_NOISE_TOKENS:
            continue
        if token.endswith(("公司", "负责", "进行", "能力")):
            continue
        if len(token) <= 2 and token not in SHORT_CN_TOKENS and token not in TECH_KEYWORDS:
            continue
        if token.endswith(("背景", "经历", "课程", "语言", "地址")):
            continue
        if token.endswith(("经验", "要求", "以上", "以下")) and token not in TECH_KEYWORDS:
            continue
        tokens.add(token)
    return tokens


def extract_keywords(text: str, limit: int = 30) -> list[str]:
    lowered = text.lower()
    found_skills = {keyword for keyword in TECH_KEYWORDS if _contains_skill_keyword(keyword, text, lowered)}

    english_tokens = _extract_english_tokens(text)
    chinese_tokens = _extract_chinese_tokens(text)

    keywords = list(found_skills | english_tokens | chinese_tokens)
    keywords = [token.lower() if re.fullmatch(r"[A-Za-z0-9+#\-.]+", token) else token for token in keywords]
    keywords = sorted(set(keywords), key=lambda x: (x not in found_skills, len(x), x))
    return keywords[:limit]


def _contains_skill_keyword(keyword: str, text: str, lowered: str) -> bool:
    if re.search(r"[\u4e00-\u9fff]", keyword):
        return keyword in text

    target = keyword.lower()
    pattern = rf"(?<![a-z0-9+#\-.]){re.escape(target)}(?![a-z0-9+#\-.])"
    return bool(re.search(pattern, lowered))


def parse_years_from_text(text: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+?\s*年(?:工作)?经验",
        r"工作\s*(\d+(?:\.\d+)?)\s*年",
        r"(\d+(?:\.\d+)?)\s*years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def parse_required_years(text: str) -> float | None:
    patterns = [
        r"(\d+(?:\.\d+)?)\s*\+?\s*年(?:以上)?",
        r"至少\s*(\d+(?:\.\d+)?)\s*年",
        r"(\d+(?:\.\d+)?)\s*\+?\s*years?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def estimate_years_by_date_ranges(text: str) -> float | None:
    range_pattern = re.compile(
        r"(\d{4})(?:[./年-](\d{1,2}))?\s*[—–-]\s*(至今|现在|present|current|\d{4})(?:[./年-](\d{1,2}))?",
        flags=re.IGNORECASE,
    )
    today = date.today()

    spans: list[float] = []
    for match in range_pattern.finditer(text):
        start_year = int(match.group(1))
        start_month = _normalize_month(match.group(2), default=1)
        end_raw = match.group(3).lower()
        end_month = _normalize_month(match.group(4), default=12)

        if end_raw in {"至今", "现在", "present", "current"}:
            end_year = today.year
            end_month = today.month
        else:
            end_year = int(end_raw)

        if not (1990 <= start_year <= today.year + 1):
            continue
        if not (1990 <= end_year <= today.year + 1):
            continue

        months = (end_year - start_year) * 12 + (end_month - start_month)
        if months <= 0:
            continue
        spans.append(months / 12.0)

    if not spans:
        return None
    return round(max(spans), 2)


def _normalize_month(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        month = int(value)
    except ValueError:
        return default
    return max(1, min(12, month))


def normalize_score(value: float, scale: float = 100.0) -> float:
    value = max(0.0, min(scale, value))
    return round(value, 2)
