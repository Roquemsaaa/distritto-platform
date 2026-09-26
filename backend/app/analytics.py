import json
from datetime import datetime, timedelta, timezone
from .db import connect, now_iso, get_setting

def _cutoff(days):
    return (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()

def _rate(a,b):
    return round((a/b*100),1) if b else 0.0

def analytics_summary(days=30, force=False):
    key=f"analytics:{days}"
    now=datetime.now(timezone.utc)
    with connect() as con:
        if not force:
            row=con.execute("SELECT payload_json,expires_at FROM cache_entries WHERE cache_key=?",(key,)).fetchone()
            if row:
                try:
                    if datetime.fromisoformat(row['expires_at'])>now:
                        payload=json.loads(row['payload_json']); payload['cache_hit']=True; return payload
                except Exception: pass
        cutoff=_cutoff(days)
        q=lambda sql,args=(): con.execute(sql,args).fetchone()[0]
        sessions=q("SELECT COUNT(DISTINCT session_id) FROM events WHERE occurred_at>=? AND session_id<>''",(cutoff,))
        visitors=q("SELECT COUNT(DISTINCT visitor_id) FROM events WHERE occurred_at>=? AND visitor_id<>''",(cutoff,))
        page_views=q("SELECT COUNT(*) FROM events WHERE occurred_at>=? AND event_type='page_view'",(cutoff,))
        product_views=q("SELECT COUNT(*) FROM events WHERE occurred_at>=? AND event_type='product_view'",(cutoff,))
        wa=q("SELECT COUNT(*) FROM events WHERE occurred_at>=? AND event_type='whatsapp_click'",(cutoff,))
        active_seconds=q("SELECT COALESCE(SUM(numeric_value),0) FROM events WHERE occurred_at>=? AND event_type='heartbeat'",(cutoff,))
        sales=q("SELECT COUNT(*) FROM sales WHERE sold_at>=?",(cutoff,))
        revenue=q("SELECT COALESCE(SUM(total_cop),0) FROM sales WHERE sold_at>=?",(cutoff,))
        gross_profit=q("SELECT COALESCE(SUM(total_cop-cost_cop),0) FROM sales WHERE sold_at>=?",(cutoff,))
        units=q("SELECT COALESCE(SUM(quantity),0) FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE s.sold_at>=?",(cutoff,))
        top_products=[dict(r) for r in con.execute("""SELECT e.product_id,p.name,p.reference,
            SUM(CASE WHEN e.event_type='product_view' THEN 1 ELSE 0 END) views,
            SUM(CASE WHEN e.event_type='whatsapp_click' THEN 1 ELSE 0 END) whatsapp_clicks
            FROM events e LEFT JOIN products p ON p.id=e.product_id
            WHERE e.occurred_at>=? AND e.product_id<>'' GROUP BY e.product_id ORDER BY views DESC LIMIT 10""",(cutoff,)).fetchall()]
        sources=[dict(r) for r in con.execute("""SELECT COALESCE(NULLIF(source,''),'Directo') source, COUNT(DISTINCT session_id) sessions
            FROM events WHERE occurred_at>=? AND event_type='page_view' GROUP BY COALESCE(NULLIF(source,''),'Directo') ORDER BY sessions DESC LIMIT 10""",(cutoff,)).fetchall()]
        devices=[dict(r) for r in con.execute("""SELECT COALESCE(NULLIF(device,''),'Desconocido') device, COUNT(DISTINCT session_id) sessions
            FROM events WHERE occurred_at>=? AND event_type='page_view' GROUP BY COALESCE(NULLIF(device,''),'Desconocido') ORDER BY sessions DESC""",(cutoff,)).fetchall()]
        colors=[dict(r) for r in con.execute("""SELECT e.product_id,e.variant_id,p.name product_name,v.name variant_name,COUNT(*) views
            FROM events e LEFT JOIN products p ON p.id=e.product_id LEFT JOIN variants v ON v.product_id=e.product_id AND v.id=e.variant_id
            WHERE e.occurred_at>=? AND e.event_type='variant_view' AND e.variant_id<>'' GROUP BY e.product_id,e.variant_id ORDER BY views DESC LIMIT 10""",(cutoff,)).fetchall()]
        payload={'days':days,'generated_at':now_iso(),'cache_hit':False,
          'kpis':{'sessions':sessions,'visitors':visitors,'page_views':page_views,'product_views':product_views,
                  'whatsapp_clicks':wa,'sales':sales,'units_sold':units,'revenue_cop':revenue,'gross_profit_cop':gross_profit,
                  'avg_active_seconds':round(active_seconds/sessions,1) if sessions else 0,
                  'product_view_rate':_rate(product_views,sessions),'whatsapp_rate':_rate(wa,product_views),'session_sale_rate':_rate(sales,sessions)},
          'top_products':top_products,'sources':sources,'devices':devices,'top_variants':colors}
        ttl=int(get_setting(con,'cache_seconds','60') or 60)
        expires=(now+timedelta(seconds=ttl)).isoformat()
        con.execute("INSERT INTO cache_entries(cache_key,payload_json,expires_at,created_at) VALUES(?,?,?,?) ON CONFLICT(cache_key) DO UPDATE SET payload_json=excluded.payload_json,expires_at=excluded.expires_at,created_at=excluded.created_at",(key,json.dumps(payload,ensure_ascii=False),expires,now_iso()))
        return payload

def invalidate_cache(prefix='analytics:'):
    with connect() as con:
        con.execute("DELETE FROM cache_entries WHERE cache_key LIKE ?",(prefix+'%',))
