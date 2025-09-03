class Response:
    def __init__(self, response: dict):
        if response:
            self.status_code = response["status"]
            self.suggested_gear = response["suggestedGear"]
        else:
            self.status_code = None
            self.suggested_gear = None
