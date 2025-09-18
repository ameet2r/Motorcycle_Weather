from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from app.directions import computeRoutes
from app.weather import getWeather, filterWeatherData
from tqdm import tqdm
from app.db import init_db_pool, create_tables, close_pool
from app.cache import close_redis
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.coordinates import Coordinates
from app.requestTypes import CoordsToWeatherRequest, DirectionsToWeatherRequest
from app.constants import MESSAGE_SEPARATOR
import os


app = FastAPI()

# Allow requests from the following locations
origins = os.getenv("CORS_ORIGINS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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


async def main(request: DirectionsToWeatherRequest):
    print(f"Getting weather info for your route from {request.origin} to {request.destination}")
    print(MESSAGE_SEPARATOR)

    result = {}

    if not (request.origin.placeId or request.origin.address or request.origin.location) or not (request.destination.placeId or request.destination.address or request.destination.location):
        raise HTTPException(status_code=400, detail="No locations provided")

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
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map 
    except:
        raise HTTPException(status_code=500, detail="Internal server error")

    print(f"result={result}")
    return result


@app.post("/CoordinatesToWeather/")
async def coordinatesToWeather(request: CoordsToWeatherRequest):
    print(f"Getting weather info for {request}")
    print(MESSAGE_SEPARATOR)

    result = {}
    if len(request.coordinates) == 0:
        raise HTTPException(status_code=400, detail="No coordinates provided")

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
        result["coordinates_to_forecasts_map"] = coordinates_to_forecasts_map 
    except:
        raise HTTPException(status_code=500, detail="Internal server error")

    print(f"result={result}")
    return result


