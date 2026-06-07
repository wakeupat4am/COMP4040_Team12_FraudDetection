"""Gemini-backed advisory analysis for scored cases."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from ..config import Settings


DecisionValue = Literal["allow", "review", "block"]
ConfidenceValue = Literal["low", "medium", "high"]


class GeminiAdvisoryResult(BaseModel):
    recommended_decision: DecisionValue
    confidence: ConfidenceValue
    summary: str = Field(min_length=1)
    key_factors: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    follow_up_actions: list[str] = Field(default_factory=list)

    @field_validator("recommended_decision", "confidence", mode="before")
    @classmethod
    def _normalize_enum(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("key_factors", "risk_flags", "follow_up_actions", mode="before")
    @classmethod
    def _normalize_string_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            normalized = value.strip()
            return [normalized] if normalized else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        return [str(value).strip()] if str(value).strip() else []


class GeminiAnalysisPayload(GeminiAdvisoryResult):
    model: str
    analyzed_at: datetime
    source_score_run_id: int


class GeminiNotConfiguredError(RuntimeError):
    """Raised when Gemini is requested without required configuration."""


class GeminiUpstreamError(RuntimeError):
    """Raised when Gemini returns unusable output or the upstream call fails."""


class GeminiAdvisoryService:
    def __init__(self, api_key: str | None, model: str = "gemini-2.5-flash", timeout_seconds: int = 15) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiAdvisoryService":
        return cls(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout_seconds=settings.gemini_timeout_seconds,
        )

    def analyze_case(self, case_snapshot: dict[str, Any]) -> GeminiAdvisoryResult:
        if not self.api_key:
            raise GeminiNotConfiguredError("Gemini advisory analysis is not configured.")

        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise GeminiUpstreamError("google-genai is not installed.") from exc

        client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(
                api_version="v1alpha",
                timeout=self.timeout_seconds * 1000,
            ),
        )
        try:
            response = self._generate_structured_response(
                client,
                contents=self._build_prompt(case_snapshot),
            )
            try:
                return self._parse_response(response)
            except ValidationError:
                repaired_response = self._generate_structured_response(
                    client,
                    contents=self._build_repair_prompt(case_snapshot, getattr(response, "text", None)),
                )
                try:
                    return self._parse_response(repaired_response)
                except ValidationError as exc:
                    response_text = getattr(repaired_response, "text", None) or getattr(response, "text", None)
                    preview = self._response_preview(response_text)
                    raise GeminiUpstreamError(
                        f"Gemini returned invalid structured output. Raw response: {preview}",
                    ) from exc
        except GeminiUpstreamError:
            raise
        except Exception as exc:
            raise GeminiUpstreamError(f"Gemini analysis request failed: {exc}") from exc
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def build_analysis_payload(self, case_snapshot: dict[str, Any], source_score_run_id: int) -> dict[str, Any]:
        advisory = self.analyze_case(case_snapshot)
        payload = GeminiAnalysisPayload(
            **advisory.model_dump(),
            model=self.model,
            analyzed_at=datetime.now(tz=timezone.utc),
            source_score_run_id=source_score_run_id,
        )
        return payload.model_dump(mode="json")

    def _build_prompt(self, case_snapshot: dict[str, Any]) -> str:
        serialized_snapshot = json.dumps(case_snapshot, indent=2, sort_keys=True, default=str)
        return (
            "You are a fraud-operations advisory assistant. "
            "Review the provided case snapshot and return a structured recommendation. "
            "Return only a single JSON object with these exact fields: "
            "recommended_decision, confidence, summary, key_factors, risk_flags, follow_up_actions. "
            "Use only these enum values: recommended_decision in [allow, review, block], "
            "confidence in [low, medium, high]. "
            "Keep summary under 35 words. "
            "Return at most 3 key_factors, 3 risk_flags, and 3 follow_up_actions. "
            "Keep each list item under 12 words. "
            "Do not include markdown code fences or explanatory text outside the JSON object. "
            "Base your analysis only on the case snapshot below.\n\n"
            f"{serialized_snapshot}"
        )

    def _build_repair_prompt(self, case_snapshot: dict[str, Any], prior_response_text: Any) -> str:
        serialized_snapshot = json.dumps(case_snapshot, indent=2, sort_keys=True, default=str)
        prior_response = prior_response_text if isinstance(prior_response_text, str) and prior_response_text.strip() else "<empty>"
        return (
            "Your previous response did not match the required JSON format. "
            "Return only one valid JSON object with these exact fields: "
            "recommended_decision, confidence, summary, key_factors, risk_flags, follow_up_actions. "
            "No markdown, no prose, no code fences. "
            "Use recommended_decision in [allow, review, block] and confidence in [low, medium, high]. "
            "Keep summary under 35 words and each array to at most 3 short strings.\n\n"
            "Previous response:\n"
            f"{prior_response}\n\n"
            "Case snapshot:\n"
            f"{serialized_snapshot}"
        )

    def _generate_structured_response(self, client: Any, contents: str) -> Any:
        from google.genai import types

        return client.models.generate_content(
            model=self.model,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_json_schema=GeminiAdvisoryResult.model_json_schema(),
                temperature=0,
                max_output_tokens=2048,
            ),
        )

    def _parse_response(self, response: Any) -> GeminiAdvisoryResult:
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return GeminiAdvisoryResult.model_validate(parsed)

        response_text = getattr(response, "text", None)
        if not response_text:
            raise GeminiUpstreamError("Gemini returned an empty response.")

        normalized_text = self._extract_json_text(response_text)
        return GeminiAdvisoryResult.model_validate_json(normalized_text)

    def _extract_json_text(self, response_text: str) -> str:
        cleaned = response_text.strip()
        code_fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
        if code_fence_match:
            return code_fence_match.group(1)

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return cleaned[start : end + 1]
        return cleaned

    def _response_preview(self, response_text: Any) -> str:
        if not isinstance(response_text, str) or not response_text.strip():
            return "<empty>"
        compact = response_text.strip().replace("\n", " ")
        return compact[:400]
