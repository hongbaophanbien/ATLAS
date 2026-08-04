from __future__ import annotations
from core import safe_float
from x_connector import analyze_manual_posts

def analyst_consensus(text):
    df,base=analyze_manual_posts(text)
    if df.empty: return df,{'Consensus':'No data','Score':0.0,'Confidence':0.0,'Bullish':0,'Bearish':0,'Neutral':0}
    bull=int((df['Sentiment']=='Bullish').sum()); bear=int((df['Sentiment']=='Bearish').sum()); neutral=int((df['Sentiment']=='Neutral').sum())
    consensus='Bullish consensus' if bull>bear+1 else 'Bearish consensus' if bear>bull+1 else 'Mixed / retest debate'
    return df,{'Consensus':consensus,'Score':safe_float(base.get('Sentiment Score'),0),'Confidence':safe_float(base.get('Confidence'),0),'Bullish':bull,'Bearish':bear,'Neutral':neutral}

def signal_fusion(base,flow,plan,analyst=None):
    analyst=analyst or {}; aw=min(.12,safe_float(analyst.get('Confidence'),0)/100*.12)
    raw=safe_float(base.get('MTF Score'),50)*.27+safe_float(base.get('Trade Score'),50)*.20+safe_float(base.get('Sector Flow'),50)*.13+safe_float(flow.get('Money In'),50)*.22+(100-safe_float(flow.get('Sell-off Risk'),50))*.10+safe_float(plan.get('Up Probability'),50)*.08
    a=50+safe_float(analyst.get('Score'),0)*.5; score=raw*(1-aw)+a*aw
    conf=max(0,min(100,35+abs(score-50)*.8+safe_float(base.get('RVOL20'),1)*5+safe_float(analyst.get('Confidence'),0)*.08))
    conclusion='High-conviction bullish setup' if score>=68 else 'Bullish, wait for trigger' if score>=58 else 'High-conviction bearish setup' if score<=35 else 'Bearish, wait for breakdown' if score<=44 else 'Mixed / no clean edge'
    return {'Combined Score':round(score,1),'Confidence':round(conf,1),'Conclusion':conclusion,'Chart':round(safe_float(base.get('MTF Score'),50),1),'Money Flow':round(safe_float(flow.get('Money In'),50),1),'Sector':round(safe_float(base.get('Sector Flow'),50),1),'Analysts':round(a,1)}

def build_story(ticker,base,flow,plan,fusion,analyst=None):
    analyst=analyst or {}
    parts=[f"{ticker} có Signal Fusion {fusion['Combined Score']:.0f}/100, confidence {fusion['Confidence']:.0f}%.",f"Money In {safe_float(flow.get('Money In')):.0f} so với Money Out {safe_float(flow.get('Money Out')):.0f}, trạng thái {flow.get('Flow Status','Neutral')}.",f"Kế hoạch: {plan.get('Action','WAIT')}; entry {plan.get('Entry Low')}–{plan.get('Entry High')}, không chase trên {plan.get('Chase Limit')}, TP1 {plan.get('TP1')}, TP2 {plan.get('TP2')}." ]
    if analyst.get('Consensus') and analyst.get('Consensus')!='No data': parts.append(f"Analyst consensus: {analyst['Consensus']}; chỉ dùng như tín hiệu phụ.")
    if safe_float(flow.get('Sell-off Risk'),50)>=65: parts.append('Sell-off risk cao: ưu tiên breakdown/retest thay vì call sớm.')
    return ' '.join(parts)
