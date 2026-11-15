"""Immutable provenance for a completed translation and its cached value."""
from dataclasses import dataclass


@dataclass(frozen=True,slots=True)
class TranslationInfo:
    source: str
    elapsed_ms: float
    device: str | None = None
    profile_kind: str | None = None
    match_percent: float | None = None
    cached: bool = False
    fallback: bool | None = None


@dataclass(frozen=True,slots=True)
class CachedTranslation:
    text: str
    info: TranslationInfo
