import time
import logging
from utils import intersect, is_point_in_polygon, distance

logger = logging.getLogger(__name__)

class RulesEngine:
    def __init__(self, config):
        self.config = config
        self.fence = self.config.get('zones', {}).get('fence', {})
        self.polygon = self.config.get('zones', {}).get('restricted_polygon', [])
        
        self.loiter_thresh = self.config.get('rules', {}).get('loiter_seconds', 10)
        self.abandon_thresh = self.config.get('rules', {}).get('abandoned_seconds', 10)
        self.abandon_move_px = self.config.get('rules', {}).get('abandoned_move_pixels', 20)
        self.abandon_dist_px = self.config.get('rules', {}).get('abandoned_person_distance_pixels', 150)
        
        # State
        self.history = {} # track_id -> [centers...]
        self.loiter_state = {} # track_id -> first_seen_time
        self.object_state = {} # track_id -> {'first_pos': (x,y), 'first_seen': time}
        
    def check_fence_crossing(self, track_id, current_center):
        if not self.fence: return None
        p1 = tuple(self.fence['p1'])
        p2 = tuple(self.fence['p2'])
        
        if track_id in self.history and len(self.history[track_id]) > 0:
            prev_center = self.history[track_id][-1]
            if intersect(prev_center, current_center, p1, p2):
                # Basic direction using Y coordinate for simplicity
                direction = "ENTER" if current_center[1] > prev_center[1] else "EXIT"
                return {"type": "FENCE_CROSSING", "direction": direction}
        
        if track_id not in self.history:
            self.history[track_id] = []
        self.history[track_id].append(current_center)
        # Keep history short
        if len(self.history[track_id]) > 5:
            self.history[track_id].pop(0)
            
        return None

    def check_loitering(self, track_id, current_center):
        if not self.polygon: return None
        
        in_poly = is_point_in_polygon(current_center, self.polygon)
        current_time = time.time()
        
        if in_poly:
            if track_id not in self.loiter_state:
                self.loiter_state[track_id] = current_time
            else:
                duration = current_time - self.loiter_state[track_id]
                if duration >= self.loiter_thresh:
                    return {"type": "LOITERING", "duration": duration}
        else:
            if track_id in self.loiter_state:
                del self.loiter_state[track_id]
        return None

    def check_abandoned(self, track_id, current_center, cls_name, all_people_centers):
        if cls_name not in ['backpack', 'handbag', 'suitcase']:
            return None
            
        current_time = time.time()
        if track_id not in self.object_state:
            self.object_state[track_id] = {'first_pos': current_center, 'first_seen': current_time}
            return None
            
        state = self.object_state[track_id]
        dist = distance(state['first_pos'], current_center)
        
        if dist > self.abandon_move_px:
            # Object moved, reset
            self.object_state[track_id] = {'first_pos': current_center, 'first_seen': current_time}
            return None
            
        duration = current_time - state['first_seen']
        if duration >= self.abandon_thresh:
            # Check proximity to people
            person_close = False
            for p_center in all_people_centers:
                if distance(current_center, p_center) < self.abandon_dist_px:
                    person_close = True
                    break
            
            if not person_close:
                return {"type": "ABANDONED_OBJECT", "stationary_seconds": duration, "object": cls_name}
                
        return None
