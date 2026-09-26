import json, mimetypes, re
from pathlib import Path
from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .settings import Settings
from .db import connect, init_db, now_iso, audit, get_setting, set_setting
from .models import *
from .analytics import analytics_summary, invalidate_cache
from .ml_engine import recommendations, train_content_model, activate_latest_model, set_enabled as set_ml_enabled, status as ml_status

settings=Settings(); init_db()
app=FastAPI(title='DISTRITTO Digital Platform API',version='1.0.0')
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=False,allow_methods=['*'],allow_headers=['*'])
ALLOWED_IMAGE_TYPES={'image/png','image/jpeg','image/webp'}
UPLOAD_NAME=re.compile(r'^(v\d+)__(\d+)\.(jpg|jpeg|png|webp)$',re.I)

def require_admin(key):
    if settings.storage_mode=='local': return
    if not settings.admin_api_key or key!=settings.admin_api_key: raise HTTPException(401,'Credenciales de administración inválidas')

def stock_status(stock, few):
    if stock<=0:return 'Agotado'
    if stock==1:return 'Última unidad'
    if stock<=few:return 'Pocas unidades'
    return 'Disponible'

def public_state():
    with connect() as con:
        cols=[dict(r) for r in con.execute("SELECT id,name FROM collections WHERE active=1 ORDER BY sort_order,name").fetchall()]
        for c in cols:
            c['product_ids']=[r['id'] for r in con.execute("SELECT id FROM products WHERE collection_id=? AND active=1 ORDER BY created_at,id",(c['id'],)).fetchall()]
        products=[]
        for p in con.execute("SELECT * FROM products WHERE active=1 ORDER BY created_at,id").fetchall():
            d=dict(p); d['tags']=json.loads(d.pop('tags_json') or '[]'); d['active']=bool(d['active']); d['variants']=[]
            for v in con.execute("SELECT * FROM variants WHERE product_id=? AND active=1 ORDER BY rowid",(p['id'],)).fetchall():
                vd=dict(v); vd['active']=bool(vd['active']); vd['images']=[r['path'] for r in con.execute("SELECT path FROM product_images WHERE product_id=? AND variant_id=? ORDER BY position",(p['id'],v['id'])).fetchall()]; d['variants'].append(vd)
            products.append(d)
        inv={f"{r['product_id']}::{r['variant_id']}":{'product_id':r['product_id'],'variant_id':r['variant_id'],'stock':r['stock']} for r in con.execute("SELECT * FROM inventory").fetchall()}
        discounts=[dict(r) for r in con.execute("SELECT * FROM discounts WHERE active=1").fetchall()]
        for r in discounts:r['active']=bool(r['active'])
        st={'few_units_max':int(get_setting(con,'few_units_max','2')),'analytics_enabled':get_setting(con,'analytics_enabled','1')=='1','ml_enabled':get_setting(con,'ml_enabled','0')=='1'}
        return {'catalog':{'schema_version':2,'currency':'COP','collections':cols,'products':products},'inventory':{'items':inv},'discounts':{'rules':discounts},'settings':st}

@app.get('/health')
def health(): return {'status':'ok','version':'1.0.0','storage_mode':settings.storage_mode}
@app.get('/api/public/state')
def get_public_state(): return public_state()
@app.get('/api/recommendations')
def get_recommendations(product_id:str='',limit:int=4): return recommendations(product_id,max(1,min(limit,12)))

@app.post('/api/events')
def event(body:EventIn):
    with connect() as con:
        if get_setting(con,'analytics_enabled','1')!='1': return {'ok':True,'stored':False}
        con.execute("""INSERT INTO events(event_type,occurred_at,visitor_id,session_id,product_id,variant_id,collection_id,source,medium,campaign,referrer,device,page,numeric_value,metadata_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
          (body.event_type,body.occurred_at or now_iso(),body.visitor_id,body.session_id,body.product_id,body.variant_id,body.collection_id,body.source,body.medium,body.campaign,body.referrer[:500],body.device,body.page[:500],body.numeric_value,json.dumps(body.metadata,ensure_ascii=False)))
    return {'ok':True,'stored':True}

@app.get('/api/admin/state')
def admin_state(x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    state=public_state()
    with connect() as con:
        state['sales']=[dict(r) for r in con.execute("SELECT * FROM sales ORDER BY id DESC LIMIT 100").fetchall()]
        state['production']=[dict(r) for r in con.execute("SELECT * FROM production_batches ORDER BY id DESC LIMIT 100").fetchall()]
        state['settings']['cache_seconds']=int(get_setting(con,'cache_seconds','60'))
        state['discounts']={'rules':[dict(r) for r in con.execute("SELECT * FROM discounts ORDER BY created_at DESC").fetchall()]}
        for r in state['discounts']['rules']: r['active']=bool(r['active'])
    state['ml']=ml_status(); return state

@app.post('/api/admin/products')
async def create_product(metadata:str=Form(...),files:list[UploadFile]=File(...),x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    try: m=json.loads(metadata)
    except Exception: raise HTTPException(422,'Metadata inválida')
    required=['id','brand','name','collection_id','reference','price_cop','product_folder','variants']
    if any(k not in m for k in required): raise HTTPException(422,'Faltan datos obligatorios')
    with connect() as con:
        if con.execute("SELECT 1 FROM products WHERE id=? OR UPPER(reference)=UPPER(?)",(m['id'],m['reference'])).fetchone(): raise HTTPException(409,'La referencia ya existe')
        if not con.execute("SELECT 1 FROM collections WHERE id=?",(m['collection_id'],)).fetchone(): raise HTTPException(422,'La colección no existe')
        t=now_iso(); con.execute("""INSERT INTO products(id,brand,name,collection_id,reference,price_cop,description,tags_json,closure,type,product_folder,active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(m['id'],m['brand'],m['name'],m['collection_id'],m['reference'].upper(),int(m['price_cop']),m.get('description',''),json.dumps(m.get('tags',[]),ensure_ascii=False),m.get('closure',''),m.get('type',''),m['product_folder'],1,t,t))
        variant_by_key={v['client_key']:v for v in m['variants']}; grouped={k:[] for k in variant_by_key}
        for upload in files:
            mt=UPLOAD_NAME.fullmatch(upload.filename or '')
            if not mt: raise HTTPException(422,f'Archivo inválido: {upload.filename}')
            key,order,ext=mt.groups(); v=variant_by_key.get(key)
            if not v: raise HTTPException(422,'Archivo sin variante')
            data=await upload.read(); ctype=upload.content_type or mimetypes.guess_type(upload.filename or '')[0]
            if ctype not in ALLOWED_IMAGE_TYPES: raise HTTPException(415,'Formato de imagen no permitido')
            ext='jpg' if ext.lower()=='jpeg' else ext.lower(); rel=Path('catalogo')/m['product_folder']/v['folder']/f'{int(order)}.{ext}'; dest=settings.site_root/rel; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data); grouped[key].append((int(order),rel.as_posix()))
        for v in m['variants']:
            con.execute("INSERT INTO variants(id,product_id,name,color_hex,folder,sku,unit_cost_cop,active) VALUES(?,?,?,?,?,?,?,1)",(v['id'],m['id'],v['name'],v.get('color_hex','#111111'),v.get('folder',''),v.get('sku',''),int(v.get('unit_cost_cop',0) or 0)))
            imgs=sorted(grouped.get(v['client_key'],[])); expected=list(range(1,int(v.get('image_count',0))+1))
            if [n for n,_ in imgs]!=expected: raise HTTPException(422,f"Las fotos de {v['name']} deben ser 1..n")
            for pos,path in imgs: con.execute("INSERT INTO product_images(product_id,variant_id,path,position,is_cover) VALUES(?,?,?,?,?)",(m['id'],v['id'],path,pos,1 if pos==1 else 0))
            initial=int(v.get('initial_stock',0) or 0); con.execute("INSERT INTO inventory(product_id,variant_id,stock,updated_at) VALUES(?,?,?,?)",(m['id'],v['id'],initial,t))
            if initial: con.execute("INSERT INTO inventory_movements(product_id,variant_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?)",(m['id'],v['id'],'initial_stock',initial,'Stock inicial',t))
        audit(con,'create','product',m['id'],{'reference':m['reference']})
    return {'ok':True,'id':m['id']}

@app.put('/api/admin/products/{product_id}')
def update_product(product_id:str,body:ProductUpdate,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con:
        if not con.execute("SELECT 1 FROM products WHERE id=?",(product_id,)).fetchone(): raise HTTPException(404,'Producto no encontrado')
        con.execute("""UPDATE products SET brand=?,name=?,collection_id=?,reference=?,price_cop=?,description=?,tags_json=?,closure=?,type=?,active=?,updated_at=? WHERE id=?""",(body.brand,body.name,body.collection_id,body.reference.upper(),body.price_cop,body.description,json.dumps(body.tags,ensure_ascii=False),body.closure,body.type,1 if body.active else 0,now_iso(),product_id))
        for v in body.variants:
            con.execute("""UPDATE variants SET name=?,color_hex=?,folder=?,sku=?,unit_cost_cop=?,active=? WHERE product_id=? AND id=?""",(v.name,v.color_hex,v.folder,v.sku,v.unit_cost_cop,1 if v.active else 0,product_id,v.id))
        audit(con,'update','product',product_id)
    return {'ok':True}

@app.post('/api/admin/collections')
def add_collection(body:CollectionIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con:
        try: con.execute("INSERT INTO collections(id,name,sort_order,active) VALUES(?,?,(SELECT COALESCE(MAX(sort_order),0)+1 FROM collections),1)",(body.id,body.name))
        except Exception: raise HTTPException(409,'La colección ya existe')
        audit(con,'create','collection',body.id)
    return {'ok':True}
@app.put('/api/admin/collections/{collection_id}')
def edit_collection(collection_id:str,body:CollectionUpdate,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con: con.execute("UPDATE collections SET name=? WHERE id=?",(body.name,collection_id)); audit(con,'update','collection',collection_id)
    return {'ok':True}

@app.post('/api/admin/inventory')
def set_inventory(body:InventorySet,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con:
        row=con.execute("SELECT stock FROM inventory WHERE product_id=? AND variant_id=?",(body.product_id,body.variant_id)).fetchone(); old=row['stock'] if row else 0; delta=body.stock-old
        con.execute("INSERT INTO inventory(product_id,variant_id,stock,updated_at) VALUES(?,?,?,?) ON CONFLICT(product_id,variant_id) DO UPDATE SET stock=excluded.stock,updated_at=excluded.updated_at",(body.product_id,body.variant_id,body.stock,now_iso()))
        if delta: con.execute("INSERT INTO inventory_movements(product_id,variant_id,movement_type,quantity,note,created_at) VALUES(?,?,?,?,?,?)",(body.product_id,body.variant_id,'adjustment',delta,body.note,now_iso()))
        few=int(get_setting(con,'few_units_max','2')); audit(con,'set','inventory',f'{body.product_id}:{body.variant_id}',{'old':old,'new':body.stock})
    return {'ok':True,'status':stock_status(body.stock,few)}

@app.post('/api/admin/discounts')
def add_discount(body:DiscountIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    if body.discount_type not in {'percentage','fixed'} or body.scope not in {'all','collection','product'}: raise HTTPException(422,'Regla de descuento inválida')
    with connect() as con:
        con.execute("INSERT INTO discounts(id,name,discount_type,value,scope,target_id,active,starts_at,ends_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(body.id,body.name,body.discount_type,body.value,body.scope,body.target_id,1 if body.active else 0,body.starts_at,body.ends_at,now_iso())); audit(con,'create','discount',body.id)
    return {'ok':True}
@app.put('/api/admin/discounts/{discount_id}')
def edit_discount(discount_id:str,body:DiscountIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con:
        con.execute("UPDATE discounts SET name=?,discount_type=?,value=?,scope=?,target_id=?,active=?,starts_at=?,ends_at=? WHERE id=?",(body.name,body.discount_type,body.value,body.scope,body.target_id,1 if body.active else 0,body.starts_at,body.ends_at,discount_id)); audit(con,'update','discount',discount_id)
    return {'ok':True}

@app.post('/api/admin/sales')
def add_sale(body:SaleIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    if not body.items: raise HTTPException(422,'La venta no tiene productos')
    with connect() as con:
        subtotal=0;cost=0;resolved=[]
        for item in body.items:
            row=con.execute("""SELECT p.name,p.reference,v.name variant_name,v.unit_cost_cop,i.stock FROM products p JOIN variants v ON v.product_id=p.id JOIN inventory i ON i.product_id=v.product_id AND i.variant_id=v.id WHERE p.id=? AND v.id=?""",(item.product_id,item.variant_id)).fetchone()
            if not row: raise HTTPException(404,'Producto/variante no encontrado')
            if row['stock']<item.quantity: raise HTTPException(409,f"Stock insuficiente para {row['name']} - {row['variant_name']}")
            line=item.quantity*item.unit_price_cop; subtotal+=line; cost+=item.quantity*row['unit_cost_cop']; resolved.append((item,row,line))
        total=max(0,subtotal-body.discount_cop); sold_at=body.sold_at or now_iso()
        cur=con.execute("INSERT INTO sales(sold_at,channel,customer_name,customer_contact,notes,subtotal_cop,discount_cop,total_cop,cost_cop,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",(sold_at,body.channel,body.customer_name,body.customer_contact,body.notes,subtotal,body.discount_cop,total,cost,now_iso())); sale_id=cur.lastrowid
        for item,row,line in resolved:
            con.execute("INSERT INTO sale_items(sale_id,product_id,variant_id,product_name,variant_name,reference,quantity,unit_price_cop,unit_cost_cop,line_total_cop) VALUES(?,?,?,?,?,?,?,?,?,?)",(sale_id,item.product_id,item.variant_id,row['name'],row['variant_name'],row['reference'],item.quantity,item.unit_price_cop,row['unit_cost_cop'],line))
            con.execute("UPDATE inventory SET stock=stock-?,updated_at=? WHERE product_id=? AND variant_id=?",(item.quantity,now_iso(),item.product_id,item.variant_id))
            con.execute("INSERT INTO inventory_movements(product_id,variant_id,movement_type,quantity,note,reference_type,reference_id,created_at) VALUES(?,?,?,?,?,?,?,?)",(item.product_id,item.variant_id,'sale',-item.quantity,'Venta','sale',str(sale_id),now_iso()))
        audit(con,'create','sale',sale_id,{'total':total})
    invalidate_cache(); return {'ok':True,'sale_id':sale_id,'total_cop':total}

@app.post('/api/admin/production')
def add_production(body:ProductionIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    material=sum(x.quantity*x.unit_cost_cop for x in body.inputs); total=round(material+body.labor_cost_cop+body.other_cost_cop); unit=total/body.units_produced if body.units_produced else 0; denom=body.units_produced+body.waste_units; yield_pct=body.units_produced/denom*100 if denom else 100
    with connect() as con:
        if not con.execute("SELECT 1 FROM variants WHERE product_id=? AND id=?",(body.product_id,body.variant_id)).fetchone(): raise HTTPException(404,'Variante no encontrada')
        cur=con.execute("INSERT INTO production_batches(produced_at,product_id,variant_id,units_planned,units_produced,waste_units,labor_cost_cop,other_cost_cop,material_cost_cop,total_cost_cop,unit_cost_cop,yield_pct,notes,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(body.produced_at or now_iso(),body.product_id,body.variant_id,body.units_planned,body.units_produced,body.waste_units,body.labor_cost_cop,body.other_cost_cop,round(material),total,unit,yield_pct,body.notes,now_iso())); bid=cur.lastrowid
        for x in body.inputs: con.execute("INSERT INTO production_inputs(batch_id,material_name,unit,quantity,unit_cost_cop,line_cost_cop) VALUES(?,?,?,?,?,?)",(bid,x.material_name,x.unit,x.quantity,x.unit_cost_cop,x.quantity*x.unit_cost_cop))
        con.execute("UPDATE inventory SET stock=stock+?,updated_at=? WHERE product_id=? AND variant_id=?",(body.units_produced,now_iso(),body.product_id,body.variant_id))
        con.execute("INSERT INTO inventory_movements(product_id,variant_id,movement_type,quantity,note,reference_type,reference_id,created_at) VALUES(?,?,?,?,?,?,?,?)",(body.product_id,body.variant_id,'production_in',body.units_produced,'Producción','production',str(bid),now_iso()))
        audit(con,'create','production',bid,{'unit_cost':unit,'yield_pct':yield_pct})
    return {'ok':True,'batch_id':bid,'total_cost_cop':total,'unit_cost_cop':round(unit,2),'yield_pct':round(yield_pct,1)}

@app.get('/api/admin/analytics')
def admin_analytics(days:int=30,force:bool=False,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key); return analytics_summary(max(1,min(days,3650)),force)
@app.post('/api/admin/cache/invalidate')
def cache_invalidate(x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key); invalidate_cache(); return {'ok':True}
@app.get('/api/admin/ml/status')
def ml_get_status(x_admin_key:str|None=Header(default=None)): require_admin(x_admin_key); return ml_status()
@app.post('/api/admin/ml/train')
def ml_train(x_admin_key:str|None=Header(default=None)): require_admin(x_admin_key); return train_content_model()
@app.post('/api/admin/ml/activate-latest')
def ml_activate(x_admin_key:str|None=Header(default=None)): require_admin(x_admin_key); return {'ok':True,'version':activate_latest_model()}
@app.post('/api/admin/ml/toggle/{enabled}')
def ml_toggle(enabled:bool,x_admin_key:str|None=Header(default=None)): require_admin(x_admin_key); set_ml_enabled(enabled); return {'ok':True,'enabled':enabled}
@app.put('/api/admin/settings')
def update_settings(body:SettingsIn,x_admin_key:str|None=Header(default=None)):
    require_admin(x_admin_key)
    with connect() as con:
        set_setting(con,'few_units_max',body.few_units_max); set_setting(con,'analytics_enabled','1' if body.analytics_enabled else '0'); set_setting(con,'cache_seconds',body.cache_seconds); audit(con,'update','settings','global',body.model_dump())
    invalidate_cache(); return {'ok':True}

app.mount('/',StaticFiles(directory=settings.site_root,html=True),name='site')
