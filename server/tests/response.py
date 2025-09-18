class Response:
    def __init__(self, response: dict):
        if response:
            self.coordinates_to_forecasts_map = response["coordinates_to_forecasts_map"]
        else:
            self.coordinates_to_forecasts_map = None
