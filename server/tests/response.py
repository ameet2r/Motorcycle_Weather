class Response:
    def __init__(self, response: dict):
        if response:
            self.status_code = response["status"]
            self.coordinates_to_forecasts_map = response["coordinates_to_forecasts_map"]
        else:
            self.status_code = None
            self.coordinates_to_forecasts_map = None
