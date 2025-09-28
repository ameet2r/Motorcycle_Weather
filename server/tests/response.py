class Response:
    def __init__(self, response: dict):
        if response:
            self.coordinates_to_forecasts_map = response.get("coordinates_to_forecasts_map")
            self.coordinates = response.get("coordinates")
        else:
            self.coordinates_to_forecasts_map = None
            self.coordinates = None
