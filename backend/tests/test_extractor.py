"""Unit tests for rule-based extraction behavior."""

import asyncio

from app.services.extractor import ResumeExtractor
from app.utils.text import normalize_text, split_sections


def test_extract_contact_fields_from_inline_resume() -> None:
    """Contact fields should be extracted from compact single-line resume text."""

    raw = (
        "张刚以 邮箱：zhanggangyi1224@gmail.com 手机：15252657633 "
        "地址：浙江省嘉兴市桐乡市复兴名邸佳凯苑8栋1单元2601室 "
        "教育背景 南洋理工大学 人工智能理学硕士 项目经历 ICN Navigator平台"
    )
    cleaned = normalize_text(raw)
    sections = split_sections(cleaned)

    extractor = ResumeExtractor(ai_client=None)
    result = asyncio.run(extractor.extract(cleaned, sections))

    assert result.contact.name == "张刚以"
    assert result.contact.phone == "15252657633"
    assert result.contact.email == "zhanggangyi1224@gmail.com"
    assert result.contact.address is not None
    assert "教育背景" not in result.contact.address


def test_extract_background_summary_and_projects() -> None:
    """Education summary and project titles should stay concise and relevant."""

    raw = (
        "教育背景\n"
        "墨尔本大学 计算与软件系统理学学士 2023-2025\n"
        "项目经历\n"
        "ICN Navigator平台 前端负责人，负责React与API集成\n"
        "交通标志分类系统 使用机器学习实现95%准确率\n"
    )
    cleaned = normalize_text(raw)
    sections = split_sections(cleaned)

    extractor = ResumeExtractor(ai_client=None)
    result = asyncio.run(extractor.extract(cleaned, sections))

    assert result.education_background is not None
    assert "墨尔本大学" in result.education_background
    assert result.project_experience
    assert any("ICN Navigator" in item for item in result.project_experience)


def test_extract_work_years_from_date_ranges_and_infer_job_intention() -> None:
    """Date ranges should infer work years and role intent from context."""

    raw = (
        "专业技能\n"
        "前端：React、TypeScript、CSS3\n"
        "工作经历\n"
        "前端开发工程师\n"
        "2023.06 – 2024.09 负责Web前端开发\n"
        "项目经历\n"
        "交易平台系统 2025.04 – 2025.09\n"
    )
    cleaned = normalize_text(raw)
    sections = split_sections(cleaned)

    extractor = ResumeExtractor(ai_client=None)
    result = asyncio.run(extractor.extract(cleaned, sections))

    assert result.work_years is not None
    assert result.work_years >= 1.2
    assert result.job_intention in {"前端开发工程师", "全栈开发工程师"}
