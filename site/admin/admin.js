'use strict';
let STATE={catalog:{products:[],collections:[]},inventory:{items:{}},discounts:{rules:[]}};
const $=s=>document.querySelector(s), $$=s=>[...document.querySelectorAll(s)];
const esc=v=>String(v??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[ch]));
const slug=v=>String(v||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^a-zA-Z0-9._-]+/g,'-').replace(/^-+|-+$/g,'').toLowerCase();
const money=n=>new Intl.NumberFormat('es-CO',{style:'currency',currency:'COP',maximumFractionDigits:0}).format(Number(n||0));
const api=async(path,options={})=>{
  const headers={...(options.headers||{})};
  if(!(options.body instanceof FormData))headers['Content-Type']='application/json';
  const r=await fetch(path,{...options,headers});
  const d=await r.json().catch(()=>({}));
  if(!r.ok)throw new Error(d.detail||`HTTP ${r.status}`);
  return d
};
const statusFor=n=>n===null||n===undefined||n===''?['Sin registrar','unregistered']:Number(n)<=0?['Agotado','sold']:Number(n)===1?['Última unidad','last']:Number(n)===2?['Pocas unidades','few']:['Disponible','available'];

async function load(){
  STATE=await api('/api/admin/state');
  renderAll();
}
function renderAll(){
  renderMetrics();renderCollections();renderProducts();renderInventory();renderDiscounts();fillCollectionSelects();fillDiscountTarget()
}
function fillCollectionSelects(){
  $$('.collection-select').forEach(sel=>{
    const current=sel.value;
    sel.innerHTML=STATE.catalog.collections.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('');
    if(current)sel.value=current
  })
}
function renderMetrics(){
  const products=STATE.catalog.products.length;
  const variants=STATE.catalog.products.reduce((a,p)=>a+(p.variants?.length||0),0);
  const units=Object.values(STATE.inventory.items||{}).reduce((a,x)=>a+(Number.isFinite(Number(x.stock))&&x.stock!==null?Number(x.stock):0),0);
  const activeDiscounts=(STATE.discounts.rules||[]).filter(x=>x.active).length;
  $('#metrics').innerHTML=[['Productos',products],['Variantes / colores',variants],['Unidades',units],['Descuentos activos',activeDiscounts]]
    .map(([l,v])=>`<div class="metric"><strong>${v}</strong><span>${l}</span></div>`).join('');
}
function renderProducts(){
  const cols=Object.fromEntries(STATE.catalog.collections.map(c=>[c.id,c.name]));
  $('#products-body').innerHTML=STATE.catalog.products.map(p=>`<tr>
    <td>${esc(p.reference)}</td>
    <td><strong>${esc(p.name)}</strong><div class="muted">${esc(p.brand)}</div></td>
    <td>${esc(cols[p.collection_id]||p.collection_id)}</td>
    <td>${money(p.price_cop)}</td>
    <td>${p.variants?.length||0}</td>
    <td><button class="btn ghost" onclick="editProduct('${esc(p.id)}')">Editar</button></td>
  </tr>`).join('');
}
function renderCollections(){
  $('#collections-body').innerHTML=STATE.catalog.collections.map(c=>`<tr>
    <td>${esc(c.id)}</td>
    <td><input id="col-${esc(c.id)}" value="${esc(c.name)}"></td>
    <td>${c.product_ids?.length||0}</td>
    <td><button class="btn ghost" onclick="saveCollection('${esc(c.id)}')">Guardar</button></td>
  </tr>`).join('');
}
function renderInventory(){
  const rows=[];
  for(const p of STATE.catalog.products){
    for(const v of (p.variants||[])){
      const key=`${p.id}::${v.id}`;
      const raw=STATE.inventory.items?.[key]?.stock;const stock=raw===null||raw===undefined?null:Number(raw);
      const [txt,cls]=statusFor(stock);
      rows.push(`<tr>
        <td>${esc(p.reference)}</td><td>${esc(p.name)}</td><td>${esc(v.name)}</td><td>${esc(v.sku||'—')}</td>
        <td><input id="stock-${esc(p.id)}-${esc(v.id)}" type="number" min="0" value="${stock===null?'':stock}" placeholder="Sin registrar" style="width:110px"></td>
        <td><span class="badge ${cls}">${txt}</span></td>
        <td><button class="btn ghost" onclick="saveStock('${esc(p.id)}','${esc(v.id)}')">Guardar</button></td>
      </tr>`)
    }
  }
  $('#inventory-body').innerHTML=rows.join('');
}
function targetLabel(r){
  if(r.scope==='all')return 'Todo el catálogo';
  if(r.scope==='product')return STATE.catalog.products.find(p=>p.id===r.target_id)?.name||r.target_id;
  return STATE.catalog.collections.find(c=>c.id===r.target_id)?.name||r.target_id;
}
function discountTargets(scope,current=''){
  const items=scope==='product'?STATE.catalog.products:scope==='collection'?STATE.catalog.collections:[];
  return items.map(x=>`<option value="${esc(x.id)}" ${x.id===current?'selected':''}>${esc(x.name)}</option>`).join('');
}
function renderDiscounts(){
  $('#discounts-body').innerHTML=(STATE.discounts.rules||[]).map(r=>`<tr>
    <td><input id="dn-${esc(r.id)}" value="${esc(r.name)}"></td>
    <td><select id="dt-${esc(r.id)}"><option value="percentage" ${r.discount_type==='percentage'?'selected':''}>Porcentaje</option><option value="fixed" ${r.discount_type==='fixed'?'selected':''}>Valor fijo</option></select></td>
    <td><input id="dv-${esc(r.id)}" type="number" min="1" value="${r.value}" style="width:110px"></td>
    <td><select id="ds-${esc(r.id)}" onchange="refreshDiscountTarget('${esc(r.id)}')"><option value="product" ${r.scope==='product'?'selected':''}>Producto</option><option value="collection" ${r.scope==='collection'?'selected':''}>Colección</option><option value="all" ${r.scope==='all'?'selected':''}>Todo</option></select></td>
    <td><select id="dg-${esc(r.id)}" ${r.scope==='all'?'disabled':''}>${discountTargets(r.scope,r.target_id)}</select></td>
    <td><input id="da-${esc(r.id)}" type="checkbox" ${r.active?'checked':''}></td>
    <td><button class="btn ghost" onclick="saveDiscount('${esc(r.id)}')">Guardar</button></td>
  </tr>`).join('');
}
function refreshDiscountTarget(id){
  const scope=document.getElementById(`ds-${id}`).value,sel=document.getElementById(`dg-${id}`);
  sel.disabled=scope==='all';sel.innerHTML=discountTargets(scope,'');
}
function fillDiscountTarget(){
  const scope=$('#discount-scope')?.value||'product';
  const sel=$('#discount-target'),wrap=$('#discount-target-wrap');
  if(!sel)return;
  if(scope==='all'){wrap.style.display='none';sel.innerHTML='';return}else wrap.style.display='flex';
  sel.innerHTML=(scope==='product'?STATE.catalog.products:STATE.catalog.collections)
    .map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');
}
$('#discount-scope').addEventListener('change',fillDiscountTarget);

$$('.tab-btn').forEach(b=>b.addEventListener('click',()=>{
  $$('.tab-btn').forEach(x=>x.classList.remove('active'));
  $$('.tab').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');$('#'+b.dataset.tab).classList.add('active')
}));

async function saveCollection(id){
  try{
    const name=document.getElementById(`col-${id}`).value.trim();
    await api(`/api/admin/collections/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify({name})});
    await load()
  }catch(e){alert(e.message)}
}
$('#collection-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target),id=slug(fd.get('id')),name=String(fd.get('name')||'').trim();
  try{await api('/api/admin/collections',{method:'POST',body:JSON.stringify({id,name})});e.target.reset();await load()}catch(err){alert(err.message)}
});
async function saveStock(product_id,variant_id){
  const input=document.getElementById(`stock-${product_id}-${variant_id}`);if(input.value===''){alert('Escribe una cantidad de unidades.');return;}const stock=Number(input.value);
  try{await api('/api/admin/inventory',{method:'POST',body:JSON.stringify({product_id,variant_id,stock})});await load()}catch(e){alert(e.message)}
}
$('#discount-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target);
  const body={
    id:`disc-${Date.now()}`,
    name:String(fd.get('name')||'').trim(),
    discount_type:fd.get('discount_type'),
    value:Number(fd.get('value')),
    scope:fd.get('scope'),
    target_id:fd.get('scope')==='all'?'':fd.get('target_id'),
    active:true
  };
  try{await api('/api/admin/discounts',{method:'POST',body:JSON.stringify(body)});e.target.reset();await load()}catch(err){alert(err.message)}
});
async function saveDiscount(id){
  const r=STATE.discounts.rules.find(x=>x.id===id);if(!r)return;
  const scope=document.getElementById(`ds-${id}`).value;
  const body={
    id:r.id,
    name:document.getElementById(`dn-${id}`).value.trim(),
    discount_type:document.getElementById(`dt-${id}`).value,
    value:Number(document.getElementById(`dv-${id}`).value),
    scope,
    target_id:scope==='all'?'':document.getElementById(`dg-${id}`).value,
    active:document.getElementById(`da-${id}`).checked
  };
  try{await api(`/api/admin/discounts/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)});await load()}catch(e){alert(e.message)}
}

const template=$('#variant-template'),variantsEl=$('#variants');
function addVariant(seed={}){
  const frag=template.content.cloneNode(true),el=frag.querySelector('.variant');
  el.querySelector('[data-field="name"]').value=seed.name||'';
  el.querySelector('[data-field="folder"]').value=seed.folder||'';
  el.querySelector('[data-field="sku"]').value=seed.sku||'';
  el.querySelector('[data-field="color_hex"]').value=seed.color_hex||'#111111';
  const ni=el.querySelector('[data-field="name"]'),fi=el.querySelector('[data-field="folder"]');
  ni.addEventListener('blur',()=>{if(!fi.value)fi.value=slug(ni.value).toUpperCase()});
  el.querySelector('.remove').onclick=()=>{if(variantsEl.children.length>1){el.remove();renumber()}};
  el.querySelector('[data-field="images"]').addEventListener('change',()=>preview(el));
  variantsEl.appendChild(el);renumber()
}
function renumber(){[...variantsEl.children].forEach((v,i)=>v.querySelector('.num').textContent=i+1)}
function ext(n){const e=String(n).split('.').pop().toLowerCase();return ['jpg','jpeg','png','webp'].includes(e)?e:'bin'}
function preview(el){
  const files=[...el.querySelector('[data-field="images"]').files],pv=el.querySelector('.preview'),plan=el.querySelector('.plan');
  pv.innerHTML='';plan.textContent=files.length?`Se guardarán como ${files.map((f,i)=>`${i+1}.${ext(f.name)}`).join(', ')}. Foto 1 = portada.`:'';
  files.forEach((f,i)=>{
    const fig=document.createElement('figure');if(i===0)fig.classList.add('cover');
    fig.innerHTML=`<img><figcaption>${i+1}.${ext(f.name)}${i===0?' · PORTADA':''}</figcaption>`;
    fig.querySelector('img').src=URL.createObjectURL(f);pv.appendChild(fig)
  })
}
$('#add-variant').onclick=()=>addVariant();

$('#new-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target);
  const meta={
    id:slug(fd.get('reference')),
    brand:String(fd.get('brand')).trim(),
    name:String(fd.get('name')).trim(),
    collection_id:fd.get('collection_id'),
    reference:String(fd.get('reference')).trim().toUpperCase(),
    price_cop:Number(fd.get('price_cop')),
    product_folder:String(fd.get('product_folder')).trim(),
    type:String(fd.get('type')||'').trim(),
    closure:String(fd.get('closure')||'').trim(),
    tags:String(fd.get('tags')||'').split(',').map(x=>x.trim()).filter(Boolean),
    description:String(fd.get('description')||'').trim(),
    active:true,
    variants:[]
  };
  const body=new FormData();
  [...variantsEl.children].forEach((el,i)=>{
    const files=[...el.querySelector('[data-field="images"]').files];
    const name=el.querySelector('[data-field="name"]').value.trim();
    meta.variants.push({
      client_key:`v${i+1}`,id:slug(name),name,
      color_hex:el.querySelector('[data-field="color_hex"]').value,
      folder:el.querySelector('[data-field="folder"]').value.trim(),
      sku:el.querySelector('[data-field="sku"]').value.trim(),
      unit_cost_cop:Number(el.querySelector('[data-field="unit_cost_cop"]').value||0),
      image_count:files.length,initial_stock:Number(el.querySelector('[data-field="initial_stock"]').value||0),active:true
    });
    files.forEach((f,j)=>body.append('files',f,`v${i+1}__${j+1}.${ext(f.name)}`))
  });
  body.append('metadata',JSON.stringify(meta));
  const status=$('#new-status');
  try{
    status.textContent='Guardando…';
    const r=await fetch('/api/admin/products',{method:'POST',body});
    const d=await r.json().catch(()=>({}));
    if(!r.ok)throw new Error(d.detail||`HTTP ${r.status}`);
    status.classList.remove('error');
    status.textContent=`Guardado correctamente: ${meta.reference}. Ya aparece en el catálogo local.`;
    e.target.reset();variantsEl.innerHTML='';addVariant();await load()
  }catch(err){status.classList.add('error');status.textContent=err.message}
});

function editProduct(id){
  const p=STATE.catalog.products.find(x=>x.id===id);if(!p)return;
  $('#edit-fields').innerHTML=`<input type="hidden" name="id" value="${esc(p.id)}"><div class="grid">
<label>Nombre<input name="name" value="${esc(p.name)}" required></label>
<label>Referencia<input name="reference" value="${esc(p.reference)}" required></label>
<label>Marca<input name="brand" value="${esc(p.brand)}" required></label>
<label>Colección><select name="collection_id">${STATE.catalog.collections.map(c=>`<option value="${esc(c.id)}" ${c.id===p.collection_id?'selected':''}>${esc(c.name)}</option>`).join('')}</select></label>
<label>Precio COP<input name="price_cop" type="number" min="0" value="${p.price_cop}" required></label>
<label>Tipo<input name="type" value="${esc(p.type||'')}"></label>
<label>Cierre<input name="closure" value="${esc(p.closure||'')}"></label>
<label>Etiquetas<input name="tags" value="${esc((p.tags||[]).join(', '))}"></label>
<label class="full">Descripción<textarea name="description">${esc(p.description||'')}</textarea></label>
</div><h3 style="margin-top:16px">Variantes</h3>
<div id="edit-variants">${(p.variants||[]).map(v=>`<div class="variant" data-id="${esc(v.id)}"><div class="grid">
<label>Nombre<input data-f="name" value="${esc(v.name)}"></label>
<label>Color<input data-f="color_hex" type="color" value="${esc(v.color_hex||'#111111')}"></label>
<label>Carpeta<input data-f="folder" value="${esc(v.folder||'')}"></label>
<label>SKU<input data-f="sku" value="${esc(v.sku||'')}"></label>
<label>Costo unitario COP<input data-f="unit_cost_cop" type="number" min="0" value="${v.unit_cost_cop||0}"></label>
</div></div>`).join('')}</div>`;
  $('#edit-status').textContent='';
  $('#edit-dialog').showModal()
}
window.editProduct=editProduct;
window.saveCollection=saveCollection;
window.saveStock=saveStock;
window.saveDiscount=saveDiscount;
window.refreshDiscountTarget=refreshDiscountTarget;

$('#edit-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const fd=new FormData(e.target),id=fd.get('id');
  const variants=[...document.querySelectorAll('#edit-variants .variant')].map(el=>({
    id:el.dataset.id,
    name:el.querySelector('[data-f="name"]').value.trim(),
    color_hex:el.querySelector('[data-f="color_hex"]').value,
    folder:el.querySelector('[data-f="folder"]').value.trim(),
    sku:el.querySelector('[data-f="sku"]').value.trim(),
    unit_cost_cop:Number(el.querySelector('[data-f="unit_cost_cop"]').value||0),
    active:true
  }));
  const body={
    brand:String(fd.get('brand')).trim(),
    name:String(fd.get('name')).trim(),
    collection_id:fd.get('collection_id'),
    reference:String(fd.get('reference')).trim().toUpperCase(),
    price_cop:Number(fd.get('price_cop')),
    description:String(fd.get('description')||'').trim(),
    tags:String(fd.get('tags')||'').split(',').map(x=>x.trim()).filter(Boolean),
    closure:String(fd.get('closure')||'').trim(),
    type:String(fd.get('type')||'').trim(),
    active:true,
    variants
  };
  try{
    await api(`/api/admin/products/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)});
    $('#edit-status').textContent='Guardado.';
    await load();
    setTimeout(()=>$('#edit-dialog').close(),350)
  }catch(err){$('#edit-status').textContent=err.message}
});

addVariant();
load().catch(e=>alert('No se pudo cargar el administrador: '+e.message));
