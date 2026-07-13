let DATA=[];
let GAMES=[];
let selectedGames=new Set();
let current=null;
let activeTab='last10';

const fmt=n=>Number.isInteger(Number(n))?String(Number(n)):Number(n).toFixed(1);
const avg=a=>a.length?a.reduce((s,x)=>s+Number(x.value||0),0)/a.length:0;
const rate=(a,l)=>a.length?Math.round(a.filter(x=>Number(x.value)>Number(l)).length/a.length*100):0;
const gameKey=g=>g.id||`${g.away_team}-${g.home_team}-${g.date}`;
const propGameKey=p=>p.game_id||`${p.home?p.opponent:p.team}-${p.home?p.team:p.opponent}-${p.game_date||''}`;

function localTime(iso){
  if(!iso)return '';
  const d=new Date(iso);
  return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'numeric',minute:'2-digit'}).format(d)+' ET';
}

async function init(){
  const r=await fetch('data/props.json?'+Date.now());
  const j=await r.json();
  DATA=(j.props||[]).filter(p=>p.market==='pts');
  GAMES=j.games||deriveGames(DATA);
  selectedGames=new Set(GAMES.map(gameKey));
  document.querySelector('#updatedAt').textContent='Last updated: '+(j.updated_at||'manual data');
  renderGames();
  populateTeams();
  render();
}

function deriveGames(props){
  const map=new Map();
  props.forEach(p=>{
    const away=p.home?p.opponent:p.team;
    const home=p.home?p.team:p.opponent;
    const id=p.game_id||`${away}-${home}-${p.game_date||''}`;
    if(!map.has(id))map.set(id,{id,date:p.game_date||'',datetime:p.game_datetime||'',away_team:away,home_team:home});
  });
  return [...map.values()];
}

function renderGames(){
  const wrap=document.querySelector('#games');
  if(!GAMES.length){wrap.innerHTML='<span class="noGames">No WNBA games found for this slate.</span>';return;}
  wrap.innerHTML=GAMES.map(g=>{
    const k=gameKey(g),active=selectedGames.has(k);
    return `<button class="gameChip ${active?'active':''}" data-game="${k}">
      <span><b>${g.away_team}</b> @ <b>${g.home_team}</b></span>
      <small>${localTime(g.datetime)||g.time||''}</small>
    </button>`;
  }).join('');
  wrap.querySelectorAll('.gameChip').forEach(b=>b.onclick=()=>{
    const k=b.dataset.game;
    selectedGames.has(k)?selectedGames.delete(k):selectedGames.add(k);
    renderGames();render();
  });
  document.querySelector('#selectAllGames').textContent=selectedGames.size===GAMES.length?'Clear all':'Select all';
}

function populateTeams(){
  const teams=[...new Set(DATA.map(x=>x.team))].sort();
  document.querySelector('#team').innerHTML='<option value="all">All teams</option>'+teams.map(t=>`<option>${t}</option>`).join('');
}

function filteredData(){
  const q=document.querySelector('#search').value.toLowerCase();
  const m='pts';
  const t=document.querySelector('#team').value;
  return DATA.filter(x=>selectedGames.has(propGameKey(x))&&x.player.toLowerCase().includes(q)&&(m==='all'||x.market===m)&&(t==='all'||x.team===t));
}

function render(){
  const f=filteredData();
  document.querySelector('#rows').innerHTML=f.map(x=>{
    const l10=x.last10||[],l5=l10.slice(0,5),h=x.h2h||[],edge=Number(x.projection)-Number(x.line);
    return `<tr data-id="${DATA.indexOf(x)}"><td><span class="player">${x.player}</span><span class="sub">${x.team} · ${x.position||''}</span></td><td>${x.team} ${x.home?'vs':'@'} ${x.opponent}</td><td><span class="pill">${x.market_label}</span></td><td>${fmt(x.line)}</td><td>${fmt(avg(l5))}</td><td>${fmt(avg(l10))}</td><td>${h.length?fmt(avg(h)):'—'}</td><td>${fmt(x.projection)}</td><td class="${edge>=0?'positive':'negative'}">${edge>=0?'+':''}${fmt(edge)}</td><td class="rate">${rate(l10,x.line)}%</td></tr>`;
  }).join('')||'<tr><td colspan="10" class="empty">No props match the selected game(s).</td></tr>';
  document.querySelector('#propCount').textContent=f.length;
  const sorted=[...f].sort((a,b)=>rate(b.last10||[],b.line)-rate(a.last10||[],a.line));
  const best=sorted[0];
  document.querySelector('#bestRate').textContent=best?`${best.player} ${rate(best.last10||[],best.line)}%`:'—';
  document.querySelector('#avgEdge').textContent=f.length?fmt(f.reduce((s,x)=>s+(Number(x.projection)-Number(x.line)),0)/f.length):'—';
  document.querySelectorAll('tbody tr[data-id]').forEach(r=>r.onclick=()=>openModal(DATA[+r.dataset.id]));
}

function openModal(x){
  current=x;activeTab='last10';
  document.querySelector('#modalName').textContent=x.player;
  document.querySelector('#modalMatchup').textContent=`${x.team} ${x.home?'vs':'@'} ${x.opponent}${x.game_datetime?' · '+localTime(x.game_datetime):''}`;
  document.querySelector('#modalMarket').textContent=x.market_label.toUpperCase()+' MODEL';
  document.querySelector('#modalLine').textContent=fmt(x.line);
  document.querySelector('#modalProjection').textContent=fmt(x.projection);
  const e=Number(x.projection)-Number(x.line);
  document.querySelector('#modalEdge').textContent=(e>=0?'+':'')+fmt(e);
  document.querySelector('#modalEdge').className=e>=0?'positive':'negative';
  document.querySelector('#modalH2H').textContent=rate(x.h2h||[],x.line)+'%';
  document.querySelectorAll('.tabs button').forEach(b=>b.classList.toggle('active',b.dataset.tab==='last10'));
  draw();document.querySelector('#modalBack').hidden=false;
}

function draw(){
  const a=activeTab==='last5'?(current.last10||[]).slice(0,5):activeTab==='h2h'?(current.h2h||[]):current.last10||[];
  document.querySelector('#periodLabel').textContent=activeTab==='h2h'?'H2H Over %':activeTab==='last5'?'L5 Over %':'L10 Over %';
  document.querySelector('#modalOver').textContent=rate(a,current.line)+'%';
  const max=Math.max(Number(current.line)*1.35,...a.map(x=>Number(x.value)),1);
  document.querySelector('#chart').innerHTML=a.length?a.map(g=>{
    const cls=Number(g.value)>Number(current.line)?'green':Number(g.value)<Number(current.line)?'red':'push';
    return `<div class="gameRow"><span>${g.date}${g.opponent?' vs '+g.opponent:''}</span><div class="track"><div class="bar ${cls}" style="width:${Math.max(4,Number(g.value)/max*100)}%"></div></div><span class="gameVal">${fmt(g.value)}</span></div>`;
  }).join(''):'<p>No games available.</p>';
}

document.querySelectorAll('#search,#market,#team').forEach(e=>e.addEventListener('input',render));
document.querySelector('#selectAllGames').onclick=()=>{
  selectedGames=selectedGames.size===GAMES.length?new Set():new Set(GAMES.map(gameKey));
  renderGames();render();
};
document.querySelector('#closeModal').onclick=()=>document.querySelector('#modalBack').hidden=true;
document.querySelector('#modalBack').onclick=e=>{if(e.target.id==='modalBack')e.currentTarget.hidden=true};
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{activeTab=b.dataset.tab;document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('active',x===b));draw()});
init();
