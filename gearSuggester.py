from tqdm import tqdm
from coordinates import Step, Coordinates
from collections import defaultdict


WEATHER_TO_GEAR_MAP = {
    "Raining": "Rain Gear",
    "Sunny": "Breathable gear",
    "Cold": "Handguards and winter gear",
    "Partly Cloudy": "Breathable gear"
}


def suggestGear(coords: list[Coordinates], ignoreEta: bool = False) -> dict:
    suggested_gear = defaultdict(set)

    for coordinate in tqdm(coords, desc="Calculating Suggesting Gear"):
        #If ignoreEta is true or there is no eta, look at all periods of the forecast 
        if ignoreEta or not coordinate.eta:
            for period in coordinate.forecasts.periods:
                if period and period.short_forecast in WEATHER_TO_GEAR_MAP:
                    coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                    suggested_gear[coordinate_key].add(WEATHER_TO_GEAR_MAP[period.short_forecast])
        # If there is an eta just get the forecast period for that eta
        else:
            filtered_period = coordinate.forecasts.filterPeriods(coordinate.eta)
            if filtered_period and filtered_period.short_forecast in WEATHER_TO_GEAR_MAP:
                coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                suggested_gear[coordinate_key].add(WEATHER_TO_GEAR_MAP[filtered_period.short_forecast])

    return suggested_gear
