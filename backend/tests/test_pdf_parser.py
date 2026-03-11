from app.services import pdf_parser


class DummyPage:
    def __init__(self, content: str) -> None:
        self.content = content

    def extract_text(self) -> str:
        return self.content


class DummyReader:
    def __init__(self, *_args, **_kwargs) -> None:
        self.pages = [DummyPage("第一页 简历信息"), DummyPage("第二页 项目经历")]
        self.is_encrypted = False


class DummyReaderWithRepeatedHeaderFooter:
    def __init__(self, *_args, **_kwargs) -> None:
        self.pages = [
            DummyPage("简历标题\n第1页\n教育背景\n墨尔本大学"),
            DummyPage("简历标题\n第2页\n项目经历\n交易系统开发"),
        ]
        self.is_encrypted = False


def test_parse_pdf_bytes_with_multi_pages(monkeypatch) -> None:
    monkeypatch.setattr(pdf_parser, "PdfReader", DummyReader)

    result = pdf_parser.parse_pdf_bytes(b"%PDF-1.4 mock")

    assert result.page_count == 2
    assert "第一页" in result.cleaned_text
    assert "第二页" in result.cleaned_text


def test_parse_pdf_bytes_removes_repeated_headers(monkeypatch) -> None:
    monkeypatch.setattr(pdf_parser, "PdfReader", DummyReaderWithRepeatedHeaderFooter)

    result = pdf_parser.parse_pdf_bytes(b"%PDF-1.4 mock")

    assert "简历标题" not in result.raw_text
    assert "教育背景" in result.cleaned_text
    assert "项目经历" in result.cleaned_text
