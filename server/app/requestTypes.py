from pydantic import BaseModel, model_validator

def is_in_us(latitude: float, longitude: float) -> bool:
    """Check if coordinates are in any U.S. state or major territory."""
    regions = [
        {"lat_min": 24.396308, "lat_max": 49.384358, "lon_min": -125.0, "lon_max": -66.93457},  # CONUS
        {"lat_min": 51.214183, "lat_max": 71.365162, "lon_min": -179.148909, "lon_max": -129.9795},  # Alaska
        {"lat_min": 18.9115, "lat_max": 22.2356, "lon_min": -160.2471, "lon_max": -154.8066},  # Hawaii
        {"lat_min": 17.8833, "lat_max": 18.5152, "lon_min": -67.9451, "lon_max": -65.2152},  # Puerto Rico
        {"lat_min": 13.25, "lat_max": 13.7, "lon_min": 144.6, "lon_max": 145.0},  # Guam
        {"lat_min": 14.0, "lat_max": 20.0, "lon_min": 144.9, "lon_max": 146.1},  # Northern Mariana Islands
        {"lat_min": -14.3, "lat_max": -11.0, "lon_min": -171.0, "lon_max": -168.0},  # American Samoa
        {"lat_min": 17.6, "lat_max": 18.5, "lon_min": -65.0, "lon_max": -64.3},  # US Virgin Islands
    ]
    for region in regions:
        if region["lat_min"] <= latitude <= region["lat_max"] and region["lon_min"] <= longitude <= region["lon_max"]:
            return True
    return False

class LatLng(BaseModel):
    latitude: str
    longitude: str

    @model_validator(mode="before")  # runs before automatic type coercion
    def validate_in_us(cls, values):
        latitude = values.get("latitude")
        longitude = values.get("longitude")
        if latitude is None or longitude is None:
            raise ValueError("Latitude and longitude are required")

        try:
            latitude_f = float(latitude)
            longitude_f = float(longitude)
        except ValueError:
            raise ValueError("Latitude and longitude must be valid numbers")

        if not is_in_us(latitude_f, longitude_f):
            raise ValueError("Coordinates must be within the United States or its territories")

        return values

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
    address: str|None = None
    eta: str|None = None

class CoordsToWeatherRequest(BaseModel):
    coordinates: list[CoordinateLocation]
    ignoreEta: bool = False
