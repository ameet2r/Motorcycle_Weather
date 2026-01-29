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


def _extract_gridpoint_layer(properties: dict, layer_name: str, convert_fn=None) -> dict:
    """
    Extract a time series layer from gridpoint properties.
    Returns a dict mapping ISO timestamp strings to converted values.
    """
    if layer_name not in properties:
        return {}

    layer = properties[layer_name]
    values = layer.get("values", [])
    uom = layer.get("uom", "")
    result = {}

    for entry in values:
        valid_time = entry.get("validTime", "")
        value = entry.get("value")

        if valid_time and value is not None:
            timestamp = valid_time.split("/")[0]
            if convert_fn:
                result[timestamp] = convert_fn(value, uom)
            else:
                result[timestamp] = value

    return result


def _convert_wind_gust(value, uom):
    """Convert wind gust to mph string."""
    km_to_mph = 0.621371
    if "km" in uom.lower():
        return f"{int(round(value * km_to_mph))} mph"
    return f"{int(round(value))} mph"


def _convert_visibility_to_miles(value, uom):
    """Convert visibility to miles (float)."""
    if "m" in uom.lower() and "mi" not in uom.lower():
        return round(value / 1609.34, 2)
    return round(value, 2)


def _convert_celsius_to_fahrenheit(value, uom):
    """Convert temperature to Fahrenheit (float)."""
    if "degc" in uom.lower() or "celsius" in uom.lower():
        return round(value * 9 / 5 + 32, 1)
    return round(value, 1)


def _convert_percent(value, uom):
    """Pass through percent values (float)."""
    return round(value, 1)


def getGridpointData(gridpoint: Point) -> dict:
    """
    Get supplementary time series data from raw gridpoint endpoint.
    Returns a dict with keys: 'windGust', 'visibility', 'apparentTemperature', 'relativeHumidity'.
    Each maps ISO timestamp strings to converted values.
    """
    empty_result = {"windGust": {}, "visibility": {}, "apparentTemperature": {}, "relativeHumidity": {}}

    try:
        gridpoint_url = f"https://api.weather.gov/gridpoints/{gridpoint.grid_id}/{gridpoint.grid_x},{gridpoint.grid_y}"
        response = requests.get(gridpoint_url, headers=HEADERS, timeout=10)

        if not response.ok:
            logger.warning(f"Gridpoint API error - Status: {response.status_code}")
            return empty_result

        gridpoint_data = response.json()

        if "properties" not in gridpoint_data:
            logger.debug(f"No properties in gridpoint response for {gridpoint.grid_id}/{gridpoint.grid_x},{gridpoint.grid_y}")
            return empty_result

        props = gridpoint_data["properties"]

        result = {
            "windGust": _extract_gridpoint_layer(props, "windGust", _convert_wind_gust),
            "visibility": _extract_gridpoint_layer(props, "visibility", _convert_visibility_to_miles),
            "apparentTemperature": _extract_gridpoint_layer(props, "apparentTemperature", _convert_celsius_to_fahrenheit),
            "relativeHumidity": _extract_gridpoint_layer(props, "relativeHumidity", _convert_percent),
        }

        return result

    except Exception as e:
        logger.error(f"Error fetching gridpoint data from API: {e}")
        return empty_result


def _match_timestamp_value(start_time: str, data_map: dict):
    """
    Match a period start_time against a data map by exact match or same-hour match.
    Returns the matched value or None.
    """
    if not start_time or not data_map:
        return None

    # Exact match first
    value = data_map.get(start_time)
    if value is not None:
        return value

    # Same-hour match
    try:
        period_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        for ts, val in data_map.items():
            try:
                ts_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                if (period_dt.year == ts_dt.year and
                    period_dt.month == ts_dt.month and
                    period_dt.day == ts_dt.day and
                    period_dt.hour == ts_dt.hour):
                    return val
            except:
                continue
    except:
        pass

    return None


def _merge_gridpoint_data(forecast_data: dict, gridpoint_data: dict) -> None:
    """
    Merge gridpoint data (wind gust, visibility, apparent temp, humidity)
    into forecast periods by matching timestamps.
    Modifies forecast_data in place.
    """
    if "properties" not in forecast_data or "periods" not in forecast_data["properties"]:
        return

    periods = forecast_data["properties"]["periods"]
    wind_gust_map = gridpoint_data.get("windGust", {})
    visibility_map = gridpoint_data.get("visibility", {})
    apparent_temp_map = gridpoint_data.get("apparentTemperature", {})
    humidity_map = gridpoint_data.get("relativeHumidity", {})

    for period in periods:
        start_time = period.get("startTime", "")

        gust_value = _match_timestamp_value(start_time, wind_gust_map)
        if gust_value is not None:
            period["windGust"] = gust_value

        vis_value = _match_timestamp_value(start_time, visibility_map)
        if vis_value is not None:
            period["visibility"] = vis_value

        apparent_temp_value = _match_timestamp_value(start_time, apparent_temp_map)
        if apparent_temp_value is not None:
            period["apparent_temperature"] = apparent_temp_value

        hum_value = _match_timestamp_value(start_time, humidity_map)
        if hum_value is not None:
            period["humidity"] = hum_value


def getForecast(gridpoint: Point) -> Forecast|None:
    """Get forecast for a gridpoint from Firestore or weather API"""
    time = datetime.now(timezone.utc)

    # Check Firestore first
    try:
        cached_forecast = get_gridpoints_to_forecast(gridpoint.grid_id, gridpoint.grid_x, gridpoint.grid_y)
        if cached_forecast:
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

            # Fetch gridpoint data (wind gust, visibility, apparent temp, humidity) and merge
            # This is done before caching so cached forecasts already contain all enriched data
            gridpoint_data = getGridpointData(gridpoint)
            _merge_gridpoint_data(forecast_data, gridpoint_data)

            # Use TTL from API Cache-Control header, default to 3 hours
            expires_at = time + timedelta(hours=3)
            cache_control = forecast_response.headers.get("Cache-Control", "")
            try:
                if "max-age=" in cache_control:
                    max_age_seconds = int(cache_control.split("max-age=")[1].split(",")[0])
                    expires_at = time + timedelta(seconds=max_age_seconds)
            except (ValueError, IndexError):
                logger.debug("Could not parse Cache-Control max-age from forecast response, using default 3 hours")

            # Store enriched forecast data in Firestore
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
            
    




