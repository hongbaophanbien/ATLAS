from __future__ import annotations
import html, math
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from atlas_brain import analyze_brain, HORIZON
from core import atr, ema, ensure_ohlcv, safe_float

def technical_bottom(daily):
    data=ensure_ohlcv(daily)
    if len(data)<20:return {}
    price=safe_float(data["Close"].iloc[-1]); a=max(safe_float(atr(data,14).iloc[-1],price*.025),.01)
    e21=safe_float(ema(data["Close"],21).iloc[-1],price); low5=safe_float(data["Low"].tail(5).min(),price); low20=safe_float(data["Low"].tail(20).min(),low5)
    return {"Bottom Low":round(max(.01,min(low20,min(low5,e21)-.45*a)),2),"Bottom High":round(max(.01,min(low5,e21)),2),"Previous Day Low":round(safe_float(data["Low"].iloc[-2],low5),2)}

def build_trade_plan(symbol,daily,row,mtf,horizon,x_sentiment_score=0.0,x_confidence=0.0):
    data=ensure_ohlcv(daily)
    if data.empty or not row:return {}
    price=safe_float(data["Close"].iloc[-1]); brain=analyze_brain(data,row,mtf,horizon); lv=brain["Levels"]; sc=brain["Scenarios"]; bottom=technical_bottom(data)
    a=max(safe_float(lv.get("ATR"),price*.025),.01); e9=safe_float(lv.get("EMA9"),price); e21=safe_float(lv.get("EMA21"),price)
    s1=safe_float(lv.get("Support 1"),min(e9,price-.4*a)); s2=safe_float(lv.get("Support 2"),min(e21,s1-.6*a))
    r1=safe_float(lv.get("Resistance 1"),price+a); r2=safe_float(lv.get("Resistance 2"),r1+a); stretch=safe_float(lv.get("Stretch"),r2+a)
    entry_score=safe_float(brain.get("Entry Score"),50); trend=safe_float(brain.get("Trend Score"),50)
    if entry_score>=70: entry_low=min(s1,e9); entry_high=min(price,max(s1+.25*a,e9+.10*a))
    elif trend>=60: entry_low=min(s2,e21); entry_high=min(s1,e9)
    else: entry_low=s2; entry_high=s1
    if entry_high<entry_low:entry_low,entry_high=entry_high,entry_low
    stop=max(.01,min(safe_float(row.get("Stop"),entry_low-a),s2-.30*a))
    chase=max(entry_high,min(price+.25*a,r1))
    cfg=HORIZON.get(horizon,HORIZON["Ngày mai"])
    money_in=safe_float(row.get("Money In"),50)
    money_out=safe_float(row.get("Money Out"),50)
    selloff=safe_float(row.get("Sell-off Risk"),50)
    bearish = trend<=42 or (money_out>=money_in+10 and selloff>=58)

    if bearish:
        # PUT plan: enter on failed bounce or confirmed breakdown.
        entry_low=max(price,min(r1,price+.20*a))
        entry_high=max(entry_low,r1)
        stop=max(r2,entry_high+.30*a)
        chase=max(.01,s1)  # Do not chase PUT below this support.
        tp1=min(s1,price-.45*a)
        tp2=min(s2,tp1-.55*a)
        stretch=min(bottom.get("Bottom Low",tp2-.80*a),tp2-.60*a)
        mid=(entry_low+entry_high)/2
        risk=max(stop-mid,.55*a)
        rr1=max(mid-tp1,0)/risk
        rr2=max(mid-tp2,0)/risk
        up=min(75,sc["Continuation"]*.45+sc["Shallow Retest"]*.35)
        down=100-up
    else:
        tp1=min(r1,price+cfg["tp1_atr"]*a)
        if tp1<=price+.15*a:tp1=price+.65*cfg["tp1_atr"]*a
        tp2=max(tp1+.55*a,min(r2,stretch))
        stretch=max(stretch,tp2+.60*a)
        mid=(entry_low+entry_high)/2
        risk=max(mid-stop,.55*a)
        rr1=max(tp1-mid,0)/risk
        rr2=max(tp2-mid,0)/risk
        up=min(78,sc["Continuation"]+sc["Shallow Retest"]*.70)
        down=100-up

    conf=min(82,38+abs(up-50)*.65+abs(trend-50)*.20)
    bullish_valid=all([
        not bearish, trend>=62, entry_score>=62, up>=58,
        money_in>=money_out, rr1>=1.0, conf>=58
    ])
    bearish_valid=all([
        bearish, trend<=45, entry_score>=55, down>=58,
        money_out>=money_in, selloff>=55, rr1>=1.0, conf>=58
    ])

    if bullish_valid:
        final_action="CANH BUY CALL — CHỈ SAU TRIGGER"
    elif bearish_valid:
        final_action="CANH BUY PUT — CHỈ SAU BREAKDOWN"
    else:
        final_action="WAIT — CHỜ XÁC NHẬN"

    sj=ZoneInfo("America/Los_Angeles")
    analysis_time=datetime.now(sj)
    validity_days={"Day trade":0,"Ngày mai":1,"Swing 3–5 ngày":5,"Swing 1–2 tuần":14}.get(horizon,1)
    valid_until=analysis_time+timedelta(days=validity_days)

    if bearish:
        plan_a=f"Giá hồi lên ${entry_low:.2f}–${entry_high:.2f} rồi bị từ chối → canh PUT."
        plan_b=f"Thủng ${s1:.2f} và retest thất bại → TP1 ${tp1:.2f}, TP2 ${tp2:.2f}."
        plan_c=f"Vượt ${stop:.2f} → hủy PUT; không short tiếp."
    else:
        plan_a=f"Retest ${entry_low:.2f}–${entry_high:.2f}, giữ hỗ trợ và reclaim EMA/VWAP → canh CALL."
        plan_b=f"Breakout trên ${r1:.2f} với volume xác nhận → TP2 ${tp2:.2f}; Stretch ${stretch:.2f}."
        plan_c=f"Mất ${s2:.2f} và retest thất bại → hủy CALL; chỉ theo dõi PUT."

    reasons=list(brain.get("Entry Reasons",[]))+[
        f"Trend {trend:.0f}/100",f"Entry {entry_score:.0f}/100",
        f"Money In {money_in:.0f} / Money Out {money_out:.0f}"
    ]
    reasons=list(brain.get("Entry Reasons",[]))+[f"Trend {trend:.0f}/100",f"Entry {entry_score:.0f}/100"]
    return {
        "Ticker":symbol,"Horizon":horizon,"Price":round(price,2),"Action":final_action,
        "Analysis Time":analysis_time.strftime("%Y-%m-%d %I:%M:%S %p %Z"),
        "Valid Until":valid_until.strftime("%Y-%m-%d %I:%M %p %Z"),
        "Direction":"PUT" if bearish else "CALL",
        "Bias":"Bullish" if trend>=62 else "Bearish" if trend<=42 else "Neutral",
        "Trend Score":round(trend,1),"Entry Score":round(entry_score,1),"Entry Label":brain["Entry Label"],
        **bottom,"Entry Low":round(entry_low,2),"Entry High":round(entry_high,2),"Chase Limit":round(chase,2),"Stop":round(stop,2),
        "TP1":round(tp1,2),"TP2":round(tp2,2),"Stretch Target":round(stretch,2),
        "Sell Zone Low":round(max(tp1-.12*a,entry_high),2),"Sell Zone High":round(tp2+.10*a,2),
        "Up Probability":round(up,1),"Down Probability":round(down,1),"Confidence":round(conf,1),
        "RR TP1":round(rr1,2),"RR TP2":round(rr2,2),"Scenarios":sc,
        "Plan A":plan_a,
        "Plan B":plan_b,
        "Plan C":plan_c,
        "Reasons":reasons,
    }

def trade_plan_html(plan):
    if not plan:return "<div>Không đủ dữ liệu.</div>"
    def money(k):
        v=safe_float(plan.get(k),np.nan)
        return "N/A" if not math.isfinite(v) else f"${v:,.2f}"
    sc=plan.get("Scenarios",{}); reasons=" • ".join(html.escape(str(x)) for x in plan.get("Reasons",[]))
    is_put=str(plan.get("Direction"))=="PUT"
    entry_label="Vùng canh PUT" if is_put else "Vùng canh CALL"
    chase_label="Không chase PUT dưới" if is_put else "Không chase CALL trên"
    tp1_label="TP1 giảm" if is_put else "TP1 gần"
    tp2_label="TP2 giảm" if is_put else "TP2 breakout"
    stretch_label="Target sâu" if is_put else "Stretch"
    return f"""
<style>
.atlas{{border:1px solid rgba(130,140,160,.35);border-radius:16px;padding:18px;background:#111722;color:#f2f4f8;font-family:Arial}}
.head{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}.title{{font-size:27px;font-weight:800}}.action{{padding:9px 12px;border-radius:10px;background:rgba(80,140,255,.18);font-weight:700}}
.scores,.grid,.scenarios{{display:grid;gap:10px;margin-top:14px}}.scores{{grid-template-columns:repeat(2,minmax(0,1fr))}}.grid{{grid-template-columns:repeat(4,minmax(0,1fr))}}.scenarios{{grid-template-columns:repeat(4,minmax(0,1fr))}}
.box{{padding:11px;border-radius:11px;background:rgba(255,255,255,.055);border:1px solid rgba(255,255,255,.08)}}.label{{font-size:12px;color:#aeb8c8;text-transform:uppercase}}.value{{font-size:20px;font-weight:800;margin-top:5px}}
.bar{{height:10px;border-radius:10px;background:#263041;overflow:hidden;margin-top:7px}}.fill{{height:100%;background:#5b8cff}}.plans{{margin-top:16px;display:grid;gap:10px}}.plan-line{{padding:13px 14px;border-radius:11px;background:rgba(91,140,255,.12);border:1px solid rgba(91,140,255,.45);line-height:1.55;color:#f2f5fb}}.plan-line b{{color:#8fb2ff;font-size:15px}}.note{{margin-top:12px;padding:12px 14px;border-radius:11px;background:rgba(255,255,255,.05);border-left:4px solid #5b8cff;color:#d4dbea;font-size:13px;line-height:1.55}}
@media(max-width:900px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}@media(max-width:600px){{.scores,.grid,.scenarios{{grid-template-columns:1fr}}.atlas{{padding:12px}}.title{{font-size:22px}}.value{{font-size:18px}}}}
</style>
<div class="atlas">
<div class="head"><div><div class="title">{plan.get('Ticker')} — {plan.get('Horizon')}</div><div style="color:#aeb8c8;margin-top:5px">Phân tích {plan.get('Analysis Time')} • Hiệu lực đến {plan.get('Valid Until')}</div><div style="color:#aeb8c8;margin-top:5px">Giá {money('Price')} • {plan.get('Bias')} • Confidence {safe_float(plan.get('Confidence')):.0f}%</div></div><div class="action">{plan.get('Action')}</div></div>
<div class="scores">
<div class="box"><div class="label">Trend Score</div><div class="value">{safe_float(plan.get('Trend Score')):.0f}/100</div><div class="bar"><div class="fill" style="width:{safe_float(plan.get('Trend Score')):.0f}%"></div></div></div>
<div class="box"><div class="label">Entry Score — {plan.get('Entry Label')}</div><div class="value">{safe_float(plan.get('Entry Score')):.0f}/100</div><div class="bar"><div class="fill" style="width:{safe_float(plan.get('Entry Score')):.0f}%"></div></div></div>
</div>
<div class="grid">
<div class="box"><div class="label">Đáy kỹ thuật</div><div class="value">{money('Bottom Low')}–{money('Bottom High')}</div></div>
<div class="box"><div class="label">{entry_label}</div><div class="value">{money('Entry Low')}–{money('Entry High')}</div></div>
<div class="box"><div class="label">{chase_label}</div><div class="value">&gt; {money('Chase Limit')}</div></div>
<div class="box"><div class="label">Stop</div><div class="value">{money('Stop')}</div></div>
<div class="box"><div class="label">{tp1_label}</div><div class="value">{money('TP1')}</div></div>
<div class="box"><div class="label">{tp2_label}</div><div class="value">{money('TP2')}</div></div>
<div class="box"><div class="label">{stretch_label}</div><div class="value">{money('Stretch Target')}</div></div>
<div class="box"><div class="label">Vùng bán</div><div class="value">{money('Sell Zone Low')}–{money('Sell Zone High')}</div></div>
</div>
<div class="scenarios">
<div class="box"><div class="label">Tiếp diễn ngay</div><div class="value">{safe_float(sc.get('Continuation')):.0f}%</div></div>
<div class="box"><div class="label">Retest nông</div><div class="value">{safe_float(sc.get('Shallow Retest')):.0f}%</div></div>
<div class="box"><div class="label">Retest sâu</div><div class="value">{safe_float(sc.get('Deep Retest')):.0f}%</div></div>
<div class="box"><div class="label">Breakdown</div><div class="value">{safe_float(sc.get('Breakdown')):.0f}%</div></div>
</div>
<div class="plans"><div class="plan-line"><b>Plan A:</b> {plan.get('Plan A')}</div><div class="plan-line"><b>Plan B:</b> {plan.get('Plan B')}</div><div class="plan-line"><b>Plan C:</b> {plan.get('Plan C')}</div></div>
<div class="note">{reasons}<br>TP1 là kháng cự gần; Stretch chỉ dùng khi breakout được xác nhận.</div>
</div>"""
