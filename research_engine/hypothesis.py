"""Optional LLM relationship hypothesis agent (candidates only).

Tries providers in HYPOTHESIS_LLM_PROVIDERS order (default: openai → gemini).
Never writes the live graph — callers must validate statistically first.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from config import (
    HYPOTHESIS_GEMINI_MODEL,
    HYPOTHESIS_LLM_ENABLED,
    HYPOTHESIS_LLM_MAX_MARKETS,
    HYPOTHESIS_LLM_MAX_SUGGESTIONS,
    HYPOTHESIS_LLM_PROVIDERS,
    HYPOTHESIS_OPENAI_MODEL,
)
from models import MarketNode, RelationshipCandidate

_SYSTEM_PROMPT = (
    "You are a senior quantitative researcher mapping a prediction-market "
    "knowledge graph. Your job is to propose the best-fit parent→child "
    "relationships for correlation and informational lead/lag — not to trade. "
    "Return JSON only. Never invent market ids."
)


def _available_providers() -> list[str]:
    if not HYPOTHESIS_LLM_ENABLED:
        return []

    available: list[str] = []
    for name in HYPOTHESIS_LLM_PROVIDERS:
        key = name.strip().lower()
        if key == "openai" and os.getenv("OPENAI_API_KEY"):
            available.append("openai")
        elif key == "gemini" and os.getenv("GEMINI_API_KEY"):
            available.append("gemini")
    return available


def propose_llm_hypotheses(
    markets: list[MarketNode],
    *,
    existing_pairs: set[tuple[str, str]] | None = None,
    connected_market_ids: set[str] | None = None,
    max_markets: int = HYPOTHESIS_LLM_MAX_MARKETS,
    max_suggestions: int = HYPOTHESIS_LLM_MAX_SUGGESTIONS,
) -> list[RelationshipCandidate]:
    """
    Ask an LLM for best-fit semantic / causal relationship hypotheses.

    Focuses on under-connected markets and cross-domain links. Soft-fails
    to [] if every provider errors — token-overlap candidates still run.
    """
    providers = _available_providers()
    if not providers:
        return []

    existing = existing_pairs or set()
    connected = connected_market_ids or set()
    ranked = sorted(markets, key=lambda m: m.volume, reverse=True)
    orphans = [m for m in ranked if m.id not in connected]
    focus = (orphans + ranked)[:max_markets]
    # Deduplicate while preserving order.
    seen_ids: set[str] = set()
    focus_markets: list[MarketNode] = []
    for market in focus:
        if market.id in seen_ids:
            continue
        seen_ids.add(market.id)
        focus_markets.append(market)
        if len(focus_markets) >= max_markets:
            break

    if len(focus_markets) < 2:
        return []

    catalog = [
        {
            "id": market.id,
            "domain": market.domain,
            "question": market.question[:180],
            "has_existing_edges": market.id in connected,
            "volume": float(market.volume),
        }
        for market in focus_markets
    ]
    prompt = {
        "task": (
            "Map the best-fit parent→child relationships for a correlation "
            "graph. Prefer: (1) under-connected markets, (2) cross-domain "
            "links with a clear informational channel, (3) pairs where the "
            "parent is likely to lead the child. Avoid trivial duplicates of "
            "already-linked pairs. Do not invent market ids."
        ),
        "markets": catalog,
        "already_linked_pair_count": len(existing),
        "max_suggestions": max_suggestions,
        "output_schema": {
            "suggestions": [
                {
                    "parent_id": "market id",
                    "child_id": "market id",
                    "rationale": "why this is a best-fit correlation / lead-lag link",
                    "confidence": 0.0,
                    "expected_sign": "positive|negative",
                    "expected_lag_hours": 0,
                }
            ]
        },
    }

    payload: dict[str, Any] | None = None
    used_provider: str | None = None
    errors: list[str] = []

    for provider in providers:
        try:
            if provider == "openai":
                payload = _call_openai(prompt)
            elif provider == "gemini":
                payload = _call_gemini(prompt)
            else:
                continue
            used_provider = provider
            break
        except Exception as exc:  # noqa: BLE001 — try next provider
            errors.append(f"{provider}: {exc}")
            print(f"Hypothesis LLM {provider} failed: {exc}")

    if payload is None or used_provider is None:
        if errors:
            print(f"Hypothesis LLM skipped (all providers failed): {'; '.join(errors)}")
        return []

    print(f"Hypothesis LLM used provider: {used_provider}")
    source = f"llm_{used_provider}"

    by_id = {market.id: market for market in focus_markets}
    candidates: list[RelationshipCandidate] = []
    seen: set[tuple[str, str]] = set()

    for item in payload.get("suggestions", []):
        parent_id = str(item.get("parent_id", ""))
        child_id = str(item.get("child_id", ""))
        if parent_id not in by_id or child_id not in by_id or parent_id == child_id:
            continue
        key = (parent_id, child_id) if parent_id < child_id else (child_id, parent_id)
        if key in existing or key in seen:
            continue
        seen.add(key)

        parent = by_id[parent_id]
        child = by_id[child_id]
        confidence = float(item.get("confidence") or 0.5)
        confidence = max(0.0, min(1.0, confidence))
        expected_sign = str(item.get("expected_sign") or "").strip().lower()
        lag_hours = item.get("expected_lag_hours")
        rationale = str(item.get("rationale") or "LLM best-fit hypothesis").strip()
        extras = []
        if expected_sign in {"positive", "negative"}:
            extras.append(f"sign={expected_sign}")
        if lag_hours is not None:
            try:
                extras.append(f"lag≈{float(lag_hours):.0f}h")
            except (TypeError, ValueError):
                pass
        if extras:
            rationale = f"{rationale} [{', '.join(extras)}]"

        candidates.append(
            RelationshipCandidate(
                parent_id=parent.id,
                child_id=child.id,
                parent_question=parent.question,
                child_question=child.question,
                parent_domain=parent.domain,
                child_domain=child.domain,
                source=source,
                rationale=rationale[:500],
                confidence=confidence,
            )
        )
        if len(candidates) >= max_suggestions:
            break

    return candidates


def _call_openai(prompt: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ["OPENAI_API_KEY"]
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    response = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": HYPOTHESIS_OPENAI_MODEL,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(prompt)},
            ],
        },
        timeout=60,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return _parse_json_content(content)


def _call_gemini(prompt: dict[str, Any]) -> dict[str, Any]:
    api_key = os.environ["GEMINI_API_KEY"]
    model = HYPOTHESIS_GEMINI_MODEL
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    response = requests.post(
        url,
        params={"key": api_key},
        headers={"Content-Type": "application/json"},
        json={
            "system_instruction": {"parts": [{"text": _SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": json.dumps(prompt)}],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        },
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    parts = data["candidates"][0]["content"]["parts"]
    content = "".join(part.get("text", "") for part in parts)
    return _parse_json_content(content)


def _parse_json_content(content: str) -> dict[str, Any]:
    text = (content or "").strip()
    if not text:
        raise ValueError("empty LLM response")

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))

    if not isinstance(parsed, dict):
        raise ValueError("LLM JSON root must be an object")
    if "suggestions" not in parsed:
        parsed = {"suggestions": parsed if isinstance(parsed, list) else []}
    return parsed
