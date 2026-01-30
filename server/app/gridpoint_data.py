from datetime import datetime


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


def _build_hour_index(data_map: dict) -> dict:
    """
    Pre-build a {(year, month, day, hour): value} index from a data map
    for O(1) same-hour lookups.
    """
    index = {}
    for ts, val in data_map.items():
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            key = (dt.year, dt.month, dt.day, dt.hour)
            if key not in index:
                index[key] = val
        except:
            continue
    return index


def _match_timestamp_value(start_time: str, data_map: dict, hour_index: dict = None):
    """
    Match a period start_time against a data map by exact match or same-hour match.
    If hour_index is provided, uses O(1) lookup instead of O(n) linear scan.
    Returns the matched value or None.
    """
    if not start_time or not data_map:
        return None

    # Exact match first
    value = data_map.get(start_time)
    if value is not None:
        return value

    # Same-hour match via pre-built index (O(1)) or fallback linear scan (O(n))
    try:
        period_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if hour_index is not None:
            return hour_index.get((period_dt.year, period_dt.month, period_dt.day, period_dt.hour))
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


def merge_gridpoint_data(forecast_data: dict, gridpoint_data: dict) -> None:
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

    # Build hour indexes once for O(1) lookups across all periods
    wind_gust_index = _build_hour_index(wind_gust_map)
    visibility_index = _build_hour_index(visibility_map)
    apparent_temp_index = _build_hour_index(apparent_temp_map)
    humidity_index = _build_hour_index(humidity_map)

    for period in periods:
        start_time = period.get("startTime", "")

        gust_value = _match_timestamp_value(start_time, wind_gust_map, wind_gust_index)
        if gust_value is not None:
            period["windGust"] = gust_value

        vis_value = _match_timestamp_value(start_time, visibility_map, visibility_index)
        if vis_value is not None:
            period["visibility"] = vis_value

        apparent_temp_value = _match_timestamp_value(start_time, apparent_temp_map, apparent_temp_index)
        if apparent_temp_value is not None:
            period["apparent_temperature"] = apparent_temp_value

        hum_value = _match_timestamp_value(start_time, humidity_map, humidity_index)
        if hum_value is not None:
            period["humidity"] = hum_value


def extract_gridpoint_layers(properties: dict) -> dict:
    """
    Extract all supplementary layers from raw gridpoint API properties.
    Returns a dict with keys: 'windGust', 'visibility', 'apparentTemperature', 'relativeHumidity'.
    """
    return {
        "windGust": _extract_gridpoint_layer(properties, "windGust", _convert_wind_gust),
        "visibility": _extract_gridpoint_layer(properties, "visibility", _convert_visibility_to_miles),
        "apparentTemperature": _extract_gridpoint_layer(properties, "apparentTemperature", _convert_celsius_to_fahrenheit),
        "relativeHumidity": _extract_gridpoint_layer(properties, "relativeHumidity", _convert_percent),
    }
