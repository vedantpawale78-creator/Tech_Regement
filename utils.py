import cv2
import math
import numpy as np
from datetime import datetime

def is_point_in_polygon(point, polygon):
    # point: (x, y)
    # polygon: list of (x, y)
    pts = np.array(polygon, np.int32)
    result = cv2.pointPolygonTest(pts, (float(point[0]), float(point[1])), False)
    return result >= 0

def ccw(A, B, C):
    return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])

def intersect(A, B, C, D):
    return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

def get_current_timestamp():
    return datetime.now().isoformat()

def distance(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
