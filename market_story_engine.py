from __future__ import annotations

import pandas as pd

from core import safe_float


def build_market_narrative(scan: pd.DataFrame, rotation: pd.DataFrame) -> str:
    if scan is None or scan.empty:
        return "Chưa đủ dữ liệu để kể câu chuyện thị trường."

    breadth = float((scan["1D %"] > 0).mean() * 100) if "1D %" in scan.columns else 50.0
    best = scan.sort_values(["Net Flow", "Trade Score"], ascending=False).head(3)
    weak = scan.sort_values(["Net Flow", "Trade Score"]).head(3)

    parts = [
        f"Breadth hiện khoảng {breadth:.0f}%.",
        "Các mã có dòng tiền tốt nhất: " + ", ".join(best["Ticker"].astype(str).tolist()) + ".",
        "Các mã yếu nhất: " + ", ".join(weak["Ticker"].astype(str).tolist()) + ".",
    ]

    if rotation is not None and not rotation.empty:
        strongest = rotation.iloc[0]
        weakest = rotation.iloc[-1]
        parts.append(
            f"Dòng tiền đang ưu tiên {strongest['Theme']} "
            f"(Rotation {safe_float(strongest['Rotation']):+.1f}) "
            f"và rút khỏi {weakest['Theme']} "
            f"({safe_float(weakest['Rotation']):+.1f})."
        )

    return " ".join(parts)
