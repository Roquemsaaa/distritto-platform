import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from .settings import Settings

settings = Settings()

def now_iso():
    return datetime.now(timezone.utc).isoformat()

@contextmanager
def connect():
    con = sqlite3.connect(settings.database_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS collections (id TEXT PRIMARY KEY, name TEXT NOT NULL, sort_order INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS products (
  id TEXT PRIMARY KEY, brand TEXT NOT NULL, name TEXT NOT NULL, collection_id TEXT NOT NULL,
  reference TEXT NOT NULL UNIQUE, price_cop INTEGER NOT NULL DEFAULT 0, description TEXT NOT NULL DEFAULT '',
  tags_json TEXT NOT NULL DEFAULT '[]', closure TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '',
  product_folder TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
  FOREIGN KEY(collection_id) REFERENCES collections(id)
);
CREATE TABLE IF NOT EXISTS variants (
  id TEXT NOT NULL, product_id TEXT NOT NULL, name TEXT NOT NULL, color_hex TEXT NOT NULL DEFAULT '#111111',
  folder TEXT NOT NULL DEFAULT '', sku TEXT NOT NULL DEFAULT '', unit_cost_cop INTEGER NOT NULL DEFAULT 0,
  active INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(product_id,id),
  FOREIGN KEY(product_id) REFERENCES products(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS product_images (
  id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, variant_id TEXT NOT NULL,
  path TEXT NOT NULL, position INTEGER NOT NULL, is_cover INTEGER NOT NULL DEFAULT 0,
  UNIQUE(product_id,variant_id,position),
  FOREIGN KEY(product_id,variant_id) REFERENCES variants(product_id,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inventory (
  product_id TEXT NOT NULL, variant_id TEXT NOT NULL, stock INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL, PRIMARY KEY(product_id,variant_id),
  FOREIGN KEY(product_id,variant_id) REFERENCES variants(product_id,id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS inventory_movements (
  id INTEGER PRIMARY KEY AUTOINCREMENT, product_id TEXT NOT NULL, variant_id TEXT NOT NULL,
  movement_type TEXT NOT NULL, quantity INTEGER NOT NULL, note TEXT NOT NULL DEFAULT '',
  reference_type TEXT NOT NULL DEFAULT '', reference_id TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS discounts (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, discount_type TEXT NOT NULL, value INTEGER NOT NULL,
  scope TEXT NOT NULL, target_id TEXT NOT NULL DEFAULT '', active INTEGER NOT NULL DEFAULT 1,
  starts_at TEXT, ends_at TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sold_at TEXT NOT NULL, channel TEXT NOT NULL DEFAULT 'Manual',
  customer_name TEXT NOT NULL DEFAULT '', customer_contact TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '',
  subtotal_cop INTEGER NOT NULL, discount_cop INTEGER NOT NULL DEFAULT 0, total_cop INTEGER NOT NULL,
  cost_cop INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, product_id TEXT NOT NULL, variant_id TEXT NOT NULL,
  product_name TEXT NOT NULL, variant_name TEXT NOT NULL, reference TEXT NOT NULL, quantity INTEGER NOT NULL,
  unit_price_cop INTEGER NOT NULL, unit_cost_cop INTEGER NOT NULL DEFAULT 0, line_total_cop INTEGER NOT NULL,
  FOREIGN KEY(sale_id) REFERENCES sales(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS production_batches (
  id INTEGER PRIMARY KEY AUTOINCREMENT, produced_at TEXT NOT NULL, product_id TEXT NOT NULL, variant_id TEXT NOT NULL,
  units_planned INTEGER NOT NULL DEFAULT 0, units_produced INTEGER NOT NULL DEFAULT 0, waste_units INTEGER NOT NULL DEFAULT 0,
  labor_cost_cop INTEGER NOT NULL DEFAULT 0, other_cost_cop INTEGER NOT NULL DEFAULT 0,
  material_cost_cop INTEGER NOT NULL DEFAULT 0, total_cost_cop INTEGER NOT NULL DEFAULT 0,
  unit_cost_cop REAL NOT NULL DEFAULT 0, yield_pct REAL NOT NULL DEFAULT 0, notes TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS production_inputs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, batch_id INTEGER NOT NULL, material_name TEXT NOT NULL,
  unit TEXT NOT NULL DEFAULT 'unidad', quantity REAL NOT NULL DEFAULT 0, unit_cost_cop REAL NOT NULL DEFAULT 0,
  line_cost_cop REAL NOT NULL DEFAULT 0, FOREIGN KEY(batch_id) REFERENCES production_batches(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, event_type TEXT NOT NULL, occurred_at TEXT NOT NULL,
  visitor_id TEXT NOT NULL DEFAULT '', session_id TEXT NOT NULL DEFAULT '', product_id TEXT NOT NULL DEFAULT '',
  variant_id TEXT NOT NULL DEFAULT '', collection_id TEXT NOT NULL DEFAULT '', source TEXT NOT NULL DEFAULT '',
  medium TEXT NOT NULL DEFAULT '', campaign TEXT NOT NULL DEFAULT '', referrer TEXT NOT NULL DEFAULT '',
  device TEXT NOT NULL DEFAULT '', page TEXT NOT NULL DEFAULT '', numeric_value REAL NOT NULL DEFAULT 0,
  metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_product ON events(product_id);
CREATE TABLE IF NOT EXISTS cache_entries (cache_key TEXT PRIMARY KEY, payload_json TEXT NOT NULL, expires_at TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ml_models (
  id INTEGER PRIMARY KEY AUTOINCREMENT, version TEXT NOT NULL UNIQUE, algorithm TEXT NOT NULL,
  artifact_json TEXT NOT NULL, metrics_json TEXT NOT NULL DEFAULT '{}', trained_at TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS audit_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL DEFAULT '', detail_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL
);
"""

def _setting(con, key, default):
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    if row is None:
        con.execute("INSERT INTO settings(key,value) VALUES(?,?)", (key, str(default)))
        return str(default)
    return row['value']

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
        _setting(con, 'few_units_max', '2')
        _setting(con, 'ml_enabled', '0')
        _setting(con, 'analytics_enabled', '1')
        _setting(con, 'heartbeat_seconds', '30')
        _setting(con, 'cache_seconds', str(settings.analytics_cache_seconds))
        count = con.execute("SELECT COUNT(*) c FROM products").fetchone()['c']
        if count == 0:
            migrate_json(con)

def migrate_json(con):
    catalog_path = settings.site_root/'data'/'catalog.json'
    inv_path = settings.site_root/'data'/'inventory.json'
    disc_path = settings.site_root/'data'/'discounts.json'
    if not catalog_path.exists(): return
    catalog = json.loads(catalog_path.read_text(encoding='utf-8'))
    inv = json.loads(inv_path.read_text(encoding='utf-8')) if inv_path.exists() else {'items':{}}
    disc = json.loads(disc_path.read_text(encoding='utf-8')) if disc_path.exists() else {'rules':[]}
    for i,c in enumerate(catalog.get('collections', [])):
        con.execute("INSERT OR IGNORE INTO collections(id,name,sort_order,active) VALUES(?,?,?,1)",(c['id'],c['name'],i))
    for p in catalog.get('products', []):
        t=now_iso()
        con.execute("""INSERT OR IGNORE INTO products(id,brand,name,collection_id,reference,price_cop,description,tags_json,closure,type,product_folder,active,created_at,updated_at)
                       VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (p['id'],p.get('brand',''),p.get('name',''),p.get('collection_id',''),p.get('reference',''),int(p.get('price_cop',0)),p.get('description',''),json.dumps(p.get('tags',[]),ensure_ascii=False),p.get('closure',''),p.get('type',''),p.get('product_folder',''),1 if p.get('active',True) else 0,t,t))
        for v in p.get('variants', []):
            con.execute("""INSERT OR IGNORE INTO variants(id,product_id,name,color_hex,folder,sku,unit_cost_cop,active) VALUES(?,?,?,?,?,?,?,?)""",
                        (v['id'],p['id'],v.get('name',''),v.get('color_hex','#111111'),v.get('folder',''),v.get('sku',''),int(v.get('unit_cost_cop',0) or 0),1 if v.get('active',True) else 0))
            for pos,img in enumerate(v.get('images',[]),1):
                con.execute("INSERT OR IGNORE INTO product_images(product_id,variant_id,path,position,is_cover) VALUES(?,?,?,?,?)",(p['id'],v['id'],img,pos,1 if pos==1 else 0))
            key=f"{p['id']}::{v['id']}"
            stock = inv.get('items',{}).get(key,{}).get('stock',0)
            con.execute("INSERT OR IGNORE INTO inventory(product_id,variant_id,stock,updated_at) VALUES(?,?,?,?)",(p['id'],v['id'],int(stock or 0),t))
    for r in disc.get('rules',[]):
        con.execute("""INSERT OR IGNORE INTO discounts(id,name,discount_type,value,scope,target_id,active,starts_at,ends_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                    (r['id'],r.get('name',''),r.get('discount_type','percentage'),int(r.get('value',0)),r.get('scope','product'),r.get('target_id',''),1 if r.get('active',True) else 0,r.get('starts_at'),r.get('ends_at'),now_iso()))

def audit(con, action, entity_type, entity_id='', detail=None):
    con.execute("INSERT INTO audit_logs(action,entity_type,entity_id,detail_json,created_at) VALUES(?,?,?,?,?)",
                (action,entity_type,str(entity_id),json.dumps(detail or {},ensure_ascii=False),now_iso()))

def get_setting(con, key, default=''):
    row=con.execute("SELECT value FROM settings WHERE key=?",(key,)).fetchone()
    return row['value'] if row else str(default)

def set_setting(con,key,value):
    con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(key,str(value)))
