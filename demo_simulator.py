import time
import json
from rules import RulesEngine
from alerts import AlertManager
from database import Database
from config_loader import load_config
from utils import get_current_timestamp

def simulate():
    print("Starting Demo Simulator...")
    config = load_config()
    db = Database(config.get('database', {}).get('path', 'data/sentinel.db'))
    rules = RulesEngine(config)
    alert_mgr = AlertManager(config, db)
    
    # 1. Fence Crossing Simulator
    print("Simulating Fence Crossing...")
    # Fence is at Y=200. Cross from (300, 150) to (300, 250)
    rules.check_fence_crossing(1, (300, 150))
    event = rules.check_fence_crossing(1, (300, 250))
    if event:
        event['track_id'] = 1
        event['object_class'] = 'person'
        alert_mgr.verify_and_generate(event, 5, 0.85)
        print(f"Generated Fence Alert: {event}")
        
    # 2. Loitering Simulator
    print("Simulating Loitering...")
    # Polygon is 200,150 to 600,450
    rules.check_loitering(2, (300, 300))
    # Hack the state to simulate time passed
    rules.loiter_state[2] = time.time() - 15
    event = rules.check_loitering(2, (300, 310))
    if event:
        event['track_id'] = 2
        event['object_class'] = 'person'
        alert_mgr.verify_and_generate(event, 10, 0.90)
        print(f"Generated Loitering Alert: {event}")
        
    # 3. Abandoned Object Simulator
    print("Simulating Abandoned Object...")
    rules.check_abandoned(3, (400, 400), 'backpack', [(100, 100)])
    rules.object_state[3]['first_seen'] = time.time() - 15
    event = rules.check_abandoned(3, (400, 400), 'backpack', [(100, 100)]) # Person far away
    if event:
        event['track_id'] = 3
        event['object_class'] = 'backpack'
        alert_mgr.verify_and_generate(event, 20, 0.75)
        print(f"Generated Abandoned Object Alert: {event}")

    # 4. Suppression Simulator
    print("Simulating Suppressed Event (Low Conf)...")
    event = {'type': 'FENCE_CROSSING', 'direction': 'ENTER', 'track_id': 4, 'object_class': 'person'}
    alert_mgr.verify_and_generate(event, 5, 0.20)
    print("Simulation Complete. Check Dashboard.")

if __name__ == '__main__':
    simulate()
