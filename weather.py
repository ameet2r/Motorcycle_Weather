import requests
import os
from directions import Step


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


def getPoints(latitude: str, longitude: str, points_to_forecast_urls_map: dict) -> tuple|None:
    truncated_latitude = truncateCoordinate(latitude)
    truncated_longitude = truncateCoordinate(longitude)

    # https://api.weather.gov/points/{lat},{lon}.
    points_url = f"https://api.weather.gov/points/{truncated_latitude},{truncated_longitude}"
     
    response = requests.get(points_url, headers=HEADERS)
    response_json = response.json()

    if response.status_code == 200:
        response_properties = response_json["properties"]
        
        gridId = response_properties["gridId"]
        gridX= response_properties["gridX"]
        gridY= response_properties["gridY"]
        grid_tuple = (gridId, gridX, gridY)

        if grid_tuple not in points_to_forecast_urls_map:
            forecast_url = response_properties["forecast"]
            # hourly_forecast_url = response_properties["forecastHourly"]

            points_to_forecast_urls_map[grid_tuple] = forecast_url

        return grid_tuple

    else:
        return None
        # return f"Error getting response for the following request to the points endpoint. url={points_url}, request={response.request}, status_code={response.status_code}"


def getWeather(route: list[Step]) -> dict:
    coordinate_to_point_map = {}
    points_to_forecast_urls_map = {}
    points_to_forecast_map = {}

    print("Getting points")
    # Get points
    for step in route:
        for coordinate in step.coordinates:
            # Don't request the same coordinates if we have already done them.
            coordinate_key = (coordinate.latitude, coordinate.longitude)
            if coordinate_key not in coordinate_to_point_map:
                coordinate_to_point_map[coordinate_key] = getPoints(latitude=coordinate.latitude, longitude=coordinate.longitude, points_to_forecast_urls_map=points_to_forecast_urls_map)

    print("Getting forecasts")
    # Get forecasts 
    for step in route:
        for coordinate in step.coordinates:
            coordinate_key = (coordinate.latitude, coordinate.longitude)
            point = coordinate_to_point_map[coordinate_key]

            # Only get forecast for points that we have not already gotten forecasts for
            if point is not None and point not in points_to_forecast_map:
                forecast_url = points_to_forecast_urls_map[point]
                forecast_response = requests.get(forecast_url, headers=HEADERS)
                if forecast_response.status_code == 200:
                    points_to_forecast_map[point] = forecast_response.json()
                else:
                    print(f"Error getting response for the following request the forecast endpoint. url={forecast_url}, request={forecast_response.request}, status_code={forecast_response.status_code}")
                    points_to_forecast_map[point] = None
    
    return points_to_forecast_map





            # hourly_forecast_response = requests.get(hourly_forecast_url, headers=headers)
            # hourly_forecast_response_json = hourly_forecast_response.json()
            # print(f"hourly_forecast_response_json={hourly_forecast_response_json}")

    #     return f"Error getting response for the following request to the points endpoint. url={points_url}, request={response.request}, status_code={response.status_code}"


