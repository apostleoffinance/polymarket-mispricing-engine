"""Propose candidate market relationships (rules first; LLM optional)."""

from __future__ import annotations

import re
from collections import defaultdict

from models import MarketNode, RelationshipCandidate
from config import (
    CANDIDATE_MAX_PER_MARKET,
    CANDIDATE_MAX_PROPOSALS,
    CANDIDATE_TOKEN_MIN_OVERLAP,
)

_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "of",
        "to",
        "in",
        "on",
        "for",
        "by",
        "at",
        "from",
        "with",
        "will",
        "be",
        "is",
        "are",
        "was",
        "were",
        "been",
        "being",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "as",
        "if",
        "than",
        "then",
        "into",
        "over",
        "under",
        "before",
        "after",
        "above",
        "below",
        "between",
        "about",
        "against",
        "during",
        "without",
        "within",
        "through",
        "vs",
        "versus",
        "yes",
        "no",
        "market",
        "price",
        "end",
        "year",
        "month",
        "week",
        "day",
        "2024",
        "2025",
        "2026",
        "2027",
        "2028",
    }
)

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def extract_tokens(question: str) -> set[str]:
    tokens = set(_TOKEN_RE.findall((question or "").lower()))
    return {token for token in tokens if len(token) >= 3 and token not in _STOPWORDS}


def _pair_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def propose_token_overlap_candidates(
    markets: list[MarketNode],
    *,
    existing_pairs: set[tuple[str, str]] | None = None,
    min_overlap: int = CANDIDATE_TOKEN_MIN_OVERLAP,
    max_per_market: int = CANDIDATE_MAX_PER_MARKET,
    max_proposals: int = CANDIDATE_MAX_PROPOSALS,
) -> list[RelationshipCandidate]:
    """
    Rule-based candidates from shared question tokens.

    Prefers cross-domain pairs (within-domain pairs are already scanned
    by discovery), but still proposes within-domain overlaps that may
    have been truncated by MAX_EDGES_PER_DOMAIN.
    """
    existing = existing_pairs or set()
    tokens_by_id = {market.id: extract_tokens(market.question) for market in markets}
    market_by_id = {market.id: market for market in markets}

    inverted: dict[str, list[str]] = defaultdict(list)
    for market_id, tokens in tokens_by_id.items():
        for token in tokens:
            inverted[token].append(market_id)

    scored: dict[tuple[str, str], tuple[int, set[str]]] = {}
    for token, ids in inverted.items():
        if len(ids) < 2 or len(ids) > 80:
            continue
        for i, left_id in enumerate(ids):
            for right_id in ids[i + 1 :]:
                key = _pair_key(left_id, right_id)
                if key in existing:
                    continue
                overlap = tokens_by_id[left_id] & tokens_by_id[right_id]
                if len(overlap) < min_overlap:
                    continue
                prev = scored.get(key)
                if prev is None or len(overlap) > prev[0]:
                    scored[key] = (len(overlap), overlap)

    ranked = sorted(scored.items(), key=lambda item: item[1][0], reverse=True)
    per_market: dict[str, int] = defaultdict(int)
    candidates: list[RelationshipCandidate] = []

    for (left_id, right_id), (overlap_n, overlap_tokens) in ranked:
        if len(candidates) >= max_proposals:
            break
        if per_market[left_id] >= max_per_market or per_market[right_id] >= max_per_market:
            continue

        left = market_by_id[left_id]
        right = market_by_id[right_id]
        parent, child = (
            (left, right) if left.volume >= right.volume else (right, left)
        )
        shared = ", ".join(sorted(overlap_tokens)[:8])
        cross = parent.domain != child.domain
        rationale = (
            f"{'Cross-domain' if cross else 'Within-domain'} token overlap "
            f"({overlap_n}): {shared}"
        )
        confidence = min(1.0, 0.35 + (0.1 * overlap_n) + (0.15 if cross else 0.0))

        candidates.append(
            RelationshipCandidate(
                parent_id=parent.id,
                child_id=child.id,
                parent_question=parent.question,
                child_question=child.question,
                parent_domain=parent.domain,
                child_domain=child.domain,
                source="token_overlap",
                rationale=rationale,
                confidence=confidence,
            )
        )
        per_market[left_id] += 1
        per_market[right_id] += 1

    return candidates
