import requests
import os


def truncateCoordinate(coordinate: str, max_decimal_places: int = 4) -> str:
    if "." not in coordinate:
        return coordinate
    
    whole, fraction = coordinate.split(".")
    if len(fraction) > max_decimal_places:
        return f"{whole}.{fraction[:max_decimal_places]}"
    else:
        return coordinate


def getWeather(latitude: str, longitude: str):
    print(f"Retrieving Weather for latitude={latitude}, longitude={longitude}")

    truncated_latitude = truncateCoordinate(latitude)
    truncated_longitude = truncateCoordinate(longitude)

    # https://api.weather.gov/points/{lat},{lon}.
    points_url = f"https://api.weather.gov/points/{truncated_latitude},{truncated_longitude}"
    headers = {
        "Accept": "application/geo+json",
        "User-Agent": os.getenv("WEATHER_DOT_GOV_API_KEY")
    }
     
    response = requests.get(points_url, headers=headers)
    response_json = response.json()

    response_properties = response_json["properties"]
    forecast_url = response_properties["forecast"]
    hourly_forecast_url = response_properties["forecastHourly"]
    
    forecast_response = requests.get(forecast_url, headers=headers)
    forecast_response_json = forecast_response.json()
    print(f"forecast_response_json={forecast_response_json}")

    # hourly_forecast_response = requests.get(hourly_forecast_url, headers=headers)
    # hourly_forecast_response_json = hourly_forecast_response.json()
    # print(f"hourly_forecast_response_json={hourly_forecast_response_json}")

