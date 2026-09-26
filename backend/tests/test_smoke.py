import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'backend'))
from app.db import init_db, connect
from app.ml_engine import recommendations, train_content_model, activate_latest_model, set_enabled
from app.analytics import analytics_summary

def test_db_migrates_catalog():
    init_db()
    with connect() as con:
        assert con.execute('SELECT COUNT(*) FROM products').fetchone()[0] >= 15
        assert con.execute('SELECT COUNT(*) FROM variants').fetchone()[0] >= 22

def test_analytics_structure():
    data=analytics_summary(30,True)
    assert 'kpis' in data and 'sessions' in data['kpis']

def test_ml_fallback_and_training():
    set_enabled(False)
    r=recommendations('',4)
    assert r['engine']=='fallback'
    trained=train_content_model()
    assert trained['metrics']['products'] >= 15
    assert activate_latest_model()
    set_enabled(True)
    r2=recommendations('adidas-colombia',4)
    assert r2['engine'] in {'ml','fallback'}
