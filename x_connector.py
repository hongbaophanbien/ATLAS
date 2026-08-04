from __future__ import annotations

import math
import re
from typing import Iterable

import pandas as pd
import requests


POSITIVE_WORDS = {
    "beat", "beats", "bullish", "breakout", "buy", "upgrade", "upgraded",
    "strong", "growth", "surge", "rally", "rebound", "outperform", "positive",
    "accumulate", "support", "higher", "record", "profit", "profits", "momentum",
    "calls", "call flow", "long", "reclaim", "bounced", "squeeze", "winner",
    "tăng", "mua", "tích cực", "bứt phá", "hồi phục", "mạnh", "vượt", "tăng trưởng",
}
NEGATIVE_WORDS = {
    "miss", "misses", "bearish", "breakdown", "sell", "downgrade", "downgraded",
    "weak", "decline", "drop", "dump", "underperform", "negative", "distribution",
    "resistance", "lower", "loss", "losses", "puts", "put flow", "short", "reject",
    "rejected", "fraud", "warning", "risk", "overvalued", "selloff",
    "giảm", "bán", "tiêu cực", "gãy", "yếu", "rủi ro", "bán tháo", "kháng cự",
}


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZÀ-ỹ0-9$%'-]+", str(text).lower())


def score_text(text: str) -> dict:
    tokens = _tokens(text)
    if not tokens:
        return {"score": 0.0, "positive": 0, "negative": 0, "label": "Neutral"}

    joined = " ".join(tokens)
    positive = sum(1 for word in POSITIVE_WORDS if word in joined)
    negative = sum(1 for word in NEGATIVE_WORDS if word in joined)
    raw = positive - negative
    score = max(-100.0, min(100.0, raw / max(positive + negative, 1) * 100.0))

    if score >= 20:
        label = "Bullish"
    elif score <= -20:
        label = "Bearish"
    else:
        label = "Neutral"

    return {
        "score": round(score, 1),
        "positive": positive,
        "negative": negative,
        "label": label,
    }


def analyze_manual_posts(text: str) -> tuple[pd.DataFrame, dict]:
    blocks = [item.strip() for item in re.split(r"\n\s*\n|\n[-•]\s*", str(text)) if item.strip()]
    if not blocks:
        return pd.DataFrame(), {
            "Sentiment Score": 0.0,
            "Bullish Posts": 0,
            "Bearish Posts": 0,
            "Neutral Posts": 0,
            "Posts": 0,
            "Confidence": 0.0,
        }

    rows = []
    for index, block in enumerate(blocks, start=1):
        result = score_text(block)
        rows.append({
            "Post": index,
            "Text": block[:500],
            "Sentiment": result["label"],
            "Score": result["score"],
        })
    df = pd.DataFrame(rows)
    return df, summarize_sentiment(df)


def summarize_sentiment(df: pd.DataFrame) -> dict:
    if df is None or df.empty:
        return {
            "Sentiment Score": 0.0,
            "Bullish Posts": 0,
            "Bearish Posts": 0,
            "Neutral Posts": 0,
            "Posts": 0,
            "Confidence": 0.0,
        }

    score = float(pd.to_numeric(df["Score"], errors="coerce").fillna(0).mean())
    labels = df["Sentiment"].astype(str)
    count = len(df)
    non_neutral = int((labels != "Neutral").sum())
    confidence = min(100.0, 20.0 + count * 2.5 + non_neutral * 1.5)
    return {
        "Sentiment Score": round(score, 1),
        "Bullish Posts": int((labels == "Bullish").sum()),
        "Bearish Posts": int((labels == "Bearish").sum()),
        "Neutral Posts": int((labels == "Neutral").sum()),
        "Posts": count,
        "Confidence": round(confidence, 1),
    }


def search_recent_posts(
    ticker: str,
    bearer_token: str,
    max_results: int = 50,
    language: str = "en",
) -> tuple[pd.DataFrame, dict, str]:
    """
    Official X API v2 recent search.
    Token is used only for this request and is not stored by this module.
    """
    token = str(bearer_token or "").strip()
    if not token:
        return pd.DataFrame(), {}, "Bearer Token trống."

    symbol = re.sub(r"[^A-Za-z0-9._-]", "", str(ticker).upper())
    if not symbol:
        return pd.DataFrame(), {}, "Ticker không hợp lệ."

    query = f'(${symbol} OR "{symbol}") -is:retweet'
    if language and language.lower() != "all":
        query += f" lang:{language.lower()}"

    params = {
        "query": query,
        "max_results": max(10, min(int(max_results), 100)),
        "tweet.fields": "created_at,public_metrics,lang,author_id",
    }
    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            "https://api.x.com/2/tweets/search/recent",
            params=params,
            headers=headers,
            timeout=20,
        )
        if response.status_code == 429:
            return pd.DataFrame(), {}, "X API rate limit/credit limit (HTTP 429)."
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return pd.DataFrame(), {}, f"{type(exc).__name__}: {exc}"

    posts = payload.get("data") or []
    rows = []
    for post in posts:
        text = str(post.get("text", ""))
        sentiment = score_text(text)
        metrics = post.get("public_metrics") or {}
        engagement = (
            float(metrics.get("like_count", 0))
            + 2.0 * float(metrics.get("retweet_count", 0))
            + 1.5 * float(metrics.get("reply_count", 0))
            + float(metrics.get("quote_count", 0))
        )
        weight = 1.0 + min(engagement, 1000.0) ** 0.5 / 10.0
        rows.append({
            "Created": post.get("created_at"),
            "Text": text,
            "Sentiment": sentiment["label"],
            "Score": sentiment["score"],
            "Engagement": engagement,
            "Weight": weight,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, summarize_sentiment(df), "Không tìm thấy bài phù hợp."

    weighted_score = float((df["Score"] * df["Weight"]).sum() / df["Weight"].sum())
    summary = summarize_sentiment(df)
    summary["Sentiment Score"] = round(weighted_score, 1)
    return df, summary, f"Đã tải {len(df)} bài X công khai trong recent search."
