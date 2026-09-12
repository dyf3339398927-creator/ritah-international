'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('stockroom-session') || '';
if (token) sessionStorage.setItem('stockroom-session', token);
history.replaceState(null, '', '/');
let state, initialized = false, lastCatalog = '', sound = false, audio, busy = false;
const seen = new Map();
$('filter').value='18';
const labels = {waiting:'待查询',in_stock:'可取货',out_of_stock:'暂无库存',unknown:'未知',ineligible:'不支持取货'};
function node(tag, text, cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;}
function toast(message){$('toast').textContent=message;$('toast').style.display='block';clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').style.display='none',5000);}
async function api(path, data){const res=await fetch('/api/'+path,{method:data?'POST':'GET',headers:{'X-Session':token,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});const json=await res.json();if(!res.ok)throw Error(json.error||'请求失败');return json;}
async function action(path,data){try{await api(path,data);await refresh();}catch(e){toast(e.message);}}
function options(select,rows,value,label){select.replaceChildren(...rows.map(r=>{const o=node('option',label(r));o.value=value(r);return o;}));}
function renderCatalog(force=false){const locale=$('locale').value, catalog=state.catalogs[locale], status=state.catalogState[locale]||{};
  const stamp=locale+':'+(catalog?.fetchedAt||0)+':'+$('filter').value;
  if(force||stamp!==lastCatalog){const selected=$('product').value;const q=$('filter').value.toLowerCase();options($('product'),(catalog?.products||[]).filter(p=>(p.name+' '+p.part).toLowerCase().includes(q)),p=>p.part,p=>p.name+' · '+p.part);if([...$('product').options].some(o=>o.value===selected))$('product').value=selected;lastCatalog=stamp;}
  $('refresh').disabled=Boolean(status.loading);$('refresh').textContent=status.loading?'正在更新…':'↻ 刷新官网目录';
  $('catalogInfo').textContent=status.error|| (catalog?`目录更新于 ${new Date(catalog.fetchedAt*1000).toLocaleString()} · ${catalog.products.length} 个 SKU。${(catalog.warnings||[]).length?'部分页面未能更新。':''}`:'尚无已验证目录。点击刷新官网目录，或输入官方 SKU。');
}
function regionChanged(){options($('store'),state.stores[$('locale').value]||[],s=>s.id,s=>s.city+' · '+s.name);renderCatalog(true);}
function beep(){if(!sound||!audio)return;const osc=audio.createOscillator(),gain=audio.createGain();osc.frequency.value=880;gain.gain.value=.12;osc.connect(gain);gain.connect(audio.destination);osc.start();osc.stop(audio.currentTime+.3);}
function render(){if(!initialized){options($('locale'),Object.entries(state.regions),r=>r[0],r=>r[1]);$('interval').value=state.interval;regionChanged();initialized=true;}
 $('total').textContent=state.targets.length;$('available').textContent=state.targets.filter(t=>t.status==='in_stock').length;$('unknown').textContent=state.targets.filter(t=>t.status==='unknown').length;$('intervalView').textContent=state.interval;
 $('toggle').textContent=state.running?'暂停监控 Ⅱ':'开始监控 ↗';$('runstate').textContent=state.running?'● 监控中':'已暂停';
 $('next').textContent=state.checking?'正在查询官方库存…':state.running?'下一轮 '+Math.max(0,Math.ceil((state.nextCheck||Date.now()/1000)-Date.now()/1000))+' 秒':'添加目标，准备就绪';
 const list=$('targetList');list.replaceChildren();
 if(!state.targets.length){const empty=node('div',undefined,'empty');empty.append(node('div','◈','symbol'),node('strong','你的下一部 iPhone，从这里开始'),node('p','在右侧选择型号和门店，添加第一个监控目标。'));list.append(empty);}
 for(const t of state.targets){const old=seen.get(t.id);if(t.status==='in_stock'&&old!=='in_stock'&&old!==undefined){beep();toast(t.storeName+'：'+t.name+' 可取货');}seen.set(t.id,t.status);
   const card=node('article',undefined,'target'),top=node('div',undefined,'target-top'),title=node('div');title.append(node('strong',t.name),node('small',t.storeName+' · '+t.part));top.append(title,node('span',labels[t.status]||'未知','status '+t.status));card.append(top);
   if(t.reason||t.detail)card.append(node('div',t.reason||t.detail,'reason'));
   const controls=node('div',undefined,'target-actions'),buy=node('button','购买助手 ↗'),link=node('a','官网商品'),remove=node('button','移除');
   buy.onclick=()=>action('purchase',{id:t.id});link.href=t.url;link.target='_blank';link.rel='noreferrer';remove.onclick=()=>action('remove',{id:t.id});if(state.purchaseAvailable!==false)controls.append(buy);controls.append(link,remove);card.append(controls,node('small',t.checkedAt?'上次查询 '+new Date(t.checkedAt*1000).toLocaleTimeString():'等待首次查询'));list.append(card);
 }
 $('purchaseState').textContent=state.purchaseAvailable===false?'Docker 监控中；点击官网商品，在本机浏览器完成购买。':state.purchase.message||'购买助手会在独立 Edge / Chrome 窗口中打开。';
 $('logs').replaceChildren(...state.logs.slice(0,50).map(l=>{const row=node('div',undefined,'log-row '+l.kind);row.append(node('time',new Date(l.time*1000).toLocaleTimeString()),node('span',l.text));return row;}));
 if(!state.logs.length)$('logs').append(node('p','准备就绪，添加目标后开始监控。'));
 renderCatalog();
}
async function refresh(){if(busy)return;busy=true;try{state=await api('state');$('connection').textContent='● 本地服务已连接';render();}catch(e){$('connection').textContent='连接中断 · 请重新打开启动器';if(!initialized)toast(e.message);}finally{busy=false;}}
$('locale').onchange=regionChanged;$('filter').oninput=()=>renderCatalog(true);
$('refresh').onclick=()=>action('catalog',{locale:$('locale').value});
$('toggle').onclick=()=>action('control',{running:!state?.running});
$('saveSettings').onclick=()=>action('settings',{interval:Number($('interval').value)});
$('notify').onclick=()=>{sound=!sound;if(sound){audio=audio||new AudioContext();audio.resume();beep();}$('notify').textContent=sound?'关闭声音提醒':'开启声音提醒';toast('声音提醒'+(sound?'已开启，保持本页面打开':'已关闭'));};
$('addForm').onsubmit=async e=>{e.preventDefault();const locale=$('locale').value;const manual=$('manualPart').value.trim();const selected=state.catalogs[locale]?.products.find(p=>p.part===$('product').value);if(!manual&&!selected){toast('请先刷新目录并选择型号，或输入官方 SKU');return;}await action('targets',{locale,store:$('store').value,part:manual||selected.part,name:manual?$('manualName').value:selected.name});};
// A manually supplied SKU may be used even before the catalog is available.
$('product').required=false;
refresh();setInterval(refresh,2000);
