import pytest
import sqlite3
import os
from alerts import AlertManager
from database import Database

@pytest.fixture
def test_db():
    db_path = 'test_data.db'
    if os.path.exists(db_path):
        os.remove(db_path)
    db = Database(db_path)
    yield db
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass

@pytest.fixture
def config():
    return {
        'model': {'confidence': 0.40},
        'verification': {'min_track_age': 3, 'cooldown_seconds': 2}
    }

def test_verify_and_generate(config, test_db):
    am = AlertManager(config, test_db)
    
    event = {'type': 'FENCE_CROSSING', 'direction': 'ENTER', 'track_id': 1}
    
    # Test valid
    alert = am.verify_and_generate(event, track_age=5, confidence=0.8)
    assert alert['verified'] is True
    
    # Test low confidence
    alert = am.verify_and_generate(event, track_age=5, confidence=0.2)
    assert alert['verified'] is False
    assert alert['suppression_reason'] == 'LOW_CONFIDENCE'
    
    # Test short track
    alert = am.verify_and_generate(event, track_age=1, confidence=0.8)
    assert alert['verified'] is False
    assert alert['suppression_reason'] == 'TRACK_TOO_SHORT'
