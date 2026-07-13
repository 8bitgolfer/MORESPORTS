import json, os, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

BASE='https://api.balldontlie.io/wnba/v1'
KEY=os.environ.get('BALLDONTLIE_API_KEY')
ET=ZoneInfo('America/New_York')
TARGET_DATE=os.environ.get('WNBA_DATE') or datetime.now(ET).date().isoformat()
if not KEY: raise SystemExit('Missing BALLDONTLIE_API_KEY')

def get(path,params=None):
    url=BASE+path
    if params:url+='?'+urllib.parse.urlencode(params,doseq=True)
    req=urllib.request.Request(url,headers={'Authorization':KEY})
    with urllib.request.urlopen(req,timeout=30) as r:return json.load(r)

def val(s,m):
    if m=='pts':return s.get('pts') or 0
    if m=='reb':return s.get('reb') or 0
    if m=='ast':return s.get('ast') or 0
    if m=='3pm':return s.get('fg3m') or 0
    if m=='pra':return (s.get('pts') or 0)+(s.get('reb') or 0)+(s.get('ast') or 0)
    raise ValueError('Unsupported market '+m)

def abbr(team):
    return team.get('abbreviation') or team.get('abbrev') or team.get('name','')[:3].upper()

def game_datetime(g):
    return g.get('datetime') or g.get('date_time') or g.get('date') or ''

# Fetch only the games on the requested Eastern Time slate.
games_raw=get('/games',{'dates[]':TARGET_DATE,'per_page':100}).get('data',[])
games=[]
for g in games_raw:
    home=g.get('home_team') or {}
    away=g.get('visitor_team') or g.get('away_team') or {}
    games.append({
        'id':g.get('id'),
        'date':TARGET_DATE,
        'datetime':game_datetime(g),
        'home_team':abbr(home),
        'away_team':abbr(away),
        'home_team_id':home.get('id'),
        'away_team_id':away.get('id')
    })

with open('data/lines.json',encoding='utf-8') as f:
    lines=json.load(f).get('props',[])

out=[]
for p in lines:
    players=get('/players/active',{'search':p['player'],'per_page':100}).get('data',[])
    exact=[x for x in players if f"{x.get('first_name','')} {x.get('last_name','')}".strip().lower()==p['player'].lower()]
    if not exact:
        print('Player not found:',p['player']);continue
    pl=exact[0]
    team=pl.get('team') or {}
    team_id=team.get('id')
    game=next((g for g in games if team_id in (g['home_team_id'],g['away_team_id'])),None)
    if not game:
        print('Skipping; player team has no game today:',p['player']);continue

    home=team_id==game['home_team_id']
    opponent_id=game['away_team_id'] if home else game['home_team_id']
    opponent=game['away_team'] if home else game['home_team']
    team_abbr=game['home_team'] if home else game['away_team']

    stats=get('/player_stats',{'player_ids[]':pl['id'],'seasons[]':TARGET_DATE[:4],'per_page':100}).get('data',[])
    stats=sorted(stats,key=lambda s:(s.get('game') or {}).get('date',''),reverse=True)
    logs=[];h2h=[]
    for s in stats:
        sg=s.get('game') or {}
        shome=(sg.get('home_team') or {})
        saway=(sg.get('visitor_team') or sg.get('away_team') or {})
        was_home=team_id==shome.get('id')
        opp=saway if was_home else shome
        item={'date':sg.get('date','')[5:10].replace('-','/'),'value':val(s,p['market']),'opponent':abbr(opp)}
        if len(logs)<10:logs.append(item)
        if opp.get('id')==opponent_id:h2h.append(item)

    values=[x['value'] for x in logs]
    projection=round(sum(values)/len(values),1) if values else 0
    out.append({
        **p,
        'team':team_abbr,'opponent':opponent,'home':home,
        'game_id':game['id'],'game_date':TARGET_DATE,'game_datetime':game['datetime'],
        'position':pl.get('position_abbreviation') or pl.get('position',''),
        'projection':projection,'last10':logs,'h2h':h2h
    })

with open('data/props.json','w',encoding='utf-8') as f:
    json.dump({'updated_at':datetime.now(ET).isoformat(timespec='minutes'),'slate_date':TARGET_DATE,'games':games,'props':out},f,indent=2)
print(f'Wrote {len(out)} props for {len(games)} games on {TARGET_DATE}.')
