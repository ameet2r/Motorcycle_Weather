from pydantic import BaseModel

class DirectionsToWeatherRequest(BaseModel):
    origin: str
    destination: str

class CoordsToWeatherRequest(BaseModel):
    coordinates: list
