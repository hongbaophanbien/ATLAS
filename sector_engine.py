from __future__ import annotations
import pandas as pd
from core import safe_float

THEMES={
"Big Tech":["AAPL","MSFT","AMZN","GOOGL","META","NVDA","TSLA"],
"AI Hardware":["NVDA","AMD","AVGO","TSM","MU","MRVL","ARM","INTC","SNDK","AMAT","LRCX","KLAC","ASML","QCOM","ALAB","DELL","WDC","GLW"],
"Semiconductor Focus":["SMH","SOXX","NVDA","AMD","AVGO","TSM","MU","MRVL","ARM","INTC","SNDK","AMAT","LRCX","KLAC","ASML","QCOM","ALAB"],
"Software":["MSFT","CRM","NOW","ADBE","ORCL","PLTR"],
"Cybersecurity":["PANW","CRWD","ZS","FTNT","OKTA"],
"Banks":["JPM","BAC","GS","MS","WFC","C"],
"Energy":["XOM","CVX","COP","SLB","OXY","VRT","BE","POWL"],
"Healthcare":["LLY","UNH","JNJ","MRK","ABBV"],
"Space":["SPCX","RKLB","ASTS","RDW","LUNR"],
"Quantum":["IONQ","RGTI","QBTS","QUBT"],
"Nuclear":["OKLO","SMR","LEU","BWXT","CCJ"],
"Rare Earths":["MP","USAR","UUUU"]}

def _clamp(v): return max(0,min(100,float(v)))

def build_theme_rotation(scan):
    if scan is None or scan.empty: return pd.DataFrame()
    out=[]; available=set(scan['Ticker'].astype(str))
    for theme,tickers in THEMES.items():
        members=scan[scan['Ticker'].isin([t for t in tickers if t in available])].copy()
        if members.empty: continue
        breadth=float((members['1D %']>0).mean()*100) if '1D %' in members else 50
        money_in=safe_float(members['Money In'].mean(),50); money_out=safe_float(members['Money Out'].mean(),50)
        mtf=safe_float(members['MTF Score'].mean(),50); trade=safe_float(members['Trade Score'].mean(),50)
        one=safe_float(members['1D %'].median(),0) if '1D %' in members else 0
        flow=_clamp(money_in*.32+breadth*.22+mtf*.22+trade*.14+_clamp(50+one*4)*.10)
        outflow=_clamp(money_out*.40+(100-breadth)*.20+(100-mtf)*.20+safe_float(members['Sell-off Risk'].mean(),50)*.20)
        rotation=flow-outflow
        status='Strong Inflow' if rotation>=18 else 'Inflow' if rotation>=7 else 'Strong Outflow' if rotation<=-18 else 'Outflow' if rotation<=-7 else 'Neutral'
        leaders=', '.join(members.sort_values(['Net Flow','Trade Score'],ascending=False)['Ticker'].head(3).tolist())
        laggards=', '.join(members.sort_values(['Net Flow','Trade Score'])['Ticker'].head(3).tolist())
        out.append({'Theme':theme,'Status':status,'Rotation':round(rotation,1),'Flow Score':round(flow,1),'Outflow Score':round(outflow,1),'Breadth Up %':round(breadth,1),'Leaders':leaders,'Laggards':laggards,'Members':len(members)})
    return pd.DataFrame(out).sort_values('Rotation',ascending=False).reset_index(drop=True) if out else pd.DataFrame()
