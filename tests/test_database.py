import pytest
import sqlite3
import os
from database import Database

def test_database_creation():
    db_path = 'test_db.sqlite'
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = Database(db_path)
    assert os.path.exists(db_path)
    
    db.insert_alert({
        'timestamp': '2026-10-02T12:00:00',
        'event_type': 'TEST_EVENT',
        'verified': True
    })
    
    alerts = db.get_alerts()
    assert len(alerts) == 1
    assert alerts[0]['event_type'] == 'TEST_EVENT'
    
    try:
        os.remove(db_path)
    except PermissionError:
        pass
