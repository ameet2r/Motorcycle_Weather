import os
from psycopg2 import pool, sql

DATABASE_URL = os.getenv("DATABASE_URL")

db_pool: pool.SimpleConnectionPool = pool.SimpleConnectionPool(minconn=1, maxconn=10, dsn=DATABASE_URL)


def init_db_pool():
    global db_pool
    if not db_pool:
        db_pool = pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL
        )

def get_conn():
    return db_pool.getconn()

def release_conn(conn):
    db_pool.putconn(conn)

def close_pool():
    if db_pool:
        db_pool.closeall()

def create_tables():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS coordinate_to_gridpoints(
            latitude DOUBLE PRECISION NOT NULL,
            longitude DOUBLE PRECISION NOT NULL,
            grid_id TEXT NOT NULL,
            grid_x INT NOT NULL,
            grid_y INT NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (latitude, longitude)
        )
    """)
    conn.commit()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gridpoints_to_forecast_url(
            grid_id TEXT NOT NULL,
            grid_x INT NOT NULL,
            grid_y INT NOT NULL,
            forecast_url TEXT NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            PRIMARY KEY (grid_id, grid_x, grid_y)
        )
    """)
    conn.commit()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS gridpoints_to_forecast(
            grid_id TEXT NOT NULL,
            grid_x INT NOT NULL,
            grid_y INT NOT NULL,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            forecast JSONB NOT NULL,
            PRIMARY KEY (grid_id, grid_x, grid_y)
        )
    """)
    conn.commit()
    release_conn(conn)

