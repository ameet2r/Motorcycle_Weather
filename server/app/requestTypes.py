from pydantic import BaseModel

class LatLng(BaseModel):
    latitude: str
    longitude: str

class Location(BaseModel):
    latLng: LatLng
    heading: int = 0

class Waypoint(BaseModel):
    via: bool = False
    vehicleStopover: bool = False
    sideOfRoad: bool = False
    location: Location|None = None
    placeId: str|None = None
    address: str|None = None

class DirectionsToWeatherRequest(BaseModel):
    origin: Waypoint
    destination: Waypoint
    intermediates: list[Waypoint] = []
    trafficAware: bool = False
    ignoreEta: bool = False

class CoordinateLocation(BaseModel):
    latLng: LatLng
    eta: str|None = None

class CoordsToWeatherRequest(BaseModel):
    coordinates: list[CoordinateLocation]
    ignoreEta: bool = False
