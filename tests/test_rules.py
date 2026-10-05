import pytest
from rules import RulesEngine

@pytest.fixture
def config():
    return {
        'zones': {
            'fence': {'p1': [100, 200], 'p2': [500, 200]},
            'restricted_polygon': [[200, 150], [600, 150], [600, 450], [200, 450]]
        },
        'rules': {
            'loiter_seconds': 2,
            'abandoned_seconds': 2,
            'abandoned_move_pixels': 20,
            'abandoned_person_distance_pixels': 150
        }
    }

def test_fence_crossing(config):
    rules = RulesEngine(config)
    # Move near but outside
    assert rules.check_fence_crossing(1, (50, 150)) is None
    assert rules.check_fence_crossing(1, (50, 250)) is None
    
    # Left to right crossing
    assert rules.check_fence_crossing(2, (300, 150)) is None
    event = rules.check_fence_crossing(2, (300, 250))
    assert event is not None
    assert event['type'] == 'FENCE_CROSSING'
    
def test_loitering(config):
    import time
    rules = RulesEngine(config)
    
    # Inside zone
    assert rules.check_loitering(1, (300, 300)) is None
    
    # Hack time to simulate duration
    rules.loiter_state[1] = time.time() - 3
    event = rules.check_loitering(1, (300, 310))
    assert event is not None
    assert event['type'] == 'LOITERING'
    
def test_abandoned_object(config):
    import time
    rules = RulesEngine(config)
    
    # Backpack appears
    assert rules.check_abandoned(1, (100, 100), 'backpack', [(200, 200)]) is None
    
    # Simulate time passed and person moves away
    rules.object_state[1]['first_seen'] = time.time() - 3
    event = rules.check_abandoned(1, (100, 100), 'backpack', [(500, 500)])
    assert event is not None
    assert event['type'] == 'ABANDONED_OBJECT'
