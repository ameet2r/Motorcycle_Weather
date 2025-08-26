from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from directions import computeRoutes
from weather import getWeather
from gearSuggester import suggestGear
from tqdm import tqdm
from db import init_db_pool, create_tables, close_pool
from cache import close_redis
from fastapi import FastAPI
from coordinates import Coordinates
from requestTypes import CoordsToWeatherRequest, DirectionsToWeatherRequest
from constants import MESSAGE_SEPARATOR


app = FastAPI()

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

    try:
        # Get directions between two locations
        steps, coords = computeRoutes(request)

        # Get weather for directions. Directions are saved as set of distances and coordinates.
        getWeather(coords)

        suggested_gear = suggestGear(coords)

        # Build result
        result["status"] = 200
        result["suggestedGear"] = suggested_gear
    except:
        result["status"] = 500

    print(f"result={result}")
    return result


@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(request: CoordsToWeatherRequest):
    print(f"Getting weather info for {request}")
    print(MESSAGE_SEPARATOR)

    result = {}

    try:
        list_of_coordinates = []
        for element in request.coordinates:
            coordinate = element["coordinate"]
            latitude = coordinate["latitude"]
            longitude = coordinate["longitude"]
            coord_datetime = datetime.fromisoformat(coordinate["eta"]).astimezone(timezone.utc)
            list_of_coordinates.append(Coordinates(latitude, longitude, coord_datetime ))

        # Get weather for list of Coordinates
        getWeather(list_of_coordinates)

        suggested_gear = suggestGear(list_of_coordinates)

        # Build result
        result["status"] = 200
        result["suggestedGear"] = suggested_gear
    except:
        result["status"] = 500

    print(f"result={result}")
    return result


