from collections import defaultdict


WEATHER_TO_GEAR_MAP = {
    "Raining": "Rain Gear",
    "Sunny": "Breathable gear",
    "Cold": "Handguards and winter gear"
}


def suggestGear(point_to_forecast_map: dict) -> set:
    point_to_recommended_gear_map = defaultdict(list)
    suggested_gear = set()

    for point in point_to_forecast_map:
        distinct_short_forecasts = set()
        properties = point_to_forecast_map[point]["properties"]
        periods = properties["periods"]
        
        # TODO: only get the forecast that is relevent to the time I will actually be at the point
        # I will only be able to do this once I switch from just route to timed route in directions.py
        # Currenlty I am grabbing forecasts for multiple days for the given point.

        # Get forecasts for each point
        for period in periods:
            start_time = period["startTime"]
            end_time = period["endTime"]
            temperature = period["temperature"]
            probability_of_precipitation = period["probabilityOfPrecipitation"]["value"]
            wind_speed = period["windSpeed"]
            wind_direction = period["windDirection"]
            short_forecast = period["shortForecast"]
            detailed_forecast = period["detailedForecast"]


            distinct_short_forecasts.add(short_forecast)

        # TODO: need to change logic that recommends gear. Currently I am just using the short_forecast. 
        # I should be taking in the temperature, probability_of_precipitation, wind_speed, wind_direction, and maybe even detailed_forecast

        # Determine which gear is needed to ride through this point
        for forecast in distinct_short_forecasts:
            if forecast in WEATHER_TO_GEAR_MAP:
                point_to_recommended_gear_map[point].append(WEATHER_TO_GEAR_MAP[forecast])
                suggested_gear.add(WEATHER_TO_GEAR_MAP[forecast])


        # print(distinct_short_forecasts)

    return suggested_gear
