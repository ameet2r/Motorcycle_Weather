from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from app.directions import computeRoutes
from app.weather import getWeather, filterWeatherData
from tqdm import tqdm
from app.db import init_db_pool, create_tables, close_pool
from app.cache import close_redis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.coordinates import Coordinates
from app.requestTypes import CoordsToWeatherRequest, DirectionsToWeatherRequest
from app.constants import MESSAGE_SEPARATOR


app = FastAPI()

# Allow requests from the following locations
origins = [
    "http://localhost:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins, # can be ["*"] for dev
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startupEvent():
    print("Welcome to Motorcycle Weather")
    print(MESSAGE_SEPARATOR)

    load_dotenv()
    init_db_pool()
    create_tables()
    print("Environment loaded, Database pool initialized, and tables ensured.")


@app.on_event("shutdown")
async def shutdownEvent():
    print("Shutting down service...")
    close_pool()
    close_redis()
    print("Database pool and Redis closed.")


@app.post("/DirectionsToWeather/")
async def main(request: DirectionsToWeatherRequest):
    print(f"Getting weather info for your route from {request.origin} to {request.destination}")
    print(MESSAGE_SEPARATOR)

    result = {}

    if not (request.origin.placeId or request.origin.address or request.origin.location) or not (request.destination.placeId or request.destination.address or request.destination.location):
        result["status"] = 400
        result["coordinates_to_forecasts_map"] = None
        return result

    try:
        # Get directions between two locations
        steps, coords = computeRoutes(request)
        print(f"coords after route computed={coords}, steps after route computed={steps}")

        # Get weather for directions. Directions are saved as set of distances and coordinates.
        getWeather(coords)
        print(f"list_of_coordinates after weather retrieved={coords}, and request.ignoreEta={request.ignoreEta}")

        # Filter forecasts
        coordinates_to_forecasts_map = filterWeatherData(coords, request.ignoreEta)
        print(f"coordinates_to_forecasts_map={coordinates_to_forecasts_map}")

        # Build result
        result["status"] = 200
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map 
    except:
        result["status"] = 500
        result["coordinates_to_forecasts_map"] = None

    print(f"result={result}")
    return result


@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(request: CoordsToWeatherRequest):
    print(f"Getting weather info for {request}")
    print(MESSAGE_SEPARATOR)

    result = {}
    if len(request.coordinates) == 0:
        result["status"] = 400
        result["coordinates_to_forecasts_map"] = None
        return result

    try:
        list_of_coordinates = []
        for element in request.coordinates:
            latitude = element.latLng.latitude
            longitude = element.latLng.longitude
           
            coord_eta = None
            if element.eta:
                coord_eta = datetime.fromisoformat(element.eta).astimezone(timezone.utc)
            list_of_coordinates.append(Coordinates(latitude, longitude, coord_eta))
        print(f"list_of_coordinates after list creation={list_of_coordinates}")

        # Get weather for list of Coordinates
        getWeather(list_of_coordinates)
        print(f"list_of_coordinates after weather retrieved={list_of_coordinates}, and request.ignoreEta={request.ignoreEta}")

        # Filter forecasts
        coordinates_to_forecasts_map = filterWeatherData(list_of_coordinates, request.ignoreEta)
        print(f"coordinates_to_forecasts_map={coordinates_to_forecasts_map}")

        # Build result
        result["status"] = 200
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map 
    except:
        result["status"] = 500
        result["coordinates_to_forecasts_map"] = None

    print(f"result={result}")
    return result


