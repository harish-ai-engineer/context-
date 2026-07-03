"""Extractive summarization — the offline baseline of the AI Understanding layer.

Frequency-scored sentence extraction: no models, no keys, deterministic. Swap
in an LLM-backed summarizer through the same function signature when quality
matters more than portability.
"""

from __future__ import annotations

import re
from collections import Counter

from ..core.model import Document

_SENTENCE = re.compile(r"(?<=[.!?])\s+")
_WORD = re.compile(r"[a-z0-9']+")

# Minimal english stopword list — enough to stop glue words dominating scores.
_STOPWORDS = frozenset(
    "a an and are as at be but by for from has have if in into is it its of on or "
    "that the their this to was were will with we you your not can may our i".split()
)


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE.split(text) if s.strip()]


def summarize(source: Document | str, max_sentences: int = 3) -> str:
    """Return the ``max_sentences`` highest-signal sentences, in original order."""
    text = source.to_text() if isinstance(source, Document) else source
    sentences = _sentences(" ".join(text.split()))
    if len(sentences) <= max_sentences:
        return " ".join(sentences)

    freq = Counter(
        w for w in _WORD.findall(text.lower()) if w not in _STOPWORDS and len(w) > 1
    )
    scored: list[tuple[float, int, str]] = []
    for i, sent in enumerate(sentences):
        words = _WORD.findall(sent.lower())
        if not words:
            continue
        score = sum(freq[w] for w in words if w not in _STOPWORDS) / (len(words) + 3)
        scored.append((score, i, sent))

    top = sorted(scored, reverse=True)[:max_sentences]
    top.sort(key=lambda t: t[1])  # restore document order
    return " ".join(sent for _, _, sent in top)
