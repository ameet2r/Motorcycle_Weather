from pydantic import BaseModel, model_validator, field_validator, Field
import re

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
    placeId: str|None = Field(None, max_length=500)
    address: str|None = Field(None, max_length=500)

    @field_validator('placeId')
    @classmethod
    def validate_place_id(cls, v):
        """Validate Google Place ID format if provided"""
        if v is not None:
            # Google Place IDs are alphanumeric with underscores/hyphens, typically start with specific prefixes
            if not re.match(r'^[A-Za-z0-9_-]+$', v):
                raise ValueError("Invalid Place ID format")
            if len(v) < 10 or len(v) > 500:
                raise ValueError("Place ID length must be between 10 and 500 characters")
        return v

    @field_validator('address')
    @classmethod
    def validate_address(cls, v):
        """Validate address format if provided"""
        if v is not None:
            # Basic sanitization - no control characters
            if any(ord(char) < 32 for char in v):
                raise ValueError("Address contains invalid control characters")
        return v

class DirectionsToWeatherRequest(BaseModel):
    origin: Waypoint
    destination: Waypoint
    intermediates: list[Waypoint] = Field(default=[], max_length=25)
    trafficAware: bool = False
    ignoreEta: bool = False

    @field_validator('intermediates')
    @classmethod
    def validate_intermediates_length(cls, v):
        """Limit number of intermediate waypoints to prevent DoS"""
        if len(v) > 25:
            raise ValueError("Maximum 25 intermediate waypoints allowed")
        return v

class CoordinateLocation(BaseModel):
    latLng: LatLng
    address: str|None = Field(None, max_length=500)
    eta: str|None = Field(None, max_length=50)

    @field_validator('address')
    @classmethod
    def validate_address(cls, v):
        """Validate address format if provided"""
        if v is not None:
            # Basic sanitization - no control characters
            if any(ord(char) < 32 for char in v):
                raise ValueError("Address contains invalid control characters")
        return v

    @field_validator('eta')
    @classmethod
    def validate_eta_format(cls, v):
        """Validate ETA is a valid ISO format datetime string"""
        if v is not None:
            from datetime import datetime, timezone
            try:
                # Attempt to parse as ISO format
                datetime.fromisoformat(v).astimezone(timezone.utc)
            except (ValueError, TypeError):
                raise ValueError("ETA must be a valid ISO format datetime string")
        return v

class CoordsToWeatherRequest(BaseModel):
    coordinates: list[CoordinateLocation] = Field(..., max_length=200)
    ignoreEta: bool = False

    @field_validator('coordinates')
    @classmethod
    def validate_coordinates_length(cls, v):
        """Limit number of coordinates to prevent DoS"""
        if len(v) > 200:
            raise ValueError("Maximum 200 coordinates allowed")
        if len(v) == 0:
            raise ValueError("At least one coordinate is required")
        return v

class SearchCoordinate(BaseModel):
    """Coordinate data for a saved search"""
    key: str = Field(..., max_length=100)
    latitude: str
    longitude: str
    address: str = Field(..., max_length=500)
    elevation: str | None = Field(None, max_length=50)  # Optional - not needed for cloud sync
    periods: list | None = None  # Optional - stored locally only
    summary: dict | None = None  # Optional - stored locally only

    @field_validator('key')
    @classmethod
    def validate_key_format(cls, v):
        """Validate key is in lat:lng format"""
        if ':' not in v:
            raise ValueError("Key must be in 'latitude:longitude' format")
        return v

class CreateSearchRequest(BaseModel):
    """Request model for creating a search"""
    id: str = Field(..., min_length=1, max_length=100)
    timestamp: str = Field(..., max_length=50)
    coordinates: list[SearchCoordinate] = Field(..., max_length=200)

    @field_validator('id')
    @classmethod
    def validate_search_id(cls, v):
        """Validate search ID format - alphanumeric, hyphens, underscores only"""
        if not re.match(r'^[A-Za-z0-9_-]+$', v):
            raise ValueError("Search ID must contain only alphanumeric characters, hyphens, and underscores")
        return v

    @field_validator('timestamp')
    @classmethod
    def validate_timestamp_format(cls, v):
        """Validate timestamp is a valid ISO format datetime string"""
        from datetime import datetime, timezone
        try:
            datetime.fromisoformat(v).astimezone(timezone.utc)
        except (ValueError, TypeError):
            raise ValueError("Timestamp must be a valid ISO format datetime string")
        return v

    @field_validator('coordinates')
    @classmethod
    def validate_coordinates_length(cls, v):
        """Limit number of coordinates to prevent DoS"""
        if len(v) > 200:
            raise ValueError("Maximum 200 coordinates allowed")
        if len(v) == 0:
            raise ValueError("At least one coordinate is required")
        return v
