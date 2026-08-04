from __future__ import annotations
import json, os, math
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import requests

def _secret(name: str) -> str:
    try:
        import streamlit as st
        value = st.secrets.get(name, "")
        if value: return str(value)
    except Exception:
        pass
    return str(os.getenv(name, ""))

def configured() -> bool:
    return bool(_secret("SUPABASE_URL") and _secret("SUPABASE_KEY"))


def write_configured() -> bool:
    return bool(
        _secret("SUPABASE_URL")
        and (_secret("SUPABASE_WRITE_KEY") or _secret("SUPABASE_KEY"))
    )

def _endpoint() -> str:
    return _secret("SUPABASE_URL").rstrip("/") + "/rest/v1/atlas_snapshots"

def _headers(prefer=None, key=None) -> dict:
    key = str(key or _secret("SUPABASE_KEY")).strip()
    h = {
        "apikey": key,
        "Content-Type": "application/json",
    }

    # Legacy Supabase anon/service-role JWT keys begin with "eyJ".
    # New sb_publishable_/sb_secret_ keys authenticate through apikey.
    if key.startswith("eyJ"):
        h["Authorization"] = f"Bearer {key}"

    if prefer:
        h["Prefer"] = prefer
    return h


def _json_safe(value):
    """Convert pandas/numpy values to strict JSON-compatible values."""
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    try:
        if pd.isna(value):
            return None
    except Exception:
        pass
    if isinstance(value, (str, int, bool)):
        return value
    return str(value)


def save_snapshot(payload: dict, snapshot_id: str = "latest") -> None:
    if not configured():
        raise RuntimeError("SUPABASE_URL/SUPABASE_KEY chưa cấu hình")

    body = {
        "id": str(snapshot_id),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "payload": _json_safe(payload),
    }
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )
    response = requests.post(
        _endpoint(),
        params={"on_conflict": "id"},
        headers=_headers("resolution=merge-duplicates,return=minimal"),
        data=encoded,
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(
            f"Supabase snapshot save failed ({response.status_code}): "
            f"{response.text[:1200]}"
        )

def load_snapshot(snapshot_id: str = "latest") -> dict:
    if not configured(): return {}
    r=requests.get(_endpoint(),params={"id":f"eq.{snapshot_id}","select":"updated_at,payload","limit":"1"},headers=_headers(),timeout=20)
    r.raise_for_status(); rows=r.json()
    if not rows: return {}
    payload=rows[0].get("payload") or {}; payload["_snapshot_updated_at"]=rows[0].get("updated_at")
    return payload

def frame_to_records(frame: pd.DataFrame):
    if frame is None or frame.empty: return []
    clean=frame.where(pd.notna(frame),None)
    return clean.to_dict(orient="records")

def records_to_frame(records):
    return pd.DataFrame(records or [])


def _write_key() -> str:
    return _secret("SUPABASE_WRITE_KEY") or _secret("SUPABASE_KEY")


def settings_configured() -> bool:
    return bool(_secret("SUPABASE_URL") and _write_key())


def _settings_endpoint() -> str:
    return _secret("SUPABASE_URL").rstrip("/") + "/rest/v1/atlas_settings"


def save_watchlist_settings(
    watchlist,
    benchmark: str = "QQQ",
    settings_id: str = "default",
) -> dict:
    """
    Best-effort shared settings sync.

    Returns a small status dictionary instead of crashing the app when the
    publishable key cannot write because of RLS or insufficient privileges.
    """
    if not write_configured():
        return {
            "ok": False,
            "synced": False,
            "reason": "SUPABASE_WRITE_KEY chưa cấu hình",
        }

    key = _write_key()
    body = {
        "id": settings_id,
        "watchlist": list(watchlist or []),
        "benchmark": str(benchmark or "QQQ"),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    headers = _headers(
        "resolution=merge-duplicates,return=minimal",
        key=key,
    )

    try:
        response = requests.post(
            _settings_endpoint(),
            params={"on_conflict": "id"},
            headers=headers,
            data=json.dumps(body),
            timeout=30,
        )

        if response.status_code in (401, 403):
            return {
                "ok": False,
                "synced": False,
                "status_code": response.status_code,
                "reason": (
                    "Supabase không cho phép ghi atlas_settings. "
                    "Watchlist vẫn được lưu local/URL."
                ),
            }

        response.raise_for_status()
        return {
            "ok": True,
            "synced": True,
            "status_code": response.status_code,
        }

    except requests.RequestException as exc:
        return {
            "ok": False,
            "synced": False,
            "reason": str(exc),
        }

def load_watchlist_settings(settings_id: str = "default") -> dict:
    if not configured():
        return {}

    response = requests.get(
        _settings_endpoint(),
        params={
            "id": f"eq.{settings_id}",
            "select": "updated_at,watchlist,benchmark",
            "limit": "1",
        },
        headers=_headers(),
        timeout=20,
    )
    response.raise_for_status()
    rows = response.json()
    return rows[0] if rows else {}
