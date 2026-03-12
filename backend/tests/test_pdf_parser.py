"""Tests for multi-page parsing and repeated header/footer cleanup."""

from app.services import pdf_parser


class DummyPage:
    """Minimal fake page object compatible with parser expectations."""

    def __init__(self, content: str) -> None:
        self.content = content

    def extract_text(self) -> str:
        """Return deterministic text used in parser tests."""

        return self.content


class DummyReader:
    """Fake PDF reader with two clean pages."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.pages = [DummyPage("第一页 简历信息"), DummyPage("第二页 项目经历")]
        self.is_encrypted = False


class DummyReaderWithRepeatedHeaderFooter:
    """Fake reader where header should be removed across pages."""

    def __init__(self, *_args, **_kwargs) -> None:
        self.pages = [
            DummyPage("简历标题\n第1页\n教育背景\n墨尔本大学"),
            DummyPage("简历标题\n第2页\n项目经历\n交易系统开发"),
        ]
        self.is_encrypted = False


def test_parse_pdf_bytes_with_multi_pages(monkeypatch) -> None:
    """Parser should keep text from all pages."""

    monkeypatch.setattr(pdf_parser, "PdfReader", DummyReader)

    result = pdf_parser.parse_pdf_bytes(b"%PDF-1.4 mock")

    assert result.page_count == 2
    assert "第一页" in result.cleaned_text
    assert "第二页" in result.cleaned_text


def test_parse_pdf_bytes_removes_repeated_headers(monkeypatch) -> None:
    """Repeated title line across pages should be removed as header noise."""

    monkeypatch.setattr(pdf_parser, "PdfReader", DummyReaderWithRepeatedHeaderFooter)

    result = pdf_parser.parse_pdf_bytes(b"%PDF-1.4 mock")

    assert "简历标题" not in result.raw_text
    assert "教育背景" in result.cleaned_text
    assert "项目经历" in result.cleaned_text
