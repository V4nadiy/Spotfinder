-- Включаем PostGIS (если не включено)
CREATE EXTENSION IF NOT EXISTS postgis;

-- Типы объектов
CREATE TABLE IF NOT EXISTS place_types (
    id SERIAL PRIMARY KEY,
    code TEXT UNIQUE NOT NULL,
    name TEXT
);

-- Геолокации объектов
CREATE TABLE IF NOT EXISTS places (
    id SERIAL PRIMARY KEY,
    type_id INTEGER REFERENCES place_types(id),
    name TEXT,
    geom GEOMETRY(Point, 4326)
);

-- HTML-карты
CREATE TABLE IF NOT EXISTS debug_maps (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP DEFAULT now(),
    user_lat DOUBLE PRECISION,
    user_lon DOUBLE PRECISION,
    map_html TEXT
);
