"""Normalizes raw transcript text by removing filler words and collapsing whitespace."""

import re

FILLER_PATTERN = re.compile(r"\b(um|uh|like|you know|yeah|right)\b", re.IGNORECASE)
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_transcript(raw: str) -> str:
    """Remove filler words, collapse whitespace, and strip the transcript."""
    text = FILLER_PATTERN.sub("", raw)
    text = WHITESPACE_PATTERN.sub(" ", text)
    text = text.strip()
    return text
