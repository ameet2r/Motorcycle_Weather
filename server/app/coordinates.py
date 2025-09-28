from .forecast import Forecast

class Point:
    def __init__(self, grid_id: str, grid_x: str, grid_y: str):
        self.grid_id = grid_id
        self.grid_x = grid_x
        self.grid_y = grid_y

    def __eq__(self, other):
        return isinstance(other, Point) and self.grid_id == other.grid_id and self.grid_x == other.grid_x and self.grid_y == other.grid_y

    def __hash__(self):
        return hash((self.grid_id, self.grid_x, self.grid_y))

    def __repr__(self):
        return f"Point({self.grid_id}, {self.grid_x}, {self.grid_y})"

    def is_not_empty(self):
        return self.grid_id != "" and self.grid_x != "" and self.grid_y != ""

    def to_str(self):
        return f"{self.grid_id}:{self.grid_x}:{self.grid_y}"


class Coordinates:
    def __init__(self, latitude: str, longitude: str, eta = None, point: Point = Point("", "", ""), forecast: Forecast = Forecast({}), address: str|None = None):
        self.latitude = latitude
        self.longitude = longitude
        self.eta = eta
        self.point = point
        self.forecasts = forecast
        self.address = address

    def __eq__(self, other):
        return (isinstance(other, Coordinates) and
            self.latitude == other.latitude and
            self.longitude == other.longitude and
            self.eta == other.eta and
            self.point == other.point and
            self.address == other.address)

    def __hash__(self):
        return hash((self.latitude, self.longitude, self.eta, self.point, self.forecasts, self.address))

    def __repr__(self):
        return f"Coordinates({self.latitude}, {self.longitude}, {self.eta}, {self.point}, {self.forecasts}, {self.address})"


class Step:
    def __init__(self, distanceMeters: str, polyline: str, coordinates: list[Coordinates]):
        self.distance_meters = distanceMeters
        self.polyline = polyline
        self.coordinates = coordinates
