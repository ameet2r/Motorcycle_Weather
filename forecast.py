from datetime import datetime, timedelta, timezone

class Period:
    def __init__(self, period_json: dict):
        if period_json:
            self.number = period_json["number"]
            self.name = period_json["name"]
            self.start_time = period_json["startTime"]
            self.end_time = period_json["endTime"]
            self.is_day_time = period_json["isDaytime"]
            self.temperature = period_json["temperature"]
            self.probability_of_precip = period_json["probabilityOfPrecipitation"]["value"]
            self.wind_speed = period_json["windSpeed"]
            self.wind_direction = period_json["windDirection"]
            self.icon = period_json["icon"]
            self.short_forecast = period_json["shortForecast"]
            self.detailed_forecast = period_json["detailedForecast"]
            self.period_json = period_json
        else:
            self.number = ""
            self.name = ""
            self.start_time = ""
            self.end_time = ""
            self.is_day_time = ""
            self.temperature = ""
            self.probability_of_precip = ""
            self.wind_speed = ""
            self.wind_direction = ""
            self.icon = ""
            self.short_forecast = ""
            self.detailed_forecast = ""
            self.period_json = ""


    def __eq__(self, other):
        return (isinstance(other, Period) and 
            self.number == other.number and
            self.name == other.name and
            self.start_time == other.start_time and
            self.end_time == other.end_time and
            self.is_day_time == other.is_day_time and
            self.temperature == other.temperature and
            self.probability_of_precip == other.probability_of_precip and
            self.wind_speed == other.wind_speed and
            self.wind_direction == other.wind_direction and
            self.icon == other.icon and
            self.short_forecast == other.short_forecast and
            self.detailed_forecast == other.detailed_forecast and
            self.period_json == other.period_json)

    def __hash__(self):
        return hash((self.number, self.name, self.start_time, 
                     self.end_time, self.is_day_time, self.temperature, 
                     self.probability_of_precip, self.wind_speed, self.wind_direction, 
                     self.icon, self.short_forecast, self.detailed_forecast, self.period_json))

    def __repr__(self):
        return f"Period({self.number}, {self.name}, {self.start_time}, {self.end_time}, {self.is_day_time}, {self.temperature}, {self.probability_of_precip}, {self.wind_speed}, {self.wind_speed}, {self.icon}, {self.short_forecast}, {self.detailed_forecast}, {self.period_json})"

    def to_json_str(self):
        return self.period_json


class Forecast:
    def __init__(self, forecast_json: dict):
        if forecast_json:
            properties = forecast_json["properties"]
            self.elevation = properties["elevation"]["value"]
            periods_json = properties["periods"]
            self.periods = []
            for period in periods_json:
                self.periods.append(Period(period))
        else:
            self.elevation = ""
            self.periods = []

    def filterPeriods(self, eta) -> Period:
        if eta:
            for period in self.periods:
                start_time_as_datetime = datetime.fromisoformat(period.start_time).astimezone(timezone.utc)
                end_time_as_datetime = datetime.fromisoformat(period.end_time).astimezone(timezone.utc)
                if start_time_as_datetime <= eta <= end_time_as_datetime:
                    return period

        return Period({})

    def __eq__(self, other):
        len_of_periods_are_equal = len(self.periods) == len(other.periods)  
        is_equal = (isinstance(other, Forecast) and self.elevation == other.elevation)
        sorted_self_period = sorted(self.periods)
        sorted_other_period = sorted(other.periods)
        for i in range(len(sorted_self_period)):
            if (sorted_self_period[i] != sorted_other_period[i]):
                return False
        return len_of_periods_are_equal and is_equal

    def __hash__(self):
        return hash((self.elevation, self.periods))

    def __repr__(self):
        return f"Forecast({self.elevation},{self.periods})"

    def is_empty(self):
        return self.elevation and self.periods


