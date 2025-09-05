import requests
import os
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from app.db import get_conn, release_conn
from app.cache import redis_conn
from app.coordinates import Point, Step, Coordinates
from app.forecast import Forecast
from rq import Queue
from app.tasks import update_gridpoints_to_forecasts_url, update_gridpoints_to_forecasts, update_coordinate_to_gridpoints
import json
from app.constants import REDIS_FORECAST_URL_KEY_SUFFIX, REDIS_FORECAST_KEY_SUFFIX

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


def getPoints(truncated_latitude: str, truncated_longitude: str) -> Point|None:
    coordinate_key = f"{truncated_latitude}:{truncated_longitude}"
    now = datetime.now(timezone.utc)

    # check Redis first
    cached_point = redis_conn.get(coordinate_key)
    if cached_point:
        grid_id, grid_x, grid_y = cached_point.decode("utf-8").split(":")
        return Point(grid_id, grid_x, grid_y)

    # check db
    point = Point("", "", "")
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT grid_id, grid_x, grid_y, expires_at FROM coordinate_to_gridpoints WHERE latitude=%s AND longitude=%s", (truncated_latitude, truncated_longitude))
        row = cur.fetchone()
        if row:
            grid_id, grid_x, grid_y, expires_at = row
            retrieved_point = Point(grid_id, grid_x, grid_y)
            if expires_at > now:
                # Populate Redis and return
                redis_conn.set(coordinate_key, retrieved_point.to_str(), ex=int((expires_at - now).total_seconds()))
                point = retrieved_point
    except:
        print(f"Failed to grab point for coordinate_key={coordinate_key}")
    finally:
        release_conn(conn)
        if point.is_not_empty():
            return point


    # Cache miss fetch from api: https://api.weather.gov/points/{lat},{lon}.
    try:
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
            forecast_url = response_properties["forecast"]
            try:
                WORKER_QUEUE.enqueue(update_coordinate_to_gridpoints, (truncated_latitude, truncated_longitude, grid_id, grid_x, grid_y, expires_at))

                WORKER_QUEUE.enqueue(update_gridpoints_to_forecasts_url, (grid_id, grid_x, grid_y, forecast_url, expires_at))

                redis_conn.set(coordinate_key, point.to_str(), ex=int((expires_at - now).total_seconds()))
                redis_conn.set(point.to_str() + REDIS_FORECAST_URL_KEY_SUFFIX, forecast_url, ex=int((expires_at - now).total_seconds()))

                return point
            except:
                print(f"Failed to send update to Redis and DB with the following data: coordinate_key={coordinate_key}, point.to_str()={point.to_str()}, point.to_str()+REDIS_FORECAST_URL_KEY_SUFFIX={point.to_str()+REDIS_FORECAST_URL_KEY_SUFFIX}, forecast_url={forecast_url}")
                
        else:
            return Point("", "", "")
    except:
        url = f"https://api.weather.gov/points/{truncated_latitude},{truncated_longitude}"
        print(f"Failed to hit point endpoint with this request: {url}, headers={HEADERS}")
        return Point("", "", "")


def getForecastUrl(gridpoint: Point, time: datetime = datetime.now(timezone.utc)) -> str:
    forecast_url = ""

    # check Redis first
    cached_forecast_url = redis_conn.get(gridpoint.to_str() + REDIS_FORECAST_URL_KEY_SUFFIX)
    if cached_forecast_url:
        return cached_forecast_url

    # check db
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute("SELECT forecast_url, expires_at FROM gridpoints_to_forecast_url WHERE grid_id=%s AND grid_x=%s AND grid_y=%s", (gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y))
        row = cur.fetchone()
        if row:
            db_forecast_url, expires_at = row
            if expires_at > time:
                # Populate Redis and return
                redis_conn.set(gridpoint.to_str() + REDIS_FORECAST_URL_KEY_SUFFIX, db_forecast_url, ex=int((expires_at - time).total_seconds()))
                forecast_url = db_forecast_url 

    except:
        print(f"Failed to get forecast_url from db")
    finally:
        release_conn(conn)

    return forecast_url


def getForecast(gridpoint: Point) -> Forecast|None:
    time = datetime.now(timezone.utc)

    # check Redis first
    cached_forecast = redis_conn.get(gridpoint.to_str() + REDIS_FORECAST_KEY_SUFFIX)
    if cached_forecast:
        cached_forecast_json = json.loads(cached_forecast.decode("utf-8"))
        return Forecast(cached_forecast_json)

    # check db
    conn = get_conn()
    forecast_result = None
    try:
        cur = conn.cursor()
        cur.execute("SELECT forecast, expires_at FROM gridpoints_to_forecast WHERE grid_id=%s AND grid_x=%s AND grid_y=%s", (gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y))
        row = cur.fetchone()
        if row:
            forecast, expires_at = row
            if expires_at > time:
                # Populate Redis and return
                redis_conn.set(gridpoint.to_str() + REDIS_FORECAST_KEY_SUFFIX, json.dumps(forecast), ex=int((expires_at - time).total_seconds()))
                forecast_result = Forecast(forecast)
    except:
        print(f"Failed to get forecast from db")
    finally:
        release_conn(conn)
        if forecast_result:
            return forecast_result
            
    # get forecast_url before hitting api
    forecast_url = getForecastUrl(gridpoint, time)

    # Cache and db miss fetch from api
    try:
        if forecast_url:
            forecast_response = requests.get(forecast_url, headers=HEADERS)
            if forecast_response.status_code == 200:
                expires_at = time + timedelta(3) # Expire forecast after 3 hours
                WORKER_QUEUE.enqueue(update_gridpoints_to_forecasts, (gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y, json.dumps(forecast_response.json()), expires_at))
                forecast_response_json = json.dumps(forecast_response.json())
                redis_conn.set(gridpoint.to_str() + REDIS_FORECAST_KEY_SUFFIX, forecast_response_json, ex=int((expires_at - time).total_seconds()))
                return Forecast(forecast_response.json())
            else:
                print(f"Error getting response for the following request the forecast endpoint. forecast={forecast_response.json()}, request={forecast_response.request}, status_code={forecast_response.status_code}")
                return Forecast({})
        else:
            print(f"Error getting forecast, no forecast_url found")
            return Forecast({})
    except:
        print(f"Error getting forecast")
        return Forecast({})


def getWeather(coords: list[Coordinates]):
    distinct_points = {}

    # Get points
    for coordinate in tqdm(coords, desc="Getting Points"):
        truncated_latitude = truncateCoordinate(coordinate.latitude)
        truncated_longitude = truncateCoordinate(coordinate.longitude)
        coordinate.point = getPoints(truncated_latitude, truncated_longitude)
        distinct_points[coordinate.point] = None

    # Get Weekly forecast for each point
    for point in tqdm(distinct_points, desc="Getting Forecasts"):
        if point.is_not_empty():
            forecast = getForecast(point)
            distinct_points[point] = forecast

    for coordinate in coords:
        if coordinate.point in distinct_points:
            coordinate.forecasts = distinct_points[coordinate.point]
            
    




