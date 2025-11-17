import requests
import os
import logging
from tqdm import tqdm
from datetime import datetime, timedelta, timezone
from .coordinates import Point, Step, Coordinates
from .forecast import Forecast
from .firestore_service import (
    get_coordinate_to_gridpoints,
    set_coordinate_to_gridpoints,
    get_gridpoints_to_forecast_url,
    set_gridpoints_to_forecast_url,
    get_gridpoints_to_forecast,
    set_gridpoints_to_forecast,
    get_alerts,
    set_alerts
)
import json
from collections import defaultdict

logger = logging.getLogger(__name__)

HEADERS = {
    "Accept": "application/geo+json",
    "User-Agent": os.getenv("WEATHER_DOT_GOV_API_KEY")
}

# Disable tqdm progress bars in production to save memory
def _get_progress_bar(iterable, desc=""):
    """Return tqdm progress bar in development, plain iterable in production"""
    environment = os.getenv("ENVIRONMENT", "development")
    if environment == "production":
        return iterable
    return tqdm(iterable, desc=desc)


def truncateCoordinate(coordinate: str, max_decimal_places: int = 4) -> str:
    if "." not in coordinate:
        return coordinate
    
    whole, fraction = coordinate.split(".")
    if len(fraction) > max_decimal_places:
        return f"{whole}.{fraction[:max_decimal_places]}"
    else:
        return coordinate


def getPoints(truncated_latitude: str, truncated_longitude: str) -> Point:
    now = datetime.now(timezone.utc)

    # Check Firestore first
    cached_data = get_coordinate_to_gridpoints(truncated_latitude, truncated_longitude)
    if cached_data:
        return Point(cached_data['gridId'], str(cached_data['gridX']), str(cached_data['gridY']))

    # Cache miss - fetch from weather.gov API
    try:
        points_url = f"https://api.weather.gov/points/{truncated_latitude},{truncated_longitude}"
        response = requests.get(points_url, headers=HEADERS, timeout=10)

        # Validate response before parsing
        if not response.ok:
            logger.warning(f"Weather API returned status code: {response.status_code}")
            return Point("", "", "")

        response_json = response.json()

        # Validate response structure
        if "properties" not in response_json:
            logger.warning(f"Invalid response structure from Weather API: missing 'properties'")
            return Point("", "", "")

        response_header_cache_control = response.headers.get("Cache-Control", "")

        max_age_hours = 24  # Default to 24 hours
        try:
            if "max-age=" in response_header_cache_control:
                max_age_seconds = response_header_cache_control.split("max-age=")[1].split(",")[0]
                max_age_hours = int(max_age_seconds) / 3600
        except:
            logger.debug("Failed to gather max-age from cache-control, using default 24 hours")

        # Validate required fields in response
        expires_at = now + timedelta(hours=max_age_hours)
        response_properties = response_json["properties"]

        # Check for required fields
        required_fields = ["gridId", "gridX", "gridY", "forecastHourly"]
        for field in required_fields:
            if field not in response_properties:
                logger.warning(f"Invalid response structure: missing '{field}' in properties")
                return Point("", "", "")

        grid_id = response_properties["gridId"]
        grid_x = str(response_properties["gridX"])
        grid_y = str(response_properties["gridY"])
        point = Point(grid_id, grid_x, grid_y)
        forecast_url = response_properties["forecastHourly"]

        try:
            # Store coordinate to gridpoints mapping synchronously
            set_coordinate_to_gridpoints(truncated_latitude, truncated_longitude, grid_id, grid_x, grid_y, expires_at)

            # Store gridpoints to forecast URL mapping synchronously
            set_gridpoints_to_forecast_url(grid_id, grid_x, grid_y, forecast_url, expires_at)

            return point
        except Exception as e:
            logger.error(f"Failed to store data in Firestore: {e}")
            return Point("", "", "")
    except Exception as e:
        logger.error(f"Failed to fetch points from Weather API for coordinates {truncated_latitude},{truncated_longitude}: {e}")
        return Point("", "", "")


def getForecastUrl(gridpoint: Point, time: datetime = datetime.now(timezone.utc)) -> str:
    """Get forecast URL for a gridpoint from Firestore"""
    try:
        forecast_url = get_gridpoints_to_forecast_url(gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y)
        return forecast_url or ""
    except Exception as e:
        logger.error(f"Failed to get forecast_url from Firestore: {e}")
        return ""


def getWindGustData(gridpoint: Point) -> dict:
    """
    Get wind gust time series data from raw gridpoint endpoint.
    Returns a dict mapping ISO timestamp strings to wind gust values in mph.
    """
    try:
        gridpoint_url = f"https://api.weather.gov/gridpoints/{gridpoint.grid_id}/{gridpoint.grid_x},{gridpoint.grid_y}"
        response = requests.get(gridpoint_url, headers=HEADERS, timeout=10)

        if not response.ok:
            logger.warning(f"Gridpoint API error - Status: {response.status_code}")
            return {}

        gridpoint_data = response.json()

        # Extract windGust time series
        if "properties" not in gridpoint_data or "windGust" not in gridpoint_data["properties"]:
            logger.debug(f"No windGust data in gridpoint response for {gridpoint.grid_id}/{gridpoint.grid_x},{gridpoint.grid_y}")
            return {}

        wind_gust_layer = gridpoint_data["properties"]["windGust"]
        values = wind_gust_layer.get("values", [])
        uom = wind_gust_layer.get("uom", "")

        # Convert to dict mapping timestamp -> gust value in mph
        gust_map = {}
        km_to_mph = 0.621371

        for entry in values:
            valid_time = entry.get("validTime", "")
            value = entry.get("value")

            if valid_time and value is not None:
                # Parse ISO 8601 duration format (e.g., "2025-10-31T21:00:00+00:00/PT1H")
                timestamp = valid_time.split("/")[0]

                # Convert km/h to mph if needed
                if "km" in uom.lower():
                    gust_mph = value * km_to_mph
                else:
                    gust_mph = value  # Assume already in mph

                gust_map[timestamp] = f"{int(round(gust_mph))} mph"

        logger.debug(f"Retrieved {len(gust_map)} wind gust data points for gridpoint {gridpoint.grid_id}/{gridpoint.grid_x},{gridpoint.grid_y}")
        return gust_map

    except Exception as e:
        logger.error(f"Error fetching wind gust data from gridpoint API: {e}")
        return {}


def _merge_wind_gust_data(forecast_data: dict, wind_gust_map: dict) -> None:
    """
    Merge wind gust data into forecast periods by matching timestamps.
    Modifies forecast_data in place.
    """
    if "properties" not in forecast_data or "periods" not in forecast_data["properties"]:
        return

    periods = forecast_data["properties"]["periods"]
    matched_count = 0

    for period in periods:
        start_time = period.get("startTime", "")

        # Try to match wind gust data by timestamp
        # Wind gust timestamps might not match exactly, so we look for the closest match
        if start_time:
            # Normalize timestamp for comparison (remove timezone offset variations)
            period_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))

            # Look for exact match first
            gust_value = wind_gust_map.get(start_time)

            # If no exact match, look for timestamp with same hour
            if not gust_value:
                for gust_timestamp, gust_val in wind_gust_map.items():
                    try:
                        gust_dt = datetime.fromisoformat(gust_timestamp.replace('Z', '+00:00'))
                        # Match if same hour
                        if (period_dt.year == gust_dt.year and
                            period_dt.month == gust_dt.month and
                            period_dt.day == gust_dt.day and
                            period_dt.hour == gust_dt.hour):
                            gust_value = gust_val
                            break
                    except:
                        continue

            if gust_value:
                period["windGust"] = gust_value
                matched_count += 1

    logger.debug(f"Merged wind gust data: {matched_count}/{len(periods)} periods matched")


def getForecast(gridpoint: Point) -> Forecast|None:
    """Get forecast for a gridpoint from Firestore or weather API"""
    time = datetime.now(timezone.utc)

    # Check Firestore first
    try:
        cached_forecast = get_gridpoints_to_forecast(gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y)
        if cached_forecast:
            # Fetch wind gust data and merge it
            wind_gust_map = getWindGustData(gridpoint)
            if wind_gust_map:
                _merge_wind_gust_data(cached_forecast, wind_gust_map)
            return Forecast(cached_forecast)
    except Exception as e:
        logger.error(f"Failed to get forecast from Firestore: {e}")

    # Get forecast_url before hitting API
    forecast_url = getForecastUrl(gridpoint, time)

    # Cache miss - fetch from weather API
    try:
        if forecast_url:
            forecast_response = requests.get(forecast_url, headers=HEADERS, timeout=10)

            # Validate response
            if not forecast_response.ok:
                logger.warning(f"Weather API error - Status: {forecast_response.status_code}")
                return Forecast({})

            forecast_data = forecast_response.json()

            # Validate response structure - should have properties with periods
            if "properties" not in forecast_data or "periods" not in forecast_data.get("properties", {}):
                logger.warning(f"Invalid forecast response structure from Weather API")
                return Forecast({})

            # Fetch wind gust data and merge it into forecast periods
            wind_gust_map = getWindGustData(gridpoint)
            if wind_gust_map:
                _merge_wind_gust_data(forecast_data, wind_gust_map)

            expires_at = time + timedelta(hours=3)  # Expire forecast after 3 hours

            # Store forecast data synchronously in Firestore
            try:
                set_gridpoints_to_forecast(gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y, forecast_data, expires_at)
            except Exception as e:
                logger.error(f"Failed to store forecast in Firestore: {e}")

            return Forecast(forecast_data)
        else:
            logger.warning(f"Error getting forecast: no forecast_url found for gridpoint {gridpoint}")
            return Forecast({})
    except Exception as e:
        logger.error(f"Error getting forecast from API: {e}")
        return Forecast({})


def filterWeatherData(coords: list[Coordinates], ignoreEta: bool = False) -> dict:
    coordinate_to_forecasts_map = defaultdict(list)

    for coordinate in _get_progress_bar(coords, desc="Filtering Forecasts"):
        #If ignoreEta is true or there is no eta, look at all periods of the forecast 
        if ignoreEta or not coordinate.eta:
            coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
            coordinate_to_forecasts_map[coordinate_key].append(coordinate.forecasts)
        # If there is an eta just get the forecast period for that eta
        else:
            filtered_period = coordinate.forecasts.filterPeriods(coordinate.eta)
            if filtered_period:
                coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                coordinate_to_forecasts_map[coordinate_key].append(filtered_period)

    return coordinate_to_forecasts_map


def getActiveAlerts(latitude: str, longitude: str) -> list:
    """
    Fetch active weather alerts for a location from Weather.gov API.
    Uses Firestore caching with 15-minute TTL to minimize API calls while
    keeping alert data relatively fresh.

    Args:
        latitude: Latitude coordinate (already truncated)
        longitude: Longitude coordinate (already truncated)

    Returns:
        list: List of active alert features from Weather.gov API
    """
    now = datetime.now(timezone.utc)

    # Check Firestore cache first
    cached_alerts = get_alerts(latitude, longitude)
    if cached_alerts is not None:
        return cached_alerts

    # Cache miss - fetch from Weather.gov API
    try:
        alerts_url = f"https://api.weather.gov/alerts/active?point={latitude},{longitude}"
        response = requests.get(alerts_url, headers=HEADERS, timeout=10)

        if not response.ok:
            logger.warning(f"Alerts API returned status code: {response.status_code}")
            return []

        response_json = response.json()

        # Extract features (alerts) from response
        alerts = response_json.get("features", [])

        # Cache alerts for 15 minutes (alerts are time-sensitive)
        expires_at = now + timedelta(minutes=15)

        try:
            set_alerts(latitude, longitude, alerts, expires_at)
        except Exception as e:
            logger.error(f"Failed to cache alerts in Firestore: {e}")

        return alerts

    except Exception as e:
        logger.error(f"Failed to fetch alerts from Weather.gov API for {latitude},{longitude}: {e}")
        return []


def getWeather(coords: list[Coordinates]):
    distinct_points = {}

    # Get points
    for coordinate in _get_progress_bar(coords, desc="Getting Points"):
        truncated_latitude = truncateCoordinate(coordinate.latitude)
        truncated_longitude = truncateCoordinate(coordinate.longitude)
        coordinate.point = getPoints(truncated_latitude, truncated_longitude)
        distinct_points[coordinate.point] = None

    # Get Weekly forecast for each point
    for point in _get_progress_bar(distinct_points, desc="Getting Forecasts"):
        if point.is_not_empty():
            forecast = getForecast(point)
            distinct_points[point] = forecast

    for coordinate in coords:
        if coordinate.point in distinct_points:
            coordinate.forecasts = distinct_points[coordinate.point]
            
    




