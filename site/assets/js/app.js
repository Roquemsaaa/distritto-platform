'use strict';

let P=[],C={},INV={items:{}},DISCOUNTS={rules:[]},SETTINGS={few_units_max:2,analytics_enabled:true,ml_enabled:false};
const WA='573218194617';
let curP=null,curV=0;

const money=n=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Number(n||0));
const keyOf=(p,v)=>`${p.id}::${v.id}`;
const stockFor=(p,v)=>{const x=INV.items?.[keyOf(p,v)]?.stock;return x===null||x===undefined?null:Number(x)};

function stockStatus(stock){
  if(stock===null||stock===undefined)return {text:'Unidades sin registrar',cls:'unregistered'};
  if(stock<=0)return {text:'Agotado',cls:'sold'};
  if(stock===1)return {text:'Última unidad',cls:'last'};
  if(stock<=Number(SETTINGS.few_units_max||2))return {text:'Pocas unidades',cls:'few'};
  return {text:'Disponible',cls:'available'};
}

function applicableDiscount(p){
  const matches=(DISCOUNTS.rules||[]).filter(r=>r.active!==false && (
    r.scope==='all' ||
    (r.scope==='collection' && r.target_id===p.collection_id) ||
    (r.scope==='product' && r.target_id===p.id)
  ));
  if(!matches.length)return null;
  return matches.map(r=>({
      r,
      saving:r.discount_type==='percentage'?p.price_cop*r.value/100:r.value
    }))
    .sort((a,b)=>b.saving-a.saving)[0].r;
}

function pricing(p){
  const d=applicableDiscount(p);
  if(!d)return {base:p.price_cop,final:p.price_cop,discount:null};
  const final=d.discount_type==='percentage'
    ? Math.max(0,Math.round(p.price_cop*(1-d.value/100)))
    : Math.max(0,p.price_cop-d.value);
  return {base:p.price_cop,final,discount:d};
}

async function loadState(){
  try{
    const r=await fetch('/api/public/state',{cache:'no-cache'});
    if(r.ok)return await r.json();
  }catch(e){}
  const [catalog,inventory,discounts]=await Promise.all([
    fetch('data/catalog.json',{cache:'no-cache'}).then(r=>r.json()),
    fetch('data/inventory.json',{cache:'no-cache'}).then(r=>r.json()),
    fetch('data/discounts.json',{cache:'no-cache'}).then(r=>r.json())
  ]);
  return {catalog,inventory,discounts};
}

function normalize(state){
  const data=state.catalog;
  INV=state.inventory||{items:{}};
  DISCOUNTS=state.discounts||{rules:[]};
  SETTINGS=state.settings||SETTINGS;
  P=(data.products||[]).filter(p=>p.active!==false).map(p=>({
    ...p,
    marca:p.brand,
    nombre:p.name,
    coleccion:(data.collections||[]).find(c=>c.id===p.collection_id)?.name||p.collection_id,
    col_id:p.collection_id,
    ref:p.reference,
    descripcion:p.description||'',
    cierre:p.closure||'',
    tipo:p.type||'',
    variantes:(p.variants||[]).filter(v=>v.active!==false).map(v=>({
      ...v,nombre:v.name,hex:v.color_hex||'#111111',imagenes:v.images||[]
    }))
  }));
  C={};
  (data.collections||[]).forEach(col=>{
    const ids=(col.product_ids||P.filter(p=>p.collection_id===col.id).map(p=>p.id)).filter(id=>P.some(p=>p.id===id));
    if(ids.length)C[col.id]={nombre:col.name,ids};
  });
}

document.addEventListener('DOMContentLoaded',async()=>{
  try{
    normalize(await loadState());
    renderCollectionNav();
    renderCatalog('all');
  }catch(err){
    console.error(err);
    const main=document.getElementById('catalogo');
    if(main)main.innerHTML='<section class="cs"><h2 class="ct">No pudimos cargar el catálogo</h2></section>';
  }
});


function renderCollectionNav(){
  const nav=document.querySelector('.cn');
  if(!nav)return;
  nav.innerHTML='<button class="cb active" data-col="all" onclick="filterCol(this)">Todos</button>';
  Object.entries(C).forEach(([id,col])=>{
    const b=document.createElement('button');
    b.className='cb';b.dataset.col=id;b.textContent=col.nombre;b.onclick=()=>filterCol(b);
    nav.appendChild(b);
  });
  const perso=document.createElement('button');
  perso.className='cb';perso.dataset.col='personalizacion';perso.textContent='Personalización';perso.onclick=()=>goPerso(perso);
  nav.appendChild(perso);
}

function renderCatalog(filter){
  const main=document.getElementById('catalogo');main.innerHTML='';
  const cols=filter==='all'?C:(C[filter]?{[filter]:C[filter]}:{});
  Object.entries(cols).forEach(([cid,col])=>{
    const prods=col.ids.map(id=>P.find(p=>p.id===id)).filter(Boolean);
    if(!prods.length)return;
    const sec=document.createElement('section');
    sec.className='cs';sec.id=cid;
    sec.innerHTML=`<div class="ch"><div><div class="ce">Colección</div><h2 class="ct">${esc(col.nombre)}</h2></div><div class="cc">${prods.length} modelo${prods.length!==1?'s':''}</div></div><div class="cdv"></div><div class="pg" id="g-${cid}"></div>`;
    main.appendChild(sec);
    const grid=sec.querySelector('#g-'+CSS.escape(cid));
    prods.forEach(p=>grid.appendChild(makeCard(p)));
  });
}

function makeCard(p){
  const el=document.createElement('article');el.className='pc';
  const v=p.variantes[0]||{id:'',nombre:'',hex:'#111',imagenes:[]};
  const tags=(p.tags||[]).map(t=>`<span class="tg">${esc(t)}</span>`).join('');
  const swatches=p.variantes.map((vv,i)=>`<button class="sw${i===0?' active':''}" style="background:${safeHex(vv.hex)}" data-idx="${i}" aria-label="${esc(vv.nombre)}" onclick="swapV(event,this,'${attr(p.id)}')"></button>`).join('');
  const pr=pricing(p),ss=stockStatus(stockFor(p,v));
  const priceHtml=pr.discount
    ? `<div class="price-wrap"><span class="old-price">${money(pr.base)}</span><span class="pp">${money(pr.final)}</span><span class="discount-chip">${esc(pr.discount.name)}</span></div>`
    : `<div class="pp">${money(pr.final)}</div>`;
  el.innerHTML=`<div class="pw">
    <img src="${attr(v.imagenes?.[0]||'')}" alt="${attr(p.nombre)}" width="900" height="900" loading="lazy" onerror="imgFallback(this)">
    <div class="pt">${tags}</div><div class="stock-badge ${ss.cls}">${ss.text}</div>
  </div>
  <div class="pb">
    <div class="pcl">${esc(p.coleccion)}</div><div class="pn">${esc(p.nombre)}</div><div class="pr">${esc(p.ref)}</div>
    <div class="pco">${swatches}</div>${priceHtml}
    <div class="pca"><button class="bcd" onclick="openModal('${attr(p.id)}')">Ver detalles</button><button class="bwa" onclick="wa('${js(p.nombre)}','${js(p.ref)}','${js(money(pr.final))}')">WhatsApp</button></div>
  </div>`;
  return el;
}

function swapV(e,el,pid){
  e.stopPropagation();
  const p=P.find(x=>x.id===pid);if(!p)return;
  const idx=+el.dataset.idx,v=p.variantes[idx];if(!v)return;
  el.closest('.pco').querySelectorAll('.sw').forEach(s=>s.classList.remove('active'));el.classList.add('active');
  const card=el.closest('.pc'),img=card.querySelector('.pw img');if(img)img.src=v.imagenes?.[0]||'';
  const badge=card.querySelector('.stock-badge'),ss=stockStatus(stockFor(p,v));
  badge.textContent=ss.text;badge.className=`stock-badge ${ss.cls}`;
}

function openModal(pid,vi=0){
  curP=P.find(p=>p.id===pid);curV=vi;if(!curP)return;
  renderModal();document.getElementById('modal').classList.add('open');document.body.style.overflow='hidden';
}
function renderModal(){
  const p=curP,v=p.variantes[curV];if(!v)return;
  const pr=pricing(p),ss=stockStatus(stockFor(p,v));
  document.getElementById('m-col').textContent=p.coleccion;
  document.getElementById('m-name').textContent=p.nombre;
  document.getElementById('m-ref').textContent=p.ref;
  document.getElementById('m-price').textContent=pr.discount?`${money(pr.final)} · antes ${money(pr.base)}`:money(pr.final);
  document.getElementById('m-desc').textContent=p.descripcion;
  const detalle=(v.imagenes?.length>1)?v.imagenes.slice(1):(v.imagenes||[]);
  const mm=document.getElementById('modal-main');mm.src=detalle[0]||v.imagenes?.[0]||'';mm.alt=p.nombre+' detalle';
  document.getElementById('modal-thumbs').innerHTML=detalle.map((img,i)=>`<img src="${attr(img)}" onerror="imgFallback(this)" class="th${i===0?' active':''}" alt="Detalle ${i+2}" loading="lazy" onclick="setMain(this,'${attr(img)}')">`).join('');
  document.getElementById('m-colors').innerHTML=p.variantes.map((vv,i)=>`<button class="swl${i===curV?' active':''}" style="background:${safeHex(vv.hex)}" aria-label="${esc(vv.nombre)}" onclick="switchV(${i})"></button>`).join('');
  const units=stockFor(p,v);document.getElementById('m-color-name').textContent=units===null?`${v.nombre} · ${ss.text}`:`${v.nombre} · ${ss.text} (${units} u.)`;
  document.getElementById('m-specs').innerHTML=[
    ['Tipo',p.tipo],['Cierre',p.cierre],['Colección',p.coleccion],['Ref.',p.ref],['Disponibilidad',ss.text]
  ].filter(x=>x[1]).map(([k,val])=>`<div class="sr"><span class="sk">${esc(k)}</span><span class="sv">${esc(val)}</span></div>`).join('');
  const msg=encodeURIComponent(`Hola DISTRITTO, quiero consultar:\n${p.nombre}\nColor: ${v.nombre}\nPrecio: ${money(pr.final)}\nRef: ${p.ref}`);
  document.getElementById('m-wa').href=`https://wa.me/${WA}?text=${msg}`;
}
function setMain(el,src){document.getElementById('modal-main').src=src;document.querySelectorAll('.th').forEach(t=>t.classList.remove('active'));el.classList.add('active')}
function switchV(i){curV=i;renderModal()}
function closeModal(e){if(e&&e.target!==document.getElementById('modal'))return;document.getElementById('modal').classList.remove('open');document.body.style.overflow=''}
function filterCol(btn){document.querySelectorAll('.cb').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderCatalog(btn.dataset.col);setTimeout(()=>document.getElementById('catalogo').scrollIntoView({behavior:'smooth',block:'start'}),30)}
function imgFallback(img){if(img.dataset.fallbackTried){img.style.opacity=.25;return}img.dataset.fallbackTried='1';if(img.src.includes('/catalogo/')&&!img.src.includes('/catalogo/1.CATALOGO/'))img.src=img.src.replace('/catalogo/','/catalogo/1.CATALOGO/')}
function wa(nombre,ref,precio){window.open(`https://wa.me/${WA}?text=${encodeURIComponent(`Hola DISTRITTO, quiero consultar:\n${nombre}\nRef: ${ref}\nPrecio: ${precio}`)}`,'_blank','noopener')}
function goPerso(btn){document.querySelectorAll('.cb').forEach(b=>b.classList.remove('active'));btn.classList.add('active');renderCatalog('all');setTimeout(()=>document.getElementById('personalizacion')?.scrollIntoView({behavior:'smooth'}),60)}

(function(){
  function start(){const imgs=document.querySelectorAll('#hero-carousel img');if(imgs.length<2)return;let cur=0;setTimeout(()=>setInterval(()=>{imgs[cur].style.opacity='0';cur=(cur+1)%imgs.length;imgs[cur].style.opacity='1'},4000),3000)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start);else start()
})();
document.addEventListener('keydown',e=>{if(e.key==='Escape')closeModal()});

function esc(v=''){return String(v).replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]))}
function attr(v=''){return esc(v)}
function js(v=''){return String(v).replace(/\\/g,'\\\\').replace(/'/g,"\\'").replace(/\n/g,' ')}
function safeHex(v=''){return /^#[0-9A-Fa-f]{3,8}$/.test(v)?v:'#111111'}


// ── ANALYTICS + RECOMMENDATIONS v1.0 ───────────────────────────────────────
const dttUid=()=>crypto.randomUUID?crypto.randomUUID():'dtt-'+Date.now()+'-'+Math.random().toString(16).slice(2);
let dttVisitor=localStorage.getItem('dtt_visitor_id')||dttUid();localStorage.setItem('dtt_visitor_id',dttVisitor);
let dttSession=sessionStorage.getItem('dtt_session_id')||dttUid();sessionStorage.setItem('dtt_session_id',dttSession);
const dttQs=new URLSearchParams(location.search);
const dttTraffic={source:dttQs.get('utm_source')||'',medium:dttQs.get('utm_medium')||'',campaign:dttQs.get('utm_campaign')||'',referrer:document.referrer||'',device:/Mobi|Android/i.test(navigator.userAgent)?'Mobile':(/Tablet|iPad/i.test(navigator.userAgent)?'Tablet':'Desktop')};
function dttTrack(event_type,extra={}){if(SETTINGS.analytics_enabled===false)return;const payload={event_type,occurred_at:new Date().toISOString(),visitor_id:dttVisitor,session_id:dttSession,page:location.pathname+location.search,...dttTraffic,...extra};const raw=JSON.stringify(payload);if(navigator.sendBeacon){navigator.sendBeacon('/api/events',new Blob([raw],{type:'application/json'}));}else{fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body:raw,keepalive:true}).catch(()=>{});}}
async function dttLoadRecommendations(pid){let box=document.getElementById('m-recs');if(!box){box=document.createElement('div');box.id='m-recs';box.style.cssText='border-top:1px solid #E8E5DE;padding-top:16px;margin-bottom:16px';document.getElementById('m-specs')?.after(box)}if(!box)return;try{const d=await fetch(`/api/recommendations?product_id=${encodeURIComponent(pid)}&limit=4`).then(r=>r.json());box.innerHTML=`<div class="mcl">También te puede gustar</div><div style="display:grid;grid-template-columns:repeat(2,1fr);gap:6px">${(d.items||[]).map(x=>`<button class="bcd dtt-rec" data-id="${attr(x.id)}">${esc(x.name)}</button>`).join('')}</div>`;box.querySelectorAll('.dtt-rec').forEach(b=>b.onclick=()=>{dttTrack('recommendation_click',{product_id:b.dataset.id,metadata:{engine:d.engine,model_version:d.model_version}});openModal(b.dataset.id)});dttTrack('recommendation_view',{product_id:pid,metadata:{engine:d.engine,model_version:d.model_version}})}catch(e){box.innerHTML=''}}
const _dttOpenModal=openModal;openModal=function(pid,vi=0){_dttOpenModal(pid,vi);const p=P.find(x=>x.id===pid),v=p?.variantes?.[vi];if(p)dttTrack('product_view',{product_id:p.id,variant_id:v?.id||'',collection_id:p.collection_id});dttLoadRecommendations(pid)};
const _dttSwapV=swapV;swapV=function(e,el,pid){_dttSwapV(e,el,pid);const p=P.find(x=>x.id===pid),v=p?.variantes?.[+el.dataset.idx];if(p&&v)dttTrack('variant_view',{product_id:p.id,variant_id:v.id,collection_id:p.collection_id})};
const _dttSwitchV=switchV;switchV=function(i){_dttSwitchV(i);const p=curP,v=p?.variantes?.[i];if(p&&v)dttTrack('variant_view',{product_id:p.id,variant_id:v.id,collection_id:p.collection_id})};
const _dttSetMain=setMain;setMain=function(el,src){_dttSetMain(el,src);if(curP){const v=curP.variantes?.[curV];dttTrack('image_view',{product_id:curP.id,variant_id:v?.id||'',collection_id:curP.collection_id})}};
const _dttFilterCol=filterCol;filterCol=function(btn){_dttFilterCol(btn);dttTrack('filter_applied',{collection_id:btn.dataset.col});dttTrack('collection_view',{collection_id:btn.dataset.col})};
const _dttGoPerso=goPerso;goPerso=function(btn){_dttGoPerso(btn);dttTrack('collection_view',{collection_id:'personalizacion'})};
const _dttWa=wa;wa=function(nombre,ref,precio){const p=P.find(x=>x.nombre===nombre&&x.ref===ref);dttTrack('whatsapp_click',{product_id:p?.id||'',collection_id:p?.collection_id||''});_dttWa(nombre,ref,precio)};
document.addEventListener('DOMContentLoaded',()=>setTimeout(()=>dttTrack('page_view'),300));
setInterval(()=>{if(document.visibilityState==='visible')dttTrack('heartbeat',{numeric_value:30})},30000);
