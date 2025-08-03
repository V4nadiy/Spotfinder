import json
import psycopg2
from config.config import DB_CONFIG

with open("data/cafes.json", "r") as f:
    coords = json.load(f)

with psycopg2.connect(**DB_CONFIG) as conn, conn.cursor() as cur:
    cur.execute("SELECT id FROM place_types WHERE code = 'cafe'")
    result = cur.fetchone()
    if not result:
        raise Exception("Place type 'cafe' not found")
    type_id = result[0]

    for lat, lon in coords:
        cur.execute("""
            INSERT INTO places (type_id, name, geom)
            VALUES (%s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
        """, (type_id, 'Imported Cafe', lon, lat))

    print(f"✅ Imported {len(coords)} cafe(s).")
