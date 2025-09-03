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

    if not (request.origin.placeId or request.origin.address or request.origin.location) or not (request.destination.placeId or request.destination.address or request.destination.location):
        result["status"] = 400
        result["suggestedGear"] = None
        return result

    try:
        # Get directions between two locations
        steps, coords = computeRoutes(request)
        print(f"coords after route computed={coords}, steps after route computed={steps}")

        # Get weather for directions. Directions are saved as set of distances and coordinates.
        getWeather(coords)
        print(f"list_of_coordinates after weather retrieved={coords}, and request.ignoreEta={request.ignoreEta}")

        suggested_gear = suggestGear(coords, request.ignoreEta)
        print(f"suggested_gear={suggested_gear}")

        # Build result
        result["status"] = 200
        result["suggestedGear"] = suggested_gear
    except:
        result["status"] = 500
        result["suggestedGear"] = None

    print(f"result={result}")
    return result


@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(request: CoordsToWeatherRequest):
    print(f"Getting weather info for {request}")
    print(MESSAGE_SEPARATOR)

    result = {}
    if len(request.coordinates) == 0:
        result["status"] = 400
        result["suggestedGear"] = None
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

        suggested_gear = suggestGear(list_of_coordinates, request.ignoreEta)
        print(f"suggested_gear={suggested_gear}")

        # Build result
        result["status"] = 200
        result["suggestedGear"] = suggested_gear
    except:
        result["status"] = 500

    print(f"result={result}")
    return result


