"""Unit tests for text normalization, section split, and keyword helpers."""

from app.utils.text import (
    estimate_years_by_date_ranges,
    extract_keywords,
    normalize_text,
    split_sections,
)


def test_normalize_text_removes_extra_spaces() -> None:
    """Normalizer should collapse duplicate whitespace and preserve content."""

    raw = "姓名： 张三\n\n\nPython   FastAPI\r\n  Redis"
    cleaned = normalize_text(raw)
    assert "\n\n" not in cleaned
    assert "  " not in cleaned
    assert "Python FastAPI" in cleaned


def test_split_sections_detects_headings() -> None:
    """Section splitter should detect canonical headings."""

    text = "个人信息\n姓名：张三\n工作经历\n在某公司负责后端开发"
    sections = split_sections(text)
    assert "基本信息" in sections
    assert "工作经历" in sections


def test_normalize_text_and_split_sections_for_inline_resume() -> None:
    """Inline resumes should still produce education/project/skill sections."""

    raw = (
        "张三 电话13800138000 教育背景 墨尔本大学 计算机本科 "
        "项目经历 交易系统开发 技能 Python FastAPI Redis"
    )
    cleaned = normalize_text(raw)
    sections = split_sections(cleaned)

    assert "教育背景" in sections
    assert "项目经历" in sections
    assert "技能" in sections


def test_extract_keywords_includes_tech_words() -> None:
    """Keyword extractor should keep technical terms."""

    text = "熟悉 Python、FastAPI、Redis，负责后端服务设计"
    keywords = extract_keywords(text)
    assert "python" in keywords
    assert "fastapi" in keywords


def test_estimate_years_by_date_ranges() -> None:
    """Date ranges should be converted to non-zero years estimate."""

    text = "工作经历 2023.06 – 2024.09 前端开发工程师"
    years = estimate_years_by_date_ranges(text)
    assert years is not None
    assert years >= 1.2
