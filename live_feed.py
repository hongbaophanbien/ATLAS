from datetime import datetime
from core import safe_float

def make_feed(scan,rotation):
    now=datetime.now().strftime('%H:%M'); events=[]
    if rotation is not None and not rotation.empty:
        for _,r in rotation.head(3).iterrows():
            if safe_float(r.get('Rotation'))>7: events.append({'kind':'good','title':f"Rotation into {r['Theme']}",'detail':f"Rotation {r['Rotation']:+.1f}; breadth {r['Breadth Up %']:.0f}%; leaders {r['Leaders']}",'time':now})
        for _,r in rotation.tail(2).iterrows():
            if safe_float(r.get('Rotation'))<-7: events.append({'kind':'bad','title':f"Money leaving {r['Theme']}",'detail':f"Rotation {r['Rotation']:+.1f}; laggards {r['Laggards']}",'time':now})
    if scan is not None and not scan.empty:
        for _,r in scan.sort_values('Net Flow',ascending=False).head(4).iterrows():
            if safe_float(r.get('Net Flow'))>18: events.append({'kind':'good','title':f"{r['Ticker']} accumulation",'detail':f"Net Flow {r['Net Flow']:+.1f}; Call Score {r.get('Call Score',0):.0f}",'time':now})
        for _,r in scan.sort_values('Net Flow').head(4).iterrows():
            if safe_float(r.get('Net Flow'))<-18: events.append({'kind':'bad','title':f"{r['Ticker']} distribution",'detail':f"Net Flow {r['Net Flow']:+.1f}; Put Score {r.get('Put Score',0):.0f}",'time':now})
    return events[:12]
