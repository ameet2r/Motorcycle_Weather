from tqdm import tqdm
from app.coordinates import Step, Coordinates
from collections import defaultdict


WEATHER_TO_GEAR_MAP = defaultdict(lambda: "All weather gear")
WEATHER_TO_GEAR_MAP["Raining"] = "Rain Gear"
WEATHER_TO_GEAR_MAP["Sunny"] = "Breathable gear"
WEATHER_TO_GEAR_MAP["Cold"] = "Handguards and winter gear"
WEATHER_TO_GEAR_MAP["Partly Cloudy"] =  "Breathable gear"


def suggestGear(coords: list[Coordinates], ignoreEta: bool = False) -> dict:

    suggested_gear = defaultdict(set)

    for coordinate in tqdm(coords, desc="Calculating Suggesting Gear"):
        #If ignoreEta is true or there is no eta, look at all periods of the forecast 
        if ignoreEta or not coordinate.eta:
            for period in coordinate.forecasts.periods:
                if period:
                    coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                    suggested_gear[coordinate_key].add(WEATHER_TO_GEAR_MAP[period.short_forecast])
        # If there is an eta just get the forecast period for that eta
        else:
            filtered_period = coordinate.forecasts.filterPeriods(coordinate.eta)
            print(f"filtered_period={filtered_period}, eta={coordinate.eta}, WEATHER_TO_GEAR_MAP={WEATHER_TO_GEAR_MAP}")
            if filtered_period:
                coordinate_key = f"{coordinate.latitude}:{coordinate.longitude}"
                suggested_gear[coordinate_key].add(WEATHER_TO_GEAR_MAP[filtered_period.short_forecast])

    return suggested_gear
