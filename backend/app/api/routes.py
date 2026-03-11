from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import get_settings
from app.schemas import (
    AnalyzeResponse,
    ExtractionResponse,
    KeywordRequest,
    KeywordResponse,
    MatchResult,
    MatchResponse,
    ParseResponse,
)
from app.services.ai_client import AIClient
from app.services.cache import CacheService
from app.services.extractor import ResumeExtractor
from app.services.matcher import JobMatcher
from app.services.pdf_parser import PDFParseError, parse_pdf_bytes
from app.utils.hash_utils import sha256_bytes, sha256_text
from app.utils.text import extract_keywords

settings = get_settings()
cache = CacheService(
    redis_url=settings.redis_url,
    default_ttl_seconds=settings.cache_ttl_seconds,
)
ai_client = AIClient(settings)
extractor = ResumeExtractor(ai_client=ai_client)
matcher = JobMatcher(ai_client=ai_client)

router = APIRouter()


@router.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name, "version": settings.app_version}


@router.post("/jobs/keywords", response_model=KeywordResponse)
async def analyze_job_keywords(payload: KeywordRequest) -> KeywordResponse:
    keywords = extract_keywords(payload.job_description, limit=40)
    return KeywordResponse(keywords=keywords)


@router.post("/resumes/parse", response_model=ParseResponse)
async def parse_resume(file: UploadFile = File(...)) -> ParseResponse:
    file_bytes, resume_id = await _read_and_validate_pdf(file)
    response, from_cache = await _get_or_parse(file_bytes, resume_id)
    response.cached = from_cache
    return response


@router.post("/resumes/extract", response_model=ExtractionResponse)
async def extract_resume(file: UploadFile = File(...)) -> ExtractionResponse:
    file_bytes, resume_id = await _read_and_validate_pdf(file)
    response, from_cache = await _get_or_extract(file_bytes, resume_id)
    response.cached = from_cache
    return response


@router.post("/resumes/match", response_model=MatchResponse)
async def match_resume(
    file: UploadFile = File(...),
    job_description: str = Form(..., min_length=3),
) -> MatchResponse:
    file_bytes, resume_id = await _read_and_validate_pdf(file)
    match_result, from_cache = await _get_or_match(
        file_bytes=file_bytes,
        resume_id=resume_id,
        job_description=job_description,
    )
    return MatchResponse(resume_id=resume_id, match=match_result, cached=from_cache)


@router.post("/resumes/analyze", response_model=AnalyzeResponse)
async def analyze_resume(
    file: UploadFile = File(...),
    job_description: str | None = Form(default=None),
) -> AnalyzeResponse:
    file_bytes, resume_id = await _read_and_validate_pdf(file)

    jd_key = sha256_text(job_description)[:16] if job_description else "no_jd"
    cache_key = f"analyze:{resume_id}:{jd_key}"

    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        cached_response = AnalyzeResponse.model_validate(cached_payload)
        cached_response.cached = True
        return cached_response

    parse_response, _ = await _get_or_parse(file_bytes, resume_id)
    extraction_response, _ = await _get_or_extract(file_bytes, resume_id)

    match_result = None
    if job_description:
        match_result, _ = await _get_or_match(
            file_bytes=file_bytes,
            resume_id=resume_id,
            job_description=job_description,
            parse_response=parse_response,
            extraction_response=extraction_response,
        )

    response = AnalyzeResponse(
        resume_id=resume_id,
        parsed=parse_response.parsed,
        extraction=extraction_response.extraction,
        match=match_result,
    )
    await cache.set_json(cache_key, response.model_dump(mode="json"))
    return response


async def _get_or_parse(file_bytes: bytes, resume_id: str) -> tuple[ParseResponse, bool]:
    cache_key = f"parse:{resume_id}"
    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        return ParseResponse.model_validate(cached_payload), True

    try:
        parsed = parse_pdf_bytes(file_bytes)
    except PDFParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    response = ParseResponse(resume_id=resume_id, parsed=parsed)
    await cache.set_json(cache_key, response.model_dump(mode="json"))
    return response, False


async def _get_or_extract(file_bytes: bytes, resume_id: str) -> tuple[ExtractionResponse, bool]:
    cache_key = f"extract:{resume_id}"
    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        return ExtractionResponse.model_validate(cached_payload), True

    parse_response, _ = await _get_or_parse(file_bytes, resume_id)
    try:
        extraction = await extractor.extract(
            cleaned_text=parse_response.parsed.cleaned_text,
            sections=parse_response.parsed.sections,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    response = ExtractionResponse(resume_id=resume_id, extraction=extraction)
    await cache.set_json(cache_key, response.model_dump(mode="json"))
    return response, False


async def _get_or_match(
    file_bytes: bytes,
    resume_id: str,
    job_description: str,
    parse_response: ParseResponse | None = None,
    extraction_response: ExtractionResponse | None = None,
) -> tuple[MatchResult, bool]:
    jd_hash = sha256_text(job_description)[:16]
    cache_key = f"match:{resume_id}:{jd_hash}"

    cached_payload = await cache.get_json(cache_key)
    if cached_payload:
        cached_response = MatchResponse.model_validate(cached_payload)
        return cached_response.match, True

    current_parse = parse_response
    if current_parse is None:
        current_parse, _ = await _get_or_parse(file_bytes, resume_id)

    current_extraction = extraction_response
    if current_extraction is None:
        current_extraction, _ = await _get_or_extract(file_bytes, resume_id)

    match_result = await matcher.match(
        extraction=current_extraction.extraction,
        resume_text=current_parse.parsed.cleaned_text,
        job_description=job_description,
    )
    response = MatchResponse(resume_id=resume_id, match=match_result)
    await cache.set_json(cache_key, response.model_dump(mode="json"))
    return match_result, False


async def _read_and_validate_pdf(file: UploadFile) -> tuple[bytes, str]:
    filename = file.filename or ""
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only single PDF file upload is supported")

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in {
        "application/pdf",
        "application/x-pdf",
        "application/octet-stream",
        "binary/octet-stream",
    }:
        raise HTTPException(status_code=400, detail="Uploaded file must be in PDF format")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    file_size_mb = len(file_bytes) / (1024 * 1024)
    if file_size_mb > settings.max_pdf_size_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Max size: {settings.max_pdf_size_mb} MB",
        )

    resume_id = sha256_bytes(file_bytes)[:16]
    return file_bytes, resume_id
