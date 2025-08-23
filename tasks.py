from db import get_conn, release_conn

def update_coordinate_to_gridpoints(data):
    print(f"[Worker] starting work to update coordinate_to_gridpoints table: {data}")

    truncated_latitude = data[0]
    truncated_longitude = data[1]
    grid_id = data[2]
    grid_x = data[3] 
    grid_y = data[4] 
    expires_at = data[5]

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
        INSERT INTO coordinate_to_gridpoints(latitude, longitude, grid_id, grid_x, grid_y, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (latitude, longitude)
        DO UPDATE SET grid_id=EXCLUDED.grid_id,
                      grid_x=EXCLUDED.grid_x,
                      grid_y=EXCLUDED.grid_y,
                      expires_at=EXCLUDED.expires_at
        """, (truncated_latitude, truncated_longitude, grid_id, grid_x, grid_y, expires_at))

        conn.commit()
        release_conn(conn)

    except:
        print(f"[Worker] failed to update coordinate_to_gridpoints table: {data}")

    print(f"[Worker] done updating coordinate_to_gridpoints table")

def update_gridpoints_to_forecasts(data):
    print(f"[Worker] starting work to update gridpoints_to_forecast table: {data}")

    grid_id = data[0]
    grid_x = data[1]
    grid_y = data[2]
    forecast_url = data[3] 
    expires_at = data[4]

    try:
        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO gridpoints_to_forecast(grid_id, grid_x, grid_y, forecast_url, expires_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (grid_id, grid_x, grid_y)
            DO UPDATE SET grid_id=EXCLUDED.grid_id,
                          grid_x=EXCLUDED.grid_x,
                          grid_y=EXCLUDED.grid_y,
                          forecast_url=EXCLUDED.forecast_url,
                          expires_at=EXCLUDED.expires_at
        """, (grid_id, grid_x, grid_y, forecast_url, expires_at))

        conn.commit()
        release_conn(conn)
    except:
        print(f"[Worker] failed to update gridpoints_to_forecast table")

    print(f"[Worker] done updating gridpoints_to_forceast table")

