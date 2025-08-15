import requests
import os
from directions import Step
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from db import get_conn, release_conn
from cache import redis_conn


HEADERS = {
    "Accept": "application/geo+json",
    "User-Agent": os.getenv("WEATHER_DOT_GOV_API_KEY")
}


def truncateCoordinate(coordinate: str, max_decimal_places: int = 4) -> str:
    if "." not in coordinate:
        return coordinate
    
    whole, fraction = coordinate.split(".")
    if len(fraction) > max_decimal_places:
        return f"{whole}.{fraction[:max_decimal_places]}"
    else:
        return coordinate


def getPoints(truncated_latitude: str, truncated_longitude: str, unique_gridpoints: set) -> str|None:
    coordinate_key = f"{truncated_latitude}:{truncated_longitude}"
    now = datetime.now(timezone.utc)

    # check Redis first
    cached_point = redis_conn.get(coordinate_key)
    if cached_point:
        grid_key = cached_point.decode("utf-8")
        unique_gridpoints.add(grid_key)
        return grid_key

    # check db
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT grid_id, grid_x, grid_y, expires_at FROM coordinate_to_gridpoints WHERE latitude=%s AND longitude=%s", (truncated_latitude, truncated_longitude))
    row = cur.fetchone()
    if row:
        grid_id, grid_x, grid_y, expires_at = row
        grid_key = f"{grid_id}:{grid_x}:{grid_y}"
        if expires_at > now:
            # Populate Redis and return
            redis_conn.set(coordinate_key, grid_key, ex=int((expires_at - now).total_seconds()))
            release_conn(conn)
            unique_gridpoints.add(grid_key)
            return grid_key

    # Cache miss fetch from api: https://api.weather.gov/points/{lat},{lon}.
    points_url = f"https://api.weather.gov/points/{truncated_latitude},{truncated_longitude}"
    response = requests.get(points_url, headers=HEADERS)
    response_json = response.json()
    response_header_cache_control = response.headers["Cache-Control"]

    max_age_hours = 0
    try:
        max_age_seconds = response_header_cache_control.split(",")[1].split("=")[1]
        max_age_hours = (int(max_age_seconds) / 60) / 60
    except:
        print("Failed to gather max-age from cache-control")

    if response.status_code == 200:
        expires_at = now + timedelta(hours=max_age_hours if max_age_hours else 24)
        response_properties = response_json["properties"]
        
        grid_id = response_properties["gridId"]
        grid_x= response_properties["gridX"]
        grid_y= response_properties["gridY"]
        grid_key = f"{grid_id}:{grid_x}:{grid_y}"

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

        forecast_url = response_properties["forecast"]
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

        redis_conn.set(coordinate_key, grid_key, ex=int((expires_at - now).total_seconds()))
        redis_conn.set(grid_key, forecast_url, ex=int((expires_at - now).total_seconds()))
        unique_gridpoints.add(grid_key)

        return grid_key
    else:
        return None

        # return f"Error getting response for the following request to the points endpoint. url={points_url}, request={response.request}, status_code={response.status_code}"


def getForecast(gridpoints: str) -> str:
    grid_id, grid_x, grid_y = gridpoints.split(":")
    now = datetime.now(timezone.utc)
    forecast_url = ""

    # check Redis first
    cached_forecast_url = redis_conn.get(gridpoints)
    if cached_forecast_url:
        forecast_url = cached_forecast_url

    # check db
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT forecast_url, expires_at FROM gridpoints_to_forecast WHERE grid_id=%s AND grid_x=%s AND grid_y=%s", (grid_id, grid_x, grid_y))
    row = cur.fetchone()
    if row:
        db_forecast_url, expires_at = row
        if expires_at > now:
            # Populate Redis and return
            redis_conn.set(gridpoints, db_forecast_url, ex=int((expires_at - now).total_seconds()))
            release_conn(conn)
            forecast_url = db_forecast_url 

    if forecast_url:
        forecast_response = requests.get(forecast_url, headers=HEADERS)
        if forecast_response.status_code == 200:
            return forecast_response.json()
        else:
            print(f"Error getting response for the following request the forecast endpoint. url={cached_forecast_url}, request={forecast_response.request}, status_code={forecast_response.status_code}")
            return ""
    else:
        print(f"Error getting forecast, no forecast_url found")
        return ""


def getWeather(route: list[Step]) -> dict:
    coordinate_to_point_map = {}
    unique_gridpoints = set()

    # Get points
    for step in tqdm(route, desc="Getting Points"):
        for coordinate in step.coordinates:
            truncated_latitude = truncateCoordinate(coordinate.latitude)
            truncated_longitude = truncateCoordinate(coordinate.longitude)
            # Don't request the same coordinates if we have already done them.
            coordinate_key = f"{truncated_latitude}:{truncated_longitude}"
            coordinate_to_point_map[coordinate_key] = getPoints(truncated_latitude, truncated_longitude, unique_gridpoints)

    # Get forecasts 
    forecasts = {}
    for gridpoint in tqdm(unique_gridpoints, desc="Getting Forecasts"):
        forecasts[gridpoint] = getForecast(gridpoint)
    
    return forecasts

            # hourly_forecast_response = requests.get(hourly_forecast_url, headers=headers)
            # hourly_forecast_response_json = hourly_forecast_response.json()
            # print(f"hourly_forecast_response_json={hourly_forecast_response_json}")

    #     return f"Error getting response for the following request to the points endpoint. url={points_url}, request={response.request}, status_code={response.status_code}"

    #TODO: Save Forecasts? Maybe last for a couple of hours before refetching from api?
    #TODO: need to update logic to include error messages if I don't get the forecast correctly.

