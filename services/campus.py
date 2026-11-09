"""Campus map data: the three buildings on static/img/campus.png and locker status groups.

Outlines are polygons in the illustration's own pixel space (2172 x 724), traced from the
image so each building can be hovered and clicked on its own. Shared edges are identical,
so the three outlines meet without gaps or overlaps.
"""

IMAGE = "img/campus.png"            # original drawing on white (building page header)
LINES = "img/campus-lines.png"      # same drawing as transparent ink (landing page)
COLOR = "img/campus-color.png"      # Christmas colouring under the ink: roofs, trees, crest
WIDTH, HEIGHT = 2172, 724

# Roof edge, roof tip and support strut of each wing (shared with the middle building).
_LEFT_EDGE = [(536, 222), (600, 241), (700, 296), (760, 346), (793, 384), (779, 400),
              (768, 404), (659, 572), (670, 580), (670, 724)]
_RIGHT_EDGE = [(1690, 214), (1600, 263), (1520, 311), (1470, 348), (1435, 387), (1460, 400),
               (1471, 409), (1586, 580), (1580, 588), (1580, 724)]

_JPL = [(0, 121), (80, 123), (160, 131), (240, 141), (320, 157), (400, 177), (480, 201),
        *_LEFT_EDGE, (0, 724)]
_SOTERO = [(2172, 121), (2080, 128), (2000, 136), (1920, 149), (1840, 167), (1760, 189),
           *_RIGHT_EDGE, (2172, 724)]
_COECSA = [(536, 30), (1363, 30), (1363, 214), *_RIGHT_EDGE, *reversed(_LEFT_EDGE)]

# slug -> display data. `label` is the map label position in % of the image.
# On hover a building grows from `origin` (a point inside it) and rises by `lift` px.
# Growing from inside means the lifted copy always covers its own outline, so no gap
# opens next to the neighbours; the wings are drawn above the middle building.
BUILDINGS = {
    "jpl":    {"name": "JPL",    "position": "Left building",   "points": _JPL,
               "label": (15.5, 40), "origin": (335, 520), "lift": -6},
    "coecsa": {"name": "COECSA", "position": "Middle building", "points": _COECSA,
               "label": (43.6, 13), "origin": (950, 420), "lift": 0},
    "sotero": {"name": "Sotero", "position": "Right building",  "points": _SOTERO,
               "label": (84.5, 40), "origin": (1876, 520), "lift": -6},
}
CARD_ORDER = ["jpl", "coecsa", "sotero"]     # left to right, as on the picture
DRAW_ORDER = ["coecsa", "jpl", "sotero"]     # the middle building sits behind both wings

# Database status -> what the student sees (green / red / gray)
STATUS_GROUP = {
    "Available": "available",
    "Reserved": "occupied",
    "Assigned": "occupied",
    "Expired": "occupied",
    "Under Maintenance": "unavailable",
}
GROUPS = ["available", "occupied", "unavailable"]


def slug_for(building_name):
    """'COECSA' -> 'coecsa'; None for a building that is not on the map."""
    return next((slug for slug, b in BUILDINGS.items() if b["name"] == building_name), None)


def group_of(status):
    return STATUS_GROUP.get(status, "unavailable")


def points_attr(points):
    return " ".join(f"{x},{y}" for x, y in points)


def view_box(points, pad=24):
    """Tight SVG viewBox around one building (for its page header)."""
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
    x1, y1 = min(WIDTH, max(xs) + pad), min(HEIGHT, max(ys))
    return f"{x0} {y0} {x1 - x0} {y1 - y0}"


def empty_counts():
    return {"total": 0, **{g: 0 for g in GROUPS}}


def summarize(rows):
    """rows of (building, status, n) -> {slug: counts}."""
    by_name = {b["name"]: slug for slug, b in BUILDINGS.items()}
    stats = {slug: empty_counts() for slug in BUILDINGS}
    for r in rows:
        slug = by_name.get(r["building"])
        if slug:
            stats[slug][group_of(r["status"])] += r["n"]
            stats[slug]["total"] += r["n"]
    return stats
