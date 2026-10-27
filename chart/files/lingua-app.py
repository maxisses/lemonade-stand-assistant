import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, HTTPException
from fast_langdetect import detect as fast_detect
from lingua import Language, LanguageDetectorBuilder
from pydantic import BaseModel, Field

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))
logger = logging.getLogger(__name__)

TARGET_LANGUAGE_NAME = os.getenv("TARGET_LANGUAGE", "ENGLISH").upper()
TARGET_LANGUAGE = getattr(Language, TARGET_LANGUAGE_NAME, Language.ENGLISH)
TARGET_LANG_CODE = TARGET_LANGUAGE.iso_code_639_1.name.lower()

EXCLUDED_LANGUAGES = [
    Language.SHONA,
    Language.XHOSA,
    Language.SOTHO,
    Language.TSONGA,
    Language.TSWANA,
    Language.GANDA,
    Language.LATIN,
    Language.ESPERANTO,
]

supported_languages = [lang for lang in Language.all() if lang not in EXCLUDED_LANGUAGES]
detector = (
    LanguageDetectorBuilder
    .from_languages(*supported_languages)
    .with_preloaded_language_models()
    .build()
)

MIN_CONFIDENCE_THRESHOLD = 0.15
MIN_CONFIDENCE_RATIO = 2.5


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Warming up language detection models for target language: %s", TARGET_LANGUAGE.name)
    if TARGET_LANGUAGE == Language.SPANISH:
        sample = "hola"
    elif TARGET_LANGUAGE == Language.PORTUGUESE:
        sample = "olá"
    else:
        sample = "hello"
    fast_detect(sample, k=1)
    detector.detect_language_of(sample)
    logger.info("Models loaded, ready to accept requests")
    yield


app = FastAPI(title="Lingua Language Detector", lifespan=lifespan)


class ContentAnalysisHttpRequest(BaseModel):
    contents: List[str] = Field(min_length=1)
    detector_params: Optional[Dict[str, Any]] = None


class ContentAnalysisResponse(BaseModel):
    start: int
    end: int
    text: str
    detection: str
    detection_type: str
    score: float
    evidences: List[Any] = []
    metadata: Dict[str, Any] = {}


def _target_confidence(text: str) -> float:
    try:
        lingua_conf = detector.compute_language_confidence_values(text)
        for confidence in lingua_conf:
            if hasattr(confidence, "language") and hasattr(confidence, "value"):
                if confidence.language == TARGET_LANGUAGE:
                    return confidence.value
    except Exception as exc:
        logger.error("Lingua confidence calculation failed")
        raise RuntimeError("Language detector unavailable") from exc
    return 0.5


def _fast_target_confidence(text: str) -> float:
    try:
        for result in fast_detect(text, k=10):
            if result.get("lang") == TARGET_LANG_CODE:
                return result.get("score", 0)
    except Exception as exc:
        logger.error("Fast language detection failed")
        raise RuntimeError("Language detector unavailable") from exc
    return 0.5


def _build_detection(text: str, score: float, detected_lang: Optional[Language], target_confidence: float) -> List[ContentAnalysisResponse]:
    return [ContentAnalysisResponse(
        start=0,
        end=len(text),
        text=text,
        detection="non_target_language",
        detection_type="language_detection",
        score=score,
        evidences=[],
        metadata={
            "detected_language": detected_lang.name if detected_lang else "UNKNOWN",
            "target_language": TARGET_LANGUAGE.name,
            "target_confidence": target_confidence,
        },
    )]


def detect_language(text: str) -> List[ContentAnalysisResponse]:
    """Return detections when text is not in the configured target language."""
    try:
        if not text or not text.strip():
            return []

        words = re.findall(r"\b\w+\b", text)
        if len(words) == 1:
            word = words[0]
            avg_target_prob = (_target_confidence(word) + _fast_target_confidence(word)) / 2
            if avg_target_prob >= 0.1:
                return []

            try:
                detected_lang = detector.detect_language_of(text)
            except Exception as exc:
                raise RuntimeError("Language detector unavailable") from exc

            if detected_lang is None or detected_lang == TARGET_LANGUAGE:
                return []

            return _build_detection(text, 1.0 - avg_target_prob, detected_lang, avg_target_prob)

        try:
            detected_lang = detector.detect_language_of(text)
        except Exception as exc:
            raise RuntimeError("Language detector unavailable") from exc

        if detected_lang is None or detected_lang == TARGET_LANGUAGE:
            return []

        try:
            detected_confidence = detector.compute_language_confidence(text, detected_lang)
            target_confidence = detector.compute_language_confidence(text, TARGET_LANGUAGE)
        except Exception as exc:
            raise RuntimeError("Language confidence calculation failed") from exc

        if detected_confidence < MIN_CONFIDENCE_THRESHOLD:
            return []

        if target_confidence > 0 and detected_confidence < (target_confidence * MIN_CONFIDENCE_RATIO):
            return []

        return _build_detection(text, 1.0 - target_confidence, detected_lang, target_confidence)
    except Exception as exc:
        logger.error("Language validation failed")
        raise RuntimeError("Language detector unavailable") from exc


@app.get("/health")
def health():
    return "ok"


@app.post("/api/v1/text/contents", response_model=List[List[ContentAnalysisResponse]])
async def analyze_contents(request: ContentAnalysisHttpRequest):
    tasks = [asyncio.to_thread(detect_language, content) for content in request.contents]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error("Language detector request failed")
            raise HTTPException(status_code=503, detail="Language detector unavailable")
        else:
            processed_results.append(result)

    return processed_results


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def catch_all(path: str, request: Request):
    body = await request.body()
    logger.warning("Unhandled route: %s /%s - body: %s", request.method, path, body)
    return {"error": f"Unknown endpoint: /{path}"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
