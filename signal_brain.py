from __future__ import annotations

import html
from typing import Any

from core import safe_float


def _label_trend(score: float) -> tuple[str, str]:
    if score >= 68:
        return "BULLISH", "good"
    if score <= 38:
        return "BEARISH", "bad"
    return "NEUTRAL", "wait"


def _label_flow(money_in: float, money_out: float, status: str) -> tuple[str, str]:
    if money_in >= money_out + 10:
        return f"ACCUMULATION — IN {money_in:.0f}", "good"
    if money_out >= money_in + 10:
        return f"DISTRIBUTION — OUT {money_out:.0f}", "bad"
    return f"MIXED — {status}", "wait"


def _verdict(plan: dict, fusion: dict, retest: dict, base: dict, flow: dict) -> dict[str, Any]:
    trend = safe_float(plan.get("Trend Score"), 50)
    entry = safe_float(plan.get("Entry Score"), 50)
    confidence = safe_float(fusion.get("Confidence"), 0)
    money_in = safe_float(flow.get("Money In"), 50)
    money_out = safe_float(flow.get("Money Out"), 50)
    selloff = safe_float(flow.get("Sell-off Risk"), 50)
    pullback = safe_float(base.get("Pullback Risk"), 50)
    action = str(plan.get("Action", "WAIT"))

    if "BUY CALL" in action and confidence >= 60:
        title, tone = "CANH BUY CALL — CHỈ SAU TRIGGER", "good"
    elif "BUY PUT" in action and confidence >= 60:
        title, tone = "CANH BUY PUT — CHỈ SAU BREAKDOWN", "bad"
    else:
        title, tone = "ĐỨNG NGOÀI — CHỜ XÁC NHẬN", "wait"

    checklist = [
        ("Trend đủ mạnh", trend >= 65 or trend <= 38),
        ("Dòng tiền đồng thuận", abs(money_in - money_out) >= 10),
        ("Entry đủ tốt", entry >= 65),
        ("Không quá nóng/quá bán", pullback <= 65 and selloff <= 78),
        ("Confidence ≥ 60%", confidence >= 60),
    ]

    reasons = []
    if money_out > money_in:
        reasons.append(f"Money Out {money_out:.0f} cao hơn Money In {money_in:.0f}")
    else:
        reasons.append(f"Money In {money_in:.0f} cao hơn Money Out {money_out:.0f}")
    reasons.append(f"Trend Score {trend:.0f}/100")
    reasons.append(f"Entry Score {entry:.0f}/100")
    reasons.append(f"Retest state: {retest.get('State', 'N/A')}")
    if selloff >= 65:
        reasons.append("Sell-off risk cao")
    if pullback >= 65:
        reasons.append("Pullback risk cao")

    return {
        "title": title,
        "tone": tone,
        "checklist": checklist,
        "reasons": reasons,
    }


def signal_fusion_html(
    ticker: str,
    plan: dict,
    fusion: dict,
    retest: dict,
    base: dict,
    flow: dict,
) -> str:
    verdict = _verdict(plan, fusion, retest, base, flow)
    trend_score = safe_float(plan.get("Trend Score"), 50)
    entry_score = safe_float(plan.get("Entry Score"), 50)
    confidence = safe_float(fusion.get("Confidence"), 0)
    money_in = safe_float(flow.get("Money In"), 50)
    money_out = safe_float(flow.get("Money Out"), 50)

    trend_label, trend_tone = _label_trend(trend_score)
    flow_label, flow_tone = _label_flow(
        money_in, money_out, str(flow.get("Flow Status", "Neutral"))
    )

    tone_class = verdict["tone"]
    checklist_html = "".join(
        f'<div class="check {"ok" if ok else "no"}">'
        f'<span>{"✓" if ok else "✕"}</span>{html.escape(label)}</div>'
        for label, ok in verdict["checklist"]
    )
    reasons_html = "".join(
        f"<li>{html.escape(reason)}</li>" for reason in verdict["reasons"]
    )

    retest_low = safe_float(retest.get("Retest Zone Low"), 0)
    retest_high = safe_float(retest.get("Retest Zone High"), 0)
    breakout = safe_float(retest.get("Breakout Trigger"), 0)
    breakdown = safe_float(plan.get("TP1"), 0)
    invalidation = safe_float(plan.get("Stop"), 0)

    if "BUY PUT" in str(plan.get("Action", "")):
        action_steps = (
            f"<b>Kế hoạch:</b> Chỉ cân nhắc PUT khi giá mất vùng "
            f"${retest_low:,.2f} và retest thất bại. "
            f"Hủy bearish nếu giá vượt ${invalidation:,.2f}."
        )
    elif "BUY CALL" in str(plan.get("Action", "")):
        action_steps = (
            f"<b>Kế hoạch:</b> Chỉ cân nhắc CALL khi giá giữ vùng "
            f"${retest_low:,.2f}–${retest_high:,.2f} hoặc breakout "
            f"${breakout:,.2f} có xác nhận."
        )
    else:
        action_steps = (
            f"<b>Kế hoạch:</b> Không vào sớm. Chờ giá phản ứng tại "
            f"${retest_low:,.2f}–${retest_high:,.2f}; chỉ đổi bias sau trigger rõ."
        )

    return f"""
<style>
.sf-wrap{{font-family:Arial;color:#f3f5f8;background:#0f151f;border:1px solid #303b4d;border-radius:18px;padding:18px}}
.sf-verdict{{padding:15px 18px;border-radius:13px;font-size:21px;font-weight:900;margin-bottom:14px}}
.sf-verdict.good{{background:#123c2d;color:#8ef0bd}} .sf-verdict.bad{{background:#491d2a;color:#ff9eb3}}
.sf-verdict.wait{{background:#453a19;color:#ffe08a}}
.sf-grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:11px}}
.sf-card{{background:#171f2c;border:1px solid #344053;border-radius:13px;padding:14px}}
.sf-label{{font-size:12px;color:#9eabba;text-transform:uppercase}} .sf-value{{font-size:21px;font-weight:850;margin-top:6px}}
.good-text{{color:#65e6a4}} .bad-text{{color:#ff718f}} .wait-text{{color:#ffd36b}}
.sf-bottom{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:13px}}
.sf-section{{background:#141c27;border:1px solid #303b4d;border-radius:13px;padding:14px;line-height:1.55}}
.check{{display:flex;gap:9px;margin:7px 0}} .check.ok{{color:#72e5a7}} .check.no{{color:#ff829a}}
ul{{margin:8px 0 0 18px;padding:0}}
@media(max-width:700px){{.sf-grid{{grid-template-columns:1fr 1fr}}.sf-bottom{{grid-template-columns:1fr}}}}
</style>
<div class="sf-wrap">
  <div class="sf-verdict {tone_class}">{html.escape(verdict["title"])}</div>
  <div class="sf-grid">
    <div class="sf-card"><div class="sf-label">Ticker</div><div class="sf-value">{html.escape(ticker)}</div></div>
    <div class="sf-card"><div class="sf-label">Trend</div><div class="sf-value {trend_tone}-text">{trend_label}</div></div>
    <div class="sf-card"><div class="sf-label">Entry</div><div class="sf-value">{entry_score:.0f}/100</div></div>
    <div class="sf-card"><div class="sf-label">Confidence</div><div class="sf-value">{confidence:.0f}%</div></div>
    <div class="sf-card"><div class="sf-label">Flow</div><div class="sf-value {flow_tone}-text">{html.escape(flow_label)}</div></div>
    <div class="sf-card"><div class="sf-label">Retest</div><div class="sf-value">{html.escape(str(retest.get("State","N/A")))}</div></div>
    <div class="sf-card"><div class="sf-label">Retest zone</div><div class="sf-value">${retest_low:,.2f}–${retest_high:,.2f}</div></div>
    <div class="sf-card"><div class="sf-label">Trigger</div><div class="sf-value">${breakout:,.2f}</div></div>
  </div>
  <div class="sf-bottom">
    <div class="sf-section"><b>ATLAS Checklist</b>{checklist_html}</div>
    <div class="sf-section"><b>Tại sao?</b><ul>{reasons_html}</ul></div>
  </div>
  <div class="sf-section" style="margin-top:12px">{action_steps}</div>
</div>
"""
