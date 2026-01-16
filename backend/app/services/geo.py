import json
import os
from typing import Optional
from shapely.geometry import shape, Point

# Global storage for neighborhood polygons
_neighborhoods: list[tuple[str, str, any]] = []  # (name, borough, polygon)
_loaded = False


def _load_neighborhoods():
    """Load NYC NTA boundaries from GeoJSON file."""
    global _neighborhoods, _loaded

    if _loaded:
        return

    geojson_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "data",
        "nyc_nta.geojson"
    )

    try:
        with open(geojson_path, "r") as f:
            data = json.load(f)

        for feature in data.get("features", []):
            props = feature.get("properties", {})
            name = props.get("ntaname", "Unknown")
            borough = props.get("boroname", "Unknown")
            geometry = feature.get("geometry")

            if geometry:
                poly = shape(geometry)
                _neighborhoods.append((name, borough, poly))

        _loaded = True
        print(f"Loaded {len(_neighborhoods)} NYC neighborhoods")
    except Exception as e:
        print(f"Error loading NYC neighborhoods: {e}")


def get_neighborhood(lat: float, lon: float) -> Optional[str]:
    """
    Given latitude and longitude, return the NYC neighborhood name.
    Returns None if the point is not within any NYC neighborhood.
    """
    _load_neighborhoods()

    if not _neighborhoods:
        return None

    point = Point(lon, lat)  # Note: Shapely uses (x, y) = (lon, lat)

    for name, borough, polygon in _neighborhoods:
        try:
            if polygon.contains(point):
                return name
        except Exception:
            continue

    return None


def get_all_neighborhoods() -> list[str]:
    """Return a list of all NYC neighborhood names."""
    _load_neighborhoods()
    return sorted(set(name for name, borough, polygon in _neighborhoods))


def get_neighborhoods_by_borough() -> dict[str, list[str]]:
    """Return neighborhoods grouped by borough."""
    _load_neighborhoods()
    boroughs: dict[str, set[str]] = {}
    for name, borough, polygon in _neighborhoods:
        if borough not in boroughs:
            boroughs[borough] = set()
        boroughs[borough].add(name)

    # Sort neighborhoods within each borough
    return {b: sorted(list(n)) for b, n in boroughs.items()}
