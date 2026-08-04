from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def data_quality_summary(
    scan: pd.DataFrame,
    opportunities: pd.DataFrame,
    flow_radar: pd.DataFrame,
    failed_count: int,
    requested_count: int,
) -> dict[str, Any]:
    scanned_count = 0 if scan is None else len(scan)
    qualified_count = 0 if opportunities is None else len(opportunities)
    flow_count = 0 if flow_radar is None else len(flow_radar)

    coverage = (
        scanned_count / max(int(requested_count), 1) * 100.0
    )

    required_flow_columns = {"Volume", "OI", "Bid", "Ask", "Flow Score"}
    flow_complete = bool(
        flow_count > 0
        and required_flow_columns.issubset(set(flow_radar.columns))
    )

    if scanned_count == 0:
        status = "FAILED"
        message = "Không quét được mã nào."
    elif coverage < 60:
        status = "DEGRADED"
        message = f"Coverage thấp: {coverage:.1f}%."
    elif flow_count == 0:
        status = "DEGRADED"
        message = "Technical scan có dữ liệu nhưng Flow Radar đang rỗng."
    elif not flow_complete:
        status = "DEGRADED"
        message = "Flow Radar thiếu Volume/OI/Bid/Ask."
    else:
        status = "READY"
        message = "Technical, Flow và snapshot đều có dữ liệu."

    return {
        "status": status,
        "message": message,
        "requested_count": int(requested_count),
        "scanned_count": int(scanned_count),
        "qualified_count": int(qualified_count),
        "flow_contract_count": int(flow_count),
        "failed_count": int(failed_count),
        "coverage_pct": round(coverage, 1),
        "flow_complete": flow_complete,
    }


def snapshot_freshness(updated_at: str | None, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)

    if not updated_at:
        return {
            "status": "UNKNOWN",
            "age_minutes": None,
            "message": "Không có thời gian snapshot.",
        }

    try:
        value = str(updated_at).replace("Z", "+00:00")
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        age = max(0.0, (now - stamp.astimezone(timezone.utc)).total_seconds() / 60.0)
    except Exception:
        return {
            "status": "UNKNOWN",
            "age_minutes": None,
            "message": "Không đọc được thời gian snapshot.",
        }

    if age <= 8:
        status = "FRESH"
    elif age <= 15:
        status = "DELAYED"
    else:
        status = "STALE"

    return {
        "status": status,
        "age_minutes": round(age, 1),
        "message": f"Snapshot {age:.1f} phút tuổi.",
    }
