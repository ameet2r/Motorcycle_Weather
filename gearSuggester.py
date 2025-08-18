from tqdm import tqdm
from coordinates import Step


WEATHER_TO_GEAR_MAP = {
    "Raining": "Rain Gear",
    "Sunny": "Breathable gear",
    "Cold": "Handguards and winter gear",
    "Partly Cloudy": "Breathable gear"
}


def suggestGear(route: list[Step]) -> dict:
    suggested_gear = {}

    for step in tqdm(route, desc="Calculating Suggesting Gear"):
        for coordinate in step.coordinates:
            filtered_period = coordinate.forecasts.filterPeriods(coordinate.eta)
            if filtered_period and filtered_period.short_forecast in WEATHER_TO_GEAR_MAP:
                coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                suggested_gear[coordinate_key] = WEATHER_TO_GEAR_MAP[filtered_period.short_forecast]

    return suggested_gear
