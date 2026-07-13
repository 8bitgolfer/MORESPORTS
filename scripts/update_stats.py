import json, os, urllib.parse, urllib.request
from datetime import date
BASE='https://api.balldontlie.io/wnba/v1'
KEY=os.environ.get('BALLDONTLIE_API_KEY')
if not KEY: raise SystemExit('Missing BALLDONTLIE_API_KEY')
def get(path,params):
    url=BASE+path+'?'+urllib.parse.urlencode(params,doseq=True)
    req=urllib.request.Request(url,headers={'Authorization':KEY})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)
def val(s,m):
    if m=='pts':return s.get('pts') or 0
    if m=='reb':return s.get('reb') or 0
    if m=='ast':return s.get('ast') or 0
    if m=='3pm':return s.get('fg3m') or 0
    if m=='pra':return (s.get('pts') or 0)+(s.get('reb') or 0)+(s.get('ast') or 0)
    raise ValueError('Unsupported market '+m)
with open('data/lines.json') as f: lines=json.load(f)['props']
out=[]
for p in lines:
    players=get('/players/active',{'search':p['player'],'per_page':100})['data']
    exact=[x for x in players if f"{x['first_name']} {x['last_name']}".lower()==p['player'].lower()]
    if not exact: print('Player not found:',p['player']);continue
    pl=exact[0]; stats=get('/player_stats',{'player_ids[]':pl['id'],'seasons[]':date.today().year,'per_page':100})['data']
    stats=sorted(stats,key=lambda s:s['game']['date'],reverse=True)
    logs=[{'date':s['game']['date'][5:10].replace('-','/'),'value':val(s,p['market']),'opponent_team_id':None} for s in stats[:10]]
    values=[x['value'] for x in logs[:10]]; projection=round(sum(values)/len(values),1) if values else 0
    item={**p,'position':pl.get('position_abbreviation',''),'projection':projection,'last10':logs,'h2h':[]}
    out.append(item)
with open('data/props.json','w') as f:json.dump({'updated_at':date.today().isoformat(),'props':out},f,indent=2)
