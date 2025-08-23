import requests
import os
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from db import get_conn, release_conn
from cache import redis_conn
from coordinates import Point, Step, Coordinates
from forecast import Forecast
from rq import Queue
from tasks import update_gridpoints_to_forecasts, update_coordinate_to_gridpoints

WORKER_QUEUE = Queue(connection=redis_conn)

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


def getPoints(truncated_latitude: str, truncated_longitude: str) -> Point:
    coordinate_key = f"{truncated_latitude}:{truncated_longitude}"
    now = datetime.now(timezone.utc)

    # check Redis first
    cached_point = redis_conn.get(coordinate_key)
    if cached_point:
        grid_id, grid_x, grid_y = cached_point.decode("utf-8").split(":")
        return Point(grid_id, grid_x, grid_y)

    # check db
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT grid_id, grid_x, grid_y, expires_at FROM coordinate_to_gridpoints WHERE latitude=%s AND longitude=%s", (truncated_latitude, truncated_longitude))
    row = cur.fetchone()
    if row:
        grid_id, grid_x, grid_y, expires_at = row
        point = Point(grid_id, grid_x, grid_y)
        if expires_at > now:
            # Populate Redis and return
            redis_conn.set(coordinate_key, point.to_str(), ex=int((expires_at - now).total_seconds()))
            return point

    release_conn(conn)

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
        point = Point(grid_id, grid_x, grid_y)

        WORKER_QUEUE.enqueue(update_coordinate_to_gridpoints, (truncated_latitude, truncated_longitude, grid_id, grid_x, grid_y, expires_at))

        forecast_url = response_properties["forecast"]
        WORKER_QUEUE.enqueue(update_gridpoints_to_forecasts, (grid_id, grid_x, grid_y, forecast_url, expires_at))

        redis_conn.set(coordinate_key, point.to_str(), ex=int((expires_at - now).total_seconds()))
        redis_conn.set(point.to_str(), forecast_url, ex=int((expires_at - now).total_seconds()))

        return point
    else:
        return Point("", "", "")


def getForecast(coordinate: Coordinates) -> Forecast:
    now = datetime.now(timezone.utc)
    forecast_url = ""
    gridpoint = coordinate.point

    # check Redis first
    cached_forecast_url = redis_conn.get(gridpoint.to_str())
    if cached_forecast_url:
        forecast_url = cached_forecast_url

    # check db
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT forecast_url, expires_at FROM gridpoints_to_forecast WHERE grid_id=%s AND grid_x=%s AND grid_y=%s", (gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y))
    row = cur.fetchone()
    if row:
        db_forecast_url, expires_at = row
        if expires_at > now:
            # Populate Redis and return
            redis_conn.set(gridpoint.to_str(), db_forecast_url, ex=int((expires_at - now).total_seconds()))
            forecast_url = db_forecast_url 

    release_conn(conn)


    if forecast_url:
        forecast_response = requests.get(forecast_url, headers=HEADERS)
        if forecast_response.status_code == 200:
            return Forecast(forecast_response.json())
        else:
            print(f"Error getting response for the following request the forecast endpoint. url={cached_forecast_url}, request={forecast_response.request}, status_code={forecast_response.status_code}")
            return Forecast({})
    else:
        print(f"Error getting forecast, no forecast_url found")
        return Forecast({})


def getWeather(route: list[Step]):
    # Get points
    for step in tqdm(route, desc="Getting Points"):
        for coordinate in step.coordinates:
            truncated_latitude = truncateCoordinate(coordinate.latitude)
            truncated_longitude = truncateCoordinate(coordinate.longitude)
            coordinate.point = getPoints(truncated_latitude, truncated_longitude)

    # Get Weekly forecast for each point
    for step in tqdm(route, desc="Getting Forecasts"):
        for coordinate in step.coordinates:
            if coordinate.point.is_not_empty:
                coordinate.forecasts = getForecast(coordinate)


    




