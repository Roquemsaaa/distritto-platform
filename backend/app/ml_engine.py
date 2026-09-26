import json, math
from collections import defaultdict
from datetime import datetime, timezone
from .db import connect, now_iso, get_setting, set_setting, audit

def _features(con):
    rows=con.execute("""SELECT p.id,p.brand,p.collection_id,p.type,p.closure,GROUP_CONCAT(v.name,'|') colors
        FROM products p LEFT JOIN variants v ON v.product_id=p.id AND v.active=1 WHERE p.active=1 GROUP BY p.id""").fetchall()
    return {r['id']:{'brand':r['brand'] or '', 'collection':r['collection_id'] or '', 'type':r['type'] or '', 'closure':r['closure'] or '', 'colors':set((r['colors'] or '').split('|'))-set([''])} for r in rows}

def train_content_model():
    with connect() as con:
        feats=_features(con); coview=defaultdict(lambda:defaultdict(int))
        sessions=con.execute("SELECT session_id, GROUP_CONCAT(DISTINCT product_id) ids FROM events WHERE product_id<>'' AND session_id<>'' GROUP BY session_id").fetchall()
        for s in sessions:
            ids=[x for x in (s['ids'] or '').split(',') if x]
            for a in ids:
                for b in ids:
                    if a!=b: coview[a][b]+=1
        artifact={}
        for a,fa in feats.items():
            scored=[]
            for b,fb in feats.items():
                if a==b: continue
                score=(3 if fa['collection']==fb['collection'] else 0)+(2 if fa['brand']==fb['brand'] else 0)+(1 if fa['type'] and fa['type']==fb['type'] else 0)+(0.5 if fa['closure'] and fa['closure']==fb['closure'] else 0)+(0.75 if fa['colors'] & fb['colors'] else 0)+min(2.0,math.log1p(coview[a].get(b,0)))
                scored.append((score,b))
            artifact[a]=[b for score,b in sorted(scored,reverse=True) if score>0][:12]
        version='content-'+datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
        metrics={'products':len(feats),'sessions_used':len(sessions),'coverage_pct':round(sum(1 for v in artifact.values() if v)/max(1,len(artifact))*100,1)}
        con.execute("INSERT INTO ml_models(version,algorithm,artifact_json,metrics_json,trained_at,is_active) VALUES(?,?,?,?,?,0)",(version,'content+coview-v1',json.dumps(artifact),json.dumps(metrics),now_iso()))
        audit(con,'train','ml_model',version,metrics)
        return {'version':version,'algorithm':'content+coview-v1','metrics':metrics}

def activate_latest_model():
    with connect() as con:
        row=con.execute("SELECT id,version FROM ml_models ORDER BY id DESC LIMIT 1").fetchone()
        if not row: return None
        con.execute("UPDATE ml_models SET is_active=0"); con.execute("UPDATE ml_models SET is_active=1 WHERE id=?",(row['id'],)); audit(con,'activate','ml_model',row['version']); return row['version']

def set_enabled(enabled: bool):
    with connect() as con:
        set_setting(con,'ml_enabled','1' if enabled else '0'); audit(con,'toggle','ml','enabled',{'enabled':enabled})

def status():
    with connect() as con:
        enabled=get_setting(con,'ml_enabled','0')=='1'; row=con.execute("SELECT version,algorithm,metrics_json,trained_at FROM ml_models WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
        return {'enabled':enabled,'active_model':dict(row) if row else None,'models':[dict(r) for r in con.execute("SELECT version,algorithm,metrics_json,trained_at,is_active FROM ml_models ORDER BY id DESC LIMIT 10").fetchall()]}

def _fallback(con, product_id, limit):
    base=con.execute("SELECT collection_id,brand,type FROM products WHERE id=?",(product_id,)).fetchone() if product_id else None
    if base:
        rows=con.execute("""SELECT id,name,reference FROM products WHERE active=1 AND id<>? ORDER BY (collection_id=?)*4 + (brand=?)*2 + (type=?)*1 DESC, name LIMIT ?""",(product_id,base['collection_id'],base['brand'],base['type'],limit)).fetchall()
    else:
        rows=con.execute("""SELECT p.id,p.name,p.reference,COUNT(e.id) n FROM products p LEFT JOIN events e ON e.product_id=p.id AND e.event_type='product_view' WHERE p.active=1 GROUP BY p.id ORDER BY n DESC,p.name LIMIT ?""",(limit,)).fetchall()
    return [dict(r) for r in rows]

def recommendations(product_id='', limit=4):
    with connect() as con:
        if get_setting(con,'ml_enabled','0')=='1':
            try:
                row=con.execute("SELECT artifact_json,version FROM ml_models WHERE is_active=1 ORDER BY id DESC LIMIT 1").fetchone()
                if row:
                    ids=json.loads(row['artifact_json']).get(product_id,[])[:limit]
                    if ids:
                        qs=','.join('?'*len(ids)); data={r['id']:dict(r) for r in con.execute(f"SELECT id,name,reference FROM products WHERE id IN ({qs})",ids).fetchall()}
                        return {'engine':'ml','model_version':row['version'],'items':[data[i] for i in ids if i in data]}
            except Exception:
                pass
        return {'engine':'fallback','model_version':None,'items':_fallback(con,product_id,limit)}
