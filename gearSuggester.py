from tqdm import tqdm
from coordinates import Step


WEATHER_TO_GEAR_MAP = {
    "Raining": "Rain Gear",
    "Sunny": "Breathable gear",
    "Cold": "Handguards and winter gear",
    "Partly Cloudy": "Breathable gear"
}


def suggestGear(route: list[Step]) -> set:
    suggested_gear = set()

    for step in tqdm(route, desc="Calculating Suggesting Gear"):
        for coordinate in step.coordinates:
            filtered_period = coordinate.forecasts.filterPeriods(coordinate.eta)
            if filtered_period and filtered_period.short_forecast in WEATHER_TO_GEAR_MAP:
                suggested_gear.add(WEATHER_TO_GEAR_MAP[filtered_period.short_forecast])

    return suggested_gear
