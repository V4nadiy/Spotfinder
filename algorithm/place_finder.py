import psycopg2
import random
import math
import logging
from typing import List, Tuple, Dict, Optional

from shapely import wkt
from shapely.geometry import Point, LineString
import folium
import overpy

logger = logging.getLogger(__name__)

class PlaceFinder:
    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config

    def _connect(self):
        return psycopg2.connect(**self.db_config)

    def get_places_by_type(self, place_type: str) -> List[Tuple[float, float]]:
        query = """
            SELECT ST_Y(geom) AS latitude, ST_X(geom) AS longitude
            FROM places p
            JOIN place_types t ON p.type_id = t.id
            WHERE t.code = %s;
        """
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(query, (place_type,))
            results = cur.fetchall()
            logger.info(f"[DB] Found {len(results)} competitors for type '{place_type}'")
            return results

    def _store_map_in_db(self, user_loc: Tuple[float, float],
                         best_loc: Tuple[float, float],
                         competitors: List[Tuple[float, float]]):
        m = folium.Map(location=user_loc, zoom_start=15)
        folium.Marker(user_loc, tooltip="User").add_to(m)
        for lat, lon in competitors:
            folium.CircleMarker([lat, lon], radius=5, color="red", fill=True).add_to(m)
        folium.Marker(best_loc, tooltip="Recommended", icon=folium.Icon(color="green")).add_to(m)
        html_map = m.get_root().render()

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO debug_maps (user_lat, user_lon, map_html)
                VALUES (%s, %s, %s);
            """, (user_loc[0], user_loc[1], html_map))
            logger.info("[DB] Saved HTML map to debug_maps")

    def find_optimal_location(
        self,
        user_location: Tuple[float, float],
        place_type: str,
        grid_step_m: float = 50.0
    ) -> Optional[Tuple[str, float, float, Tuple[float, float]]]:
        user_lat, user_lon = user_location
        competitors = self.get_places_by_type(place_type)
        if not competitors:
            logger.warning(f"No competitors found for type '{place_type}'")
            return None

        # Получение 1км буфера
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT ST_AsText(
                    ST_Buffer(
                        ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                        1000
                    )::geometry
                );
            """, (user_lon, user_lat))
            buf_wkt = cur.fetchone()[0]

        buffer_poly = wkt.loads(buf_wkt)
        minx, miny, maxx, maxy = buffer_poly.bounds

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            φ1, φ2 = math.radians(lat1), math.radians(lat2)
            Δφ = math.radians(lat2 - lat1)
            Δλ = math.radians(lon2 - lon1)
            a = math.sin(Δφ/2)**2 + math.cos(φ1)*math.cos(φ2)*math.sin(Δλ/2)**2
            return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))

        deg_step = grid_step_m / 111320
        best_point = None
        best_min_distance = -1

        lat = miny
        while lat <= maxy:
            lon = minx
            while lon <= maxx:
                pt = Point(lon, lat)
                if buffer_poly.contains(pt):
                    dists = [haversine(lat, lon, clat, clon) for clat, clon in competitors]
                    min_dist = min(dists)
                    if min_dist > best_min_distance:
                        best_min_distance = min_dist
                        best_point = pt
                lon += deg_step
            lat += deg_step

        if best_point is None:
            logger.warning("No valid point found in buffer")
            return None

        snapped_lat, snapped_lon = best_point.y, best_point.x

        try:
            bbox = f"({miny},{minx},{maxy},{maxx})"
            api = overpy.Overpass()
            result = api.query(f"way['highway']{bbox};(._;>;);out;")
            roads = [
                LineString([(n.lon, n.lat) for n in way.nodes])
                for way in result.ways if way.nodes
            ]
            orig = best_point
            projections = [road.interpolate(road.project(orig)) for road in roads]
            if projections:
                snap = min(projections, key=lambda p: p.distance(orig))
                snapped_lon, snapped_lat = snap.x, snap.y
        except Exception as e:
            logger.error(f"Overpass snapping failed: {e}")

        try:
            self._store_map_in_db(
                user_loc=(user_lat, user_lon),
                best_loc=(snapped_lat, snapped_lon),
                competitors=competitors
            )
        except Exception as e:
            logger.error(f"Failed to save map to DB: {e}")

        logger.info(f"✅ Optimal location at ({snapped_lat}, {snapped_lon}) with clearance {best_min_distance:.1f}m")
        return f"Recommended location for '{place_type}'", snapped_lat, snapped_lon, (user_lat, user_lon)