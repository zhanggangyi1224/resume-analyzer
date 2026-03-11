from __future__ import annotations

import asyncio
import json
import re
from typing import Any

import httpx

from app.core.config import Settings


class AIClient:
    def __init__(self, settings: Settings) -> None:
        self.ai_provider = settings.ai_provider
        self.timeout = settings.ai_timeout_seconds
        self.require_success = settings.ai_provider in {"gemini", "openai"}
        self.last_error: str | None = None

        self.gemini_api_key = settings.gemini_api_key
        self.gemini_base_url = settings.gemini_base_url.rstrip("/")
        self.gemini_model = settings.gemini_model

        self.openai_api_key = settings.openai_api_key
        self.openai_base_url = settings.openai_base_url.rstrip("/")
        self.openai_model = settings.openai_model

    @property
    def enabled(self) -> bool:
        return bool(self._provider_order())

    def _provider_order(self) -> list[str]:
        if self.ai_provider == "gemini":
            return ["gemini"] if self.gemini_api_key else []
        if self.ai_provider == "openai":
            return ["openai"] if self.openai_api_key else []

        providers: list[str] = []
        if self.gemini_api_key:
            providers.append("gemini")
        if self.openai_api_key:
            providers.append("openai")
        return providers

    async def _chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        self.last_error = None
        for provider in self._provider_order():
            if provider == "gemini":
                response = await self._chat_json_gemini(system_prompt, user_prompt)
            else:
                response = await self._chat_json_openai(system_prompt, user_prompt)

            if response:
                return response

        return None

    async def _chat_json_openai(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        if not self.openai_api_key:
            return None

        url = f"{self.openai_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.openai_model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            self.last_error = f"OpenAI API HTTP {exc.response.status_code}: {exc.response.text[:240]}"
            return None
        except Exception:
            self.last_error = "OpenAI API request failed"
            return None

        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        parsed = _try_parse_json(content)
        if parsed is None:
            self.last_error = "OpenAI API returned non-JSON or invalid JSON response"
        else:
            self.last_error = None
        return parsed

    async def _chat_json_gemini(self, system_prompt: str, user_prompt: str) -> dict[str, Any] | None:
        if not self.gemini_api_key:
            return None

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                "You are a strict JSON API.\n"
                                f"System instruction:\n{system_prompt}\n\n"
                                f"User input:\n{user_prompt}"
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
            },
        }

        retryable_status = {429, 500, 502, 503, 504}
        model_candidates = _dedupe_preserve_order(
            [
                self.gemini_model,
                "gemini-2.0-flash",
                "gemini-flash-latest",
                "gemini-2.0-flash-lite",
                "gemini-flash-lite-latest",
            ]
        )

        for model in model_candidates:
            url = f"{self.gemini_base_url}/models/{model}:generateContent"

            for attempt in range(2):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            url,
                            params={"key": self.gemini_api_key},
                            json=payload,
                        )
                        response.raise_for_status()
                        data = response.json()
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    self.last_error = (
                        f"Gemini API model={model} HTTP {status}: {exc.response.text[:240]}"
                    )
                    if status in retryable_status and attempt == 0:
                        await asyncio.sleep(0.8)
                        continue
                    if status in retryable_status or status in {400, 404}:
                        break
                    return None
                except Exception:
                    self.last_error = f"Gemini API request failed (model={model})"
                    if attempt == 0:
                        await asyncio.sleep(0.5)
                        continue
                    break

                content = _extract_gemini_text(data)
                parsed = _try_parse_json(content)
                if parsed is not None:
                    self.last_error = None
                    return parsed

                self.last_error = f"Gemini API model={model} returned non-JSON or invalid JSON response"
                break

        return None

    async def extract_resume(self, text: str) -> dict[str, Any] | None:
        system_prompt = (
            "You are a resume information extraction model. "
            "Extract contact, job intention and background fields with high precision. "
            "Return valid JSON only, no markdown and no extra keys."
        )
        user_prompt = (
            "Extract fields from resume text. If unavailable, use null or empty list.\n"
            "Rules:\n"
            "1) Keep contact.name as a real person's name, not title or sentence.\n"
            "2) contact.address should be concise and not include other sections.\n"
            "3) education_background must be concise (max 4 entries) and never copy whole resume text.\n"
            "4) project_experience should be list of project titles/short bullets (max 6, each under 80 chars).\n"
            "5) skills should be concise technical keywords only (max 40), remove generic words.\n"
            "6) Infer job_intention from role evidence when explicit statement is missing.\n"
            "7) expected_salary may be null when resume does not provide salary expectation.\n"
            "8) work_years must be numeric when known.\n"
            "Schema (strict):\n"
            "{"
            '"contact": {"name": null, "phone": null, "email": null, "address": null},'
            '"job_intention": null,'
            '"expected_salary": null,'
            '"work_years": null,'
            '"education_background": null,'
            '"project_experience": [],'
            '"skills": []'
            "}\n\n"
            f"Resume text:\n{text[:14000]}"
        )
        return await self._chat_json(system_prompt, user_prompt)

    async def score_match(
        self,
        resume_summary: str,
        job_description: str,
        heuristic_score: float,
    ) -> dict[str, Any] | None:
        system_prompt = (
            "You score how well a resume fits a job description. "
            "Return JSON only."
        )
        user_prompt = (
            "Given resume and JD, return JSON:\n"
            '{"ai_score": 0-100 number, "reason": "short explanation", "strengths": [], "gaps": []}\n\n'
            f"Heuristic score (reference only): {heuristic_score}\n\n"
            f"Resume summary:\n{resume_summary[:6000]}\n\n"
            f"Job description:\n{job_description[:5000]}"
        )
        return await self._chat_json(system_prompt, user_prompt)


def _extract_gemini_text(data: dict[str, Any]) -> str:
    candidates = data.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return ""

    texts: list[str] = []
    for candidate in candidates:
        content = candidate.get("content") if isinstance(candidate, dict) else None
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                texts.append(part["text"])

    return "\n".join(texts).strip()


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result: list[str] = []
    for item in items:
        value = item.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _try_parse_json(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None

    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    fenced_match = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", raw)
    if fenced_match:
        raw = fenced_match.group(1)

    brace_match = re.search(r"(\{[\s\S]*\})", raw)
    if brace_match:
        try:
            parsed = json.loads(brace_match.group(1))
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None

    return None
