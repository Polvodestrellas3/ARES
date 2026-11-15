"""Terrain and EVA planning calculations. Python standard library only.
Mobility and autonomy are editable assumptions, not NASA data.
"""
import math
from bisect import bisect_right

# Illustrative slope thresholds, not certified operational limits.
BANDS = [(5, '#48be91', 'Low'), (10, '#f1d65c', 'Moderate'),
         (15, '#f39a55', 'High'), (math.inf, '#ef6471', 'Very high')]


def slope_band(angle):
    return next((color, label) for limit, color, label in BANDS if abs(angle) < limit)


def segments(route):
    """Mean slope per sampling interval (degrees)."""
    return [(a[0], b[0], math.degrees(math.atan2(b[1]-a[1], b[0]-a[0])))
            for a,b in zip(route['profile'],route['profile'][1:]) if b[0] > a[0]]


def metrics(route, meters_per_pixel):
    pts, profile = route['points'], route['profile']
    distance = sum(math.dist(a,b) for a,b in zip(pts,pts[1:])) * meters_per_pixel
    ascent = sum(max(b[1]-a[1],0) for a,b in zip(profile,profile[1:]))
    slope = segments(route)
    return dict(distance=distance, ascent=ascent,
                max_slope=max((abs(angle) for _,_,angle in slope), default=0),
                stops=len(route['stops']))


def mission(route, meters_per_pixel, speed=1, minutes_per_stop=20, autonomy=240, reserve=30):
    """Time in minutes; assumed mean speed in km/h, without a slope correction."""
    m = metrics(route, meters_per_pixel)
    walk = 60 * (m['distance']/1000) / speed
    science = m['stops'] * minutes_per_stop
    total = walk + science + reserve
    return {**m, 'walk':walk, 'science':science, 'total':total,
            'remaining':autonomy-total, 'fits':total <= autonomy}


def recommend(results, priority):
    """Filter by time budget; prioritize science, slope or duration."""
    feasible = [i for i,r in enumerate(results) if r['fits']]
    if not feasible:
        return None
    keys = {'science':lambda r:(-r['stops'],r['max_slope'],r['total']),
            'terrain':lambda r:(r['max_slope'],r['total']),
            'time':lambda r:(r['total'],r['max_slope'])}
    return min(feasible,key=lambda i:keys[priority](results[i]))


def map_slope_pieces(route, meters_per_pixel):
    """Project profile intervals onto the round-trip polyline.
    Draw in increasing slope order so the steepest overlapping segment is visible.
    """
    pts = route['points']
    cumulative = [0.0]
    for a,b in zip(pts,pts[1:]):
        cumulative.append(cumulative[-1]+math.dist(a,b)*meters_per_pixel)
    end = route['profile'][-1][0]
    if not end or not cumulative[-1]:
        return []
    factor = cumulative[-1]/end
    def interpolate(d):
        if d <= 0:return pts[0]
        if d >= cumulative[-1]:return pts[-1]
        j = min(bisect_right(cumulative,d)-1,len(pts)-2)
        fraction = (d-cumulative[j])/(cumulative[j+1]-cumulative[j])
        return [pts[j][k]+fraction*(pts[j+1][k]-pts[j][k]) for k in (0,1)]
    pieces=[]
    for a,b,theta in segments(route):
        a,b=a*factor,b*factor
        piece=[interpolate(a)]+[p for d,p in zip(cumulative,pts) if a<d<b]+[interpolate(b)]
        pieces.append((piece,abs(theta)))
    return sorted(pieces,key=lambda p:p[1])
